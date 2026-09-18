"""
PhotoUpdater module for managing periodic photo updates from Immich.
"""
import logging
import os
import signal
import asyncio
from datetime import datetime, timedelta

import requests

from config.schema import AppConfig, PhotoFilters
from immich.client import ImmichClient, ImmichConfig
from immich.selectors import RandomAssetSelector, SmartSearchAssetSelector, RandomSmartSearchAssetSelector, AssetSelector
from immich.immich_api import ImmichAPI
from utils import (
    save_binary_data,
    extract_zip,
    cleanup_file,
    process_media_files,
    cleanup_directory,
    move_file,
    remove_directory
)
from utils.media_utils import (
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    HEIC_FORMATS
)

logger = logging.getLogger(__name__)

# Every media extension the updater owns inside hass_img_path. Files with these
# extensions are replaced on a successful update; anything else is left alone.
MANAGED_MEDIA_FORMATS = SUPPORTED_IMAGE_FORMATS + SUPPORTED_VIDEO_FORMATS + HEIC_FORMATS

# Extensions that are publishable to the album directory once processing is done
# (HEIC is converted to JPG/MP4 first, so it is never published).
PUBLISHABLE_MEDIA_FORMATS = SUPPORTED_IMAGE_FORMATS + SUPPORTED_VIDEO_FORMATS

# New photos are downloaded, extracted and converted inside this subdirectory of
# hass_img_path before replacing the previous batch. It lives inside the album
# directory so the final move is a same-filesystem rename even when hass_img_path
# is an NFS mount point. The leading dot keeps it out of Home Assistant's folder
# sensor (glob does not match dotfiles), and cleanup_directory skips directories,
# so it is never served as a photo.
STAGING_DIR_NAME = ".immich-staging"

class PhotoUpdater:
    def __init__(self, config: AppConfig):
        self.config = config
        self.running = False
        self.last_update = None
        self.current_filter_index = 0
        
        # Configure Immich client
        immich_config = ImmichConfig(
            url=config.immich.url,
            api_key=config.immich.api_key
        )
        
        # Create and configure session with API key
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": config.immich.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

        # Get list of people from Immich
        self.api = ImmichAPI(self.session, config.immich.url)
        self.people = self.api.get_people()
        
        # Create the base client
        self.client = ImmichClient(immich_config, None)  # Selector will be set per update
        
        logger.info(f"Initialized with {len(config.filters)} filter sets:")
        for filter_set in config.filters:
            logger.info(f"  {filter_set}")

    def _create_selector_for_filter(self, filter_set: PhotoFilters) -> AssetSelector:
        """Create an asset selector for the given filter set."""
        # Get person IDs for filtered people if specified
        person_ids = None
        if filter_set.people:
            try:
                person_ids = [self.people[name] for name in filter_set.people]
                logger.debug(f"Using person IDs: {person_ids} for people: {filter_set.people}")
            except KeyError as e:
                logger.warning(f"Person not found in Immich: {e}")
                logger.debug("Available people: %s", list(self.people.keys()))
        
        # Common parameters for both selector types
        selector_params = {
            "session": self.session,
            "base_url": self.config.immich.url,
            "city": filter_set.city,
            "person_ids": person_ids,
            "taken_after": filter_set.taken_after,
            "taken_before": filter_set.taken_before
        }
        
        # Create the appropriate selector type
        if filter_set.selector_type == "smart":
            return SmartSearchAssetSelector(
                search_query=filter_set.search_query,
                **selector_params
            )
        elif filter_set.selector_type == "smart-rng":
            return RandomSmartSearchAssetSelector(
                search_query=filter_set.search_query,
                max_search_results=filter_set.max_search_results or 250,  # Default to 250 if not specified
                **selector_params
            )
        else:  # random selector
            return RandomAssetSelector(**selector_params)

    def _stage_photos(self, staging_dir: str) -> list:
        """
        Download, extract and convert the next batch of photos into a staging directory.

        Nothing outside the staging directory is touched, so a failure anywhere in
        here leaves the photos currently on display alone.

        Args:
            staging_dir: Directory to download and convert into

        Returns:
            List of paths to publishable media files inside the staging directory
            (empty if the selector matched no assets)
        """
        # Get asset IDs using the configured selector
        logger.info(f"Fetching {self.config.num_photos} photos...")
        asset_ids = self.client.get_assets(count=self.config.num_photos)

        if not asset_ids:
            return []

        # Download the assets
        logger.info(f"Downloading {len(asset_ids)} photos...")
        data = self.client.download_assets(asset_ids)

        # Save the downloaded archive
        archive_path = os.path.join(staging_dir, "photos.zip")
        save_binary_data(data, archive_path)

        # Extract photos from the archive
        extracted_files = extract_zip(archive_path, staging_dir)
        logger.info(f"Extracted {len(extracted_files)} files")

        # Process the extracted files (convert HEIC to JPG/MP4)
        processed_files = process_media_files(extracted_files, staging_dir)
        logger.info(f"Processed {len(processed_files)} media files")

        # Clean up the ZIP file and original HEIC files
        cleanup_file(archive_path)
        for file in extracted_files:
            if file not in processed_files:  # Only delete original if it was converted
                cleanup_file(file)

        return [
            path for path in processed_files
            if os.path.splitext(path)[1].lower() in PUBLISHABLE_MEDIA_FORMATS
            and os.path.isfile(path)
        ]

    def _publish_photos(self, staged_files: list) -> int:
        """
        Replace the photos in the album directory with the staged batch.

        This is the only step that touches the album directory, and it is only
        reached once a complete, non-empty batch is waiting in staging. Moves are
        renames within the same filesystem, so the window in which the directory is
        empty is as short as possible.

        Args:
            staged_files: Paths of the staged media files to publish

        Returns:
            Number of files published
        """
        logger.info("Cleaning up existing media files...")
        cleanup_directory(self.config.hass_img_path, file_types=MANAGED_MEDIA_FORMATS)

        published = 0
        used_names = set()
        for staged_file in staged_files:
            # Flatten to the base name: a zip that contains folders would otherwise
            # hide photos in subdirectories where Home Assistant never sees them.
            name = os.path.basename(staged_file)
            if name in used_names:
                stem, ext = os.path.splitext(name)
                suffix = 1
                while f"{stem}_{suffix}{ext}" in used_names:
                    suffix += 1
                name = f"{stem}_{suffix}{ext}"
            used_names.add(name)

            move_file(staged_file, os.path.join(self.config.hass_img_path, name))
            published += 1

        return published

    async def update_photos(self):
        """Update photos from Immich using the current filter set"""
        current_filter = self.config.filters[self.current_filter_index]
        logger.info(f"Updating photos using {current_filter}")

        staging_dir = os.path.join(self.config.hass_img_path, STAGING_DIR_NAME)

        try:
            # Remove any staging directory left behind by a crashed run before reusing it
            remove_directory(staging_dir)
            os.makedirs(staging_dir, exist_ok=True)

            # Update selector for current filter set
            self.client.asset_selector = self._create_selector_for_filter(current_filter)

            # Fetch the whole new batch first; the photos on display are untouched
            # until it is complete
            staged_files = self._stage_photos(staging_dir)

            if not staged_files:
                logger.warning(
                    f"No photos to publish for {current_filter}; keeping the previous photos on display."
                )
            else:
                published = self._publish_photos(staged_files)
                self.last_update = datetime.now()
                logger.info(
                    f"Photo update completed successfully with {published} files. "
                    f"You should now see photos for {current_filter}."
                )

            # Move to next filter set
            self.current_filter_index = (self.current_filter_index + 1) % len(self.config.filters)
            next_filter = self.config.filters[self.current_filter_index]
            logger.info(f"Next update will use {next_filter}.")

        except Exception as e:
            logger.error(
                f"Error updating photos: {e}. Keeping the previous photos on display.",
                exc_info=True
            )
        finally:
            # Never leave a staging directory behind, successful run or not
            remove_directory(staging_dir)

    async def run(self):
        """Run the photo updater in a continuous loop"""
        self.running = True
        
        # Set up signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
            
        logger.info(f"Starting photo updater with {self.config.update_interval_minutes} minute interval")
        
        while self.running:
            try:
                await self.update_photos()
                # Log next update time
                next_update = datetime.now() + timedelta(minutes=self.config.update_interval_minutes)
                logger.info(f"Next update scheduled for {next_update}")
                # Sleep for the configured interval
                await asyncio.sleep(self.config.update_interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in update loop: {e}", exc_info=True)
                # Sleep for 1 minute before retrying on error
                await asyncio.sleep(60)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False 