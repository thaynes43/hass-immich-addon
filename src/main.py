"""
Main application entry point.
"""
import logging
import os
import sys
from pathlib import Path

from config import (
    IMMICH_URL, 
    IMMICH_API_KEY, 
    NUM_PHOTOS, 
    HASS_IMG_PATH,
    CITY_FILTER,
    DATE_FILTER,
    get_people_list
)
from immich.client import ImmichClient, ImmichConfig
from immich.selectors import RandomAssetSelector
from immich.immich_api import ImmichAPI
from utils import (
    save_binary_data, 
    extract_zip, 
    cleanup_file, 
    process_media_files,
    cleanup_directory
)
from utils.media_utils import (
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    HEIC_FORMATS
)
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    # Create Immich client with random asset selector
    config = ImmichConfig(
        url=IMMICH_URL,
        api_key=IMMICH_API_KEY
    )
    
    # Create and configure session with API key
    session = requests.Session()
    session.headers.update({
        "x-api-key": IMMICH_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    })

    # Get list of people from Immich
    api = ImmichAPI(session, IMMICH_URL)
    people = api.get_people()
    
    # Get person IDs for filtered people if specified
    person_ids = None
    people_filter = get_people_list()
    if people_filter:
        try:
            person_ids = [people[name] for name in people_filter]
            logger.info(f"Filtering photos for people: {', '.join(people_filter)}")
        except KeyError as e:
            logger.warning(f"Person not found in Immich: {e}")
            logger.debug("Available people: %s", list(people.keys()))
    
    # Initialize the asset selector with authenticated session
    selector = RandomAssetSelector(
        session=session,
        base_url=IMMICH_URL,
        city=CITY_FILTER,
        person_ids=person_ids,
        use_date_filter=DATE_FILTER
    )
    
    # Create the client with the selector
    client = ImmichClient(config, selector)
    
    try:
        # Clean up existing media files
        logger.info("Cleaning up existing media files...")
        cleanup_directory(HASS_IMG_PATH, file_types=SUPPORTED_IMAGE_FORMATS + SUPPORTED_VIDEO_FORMATS + HEIC_FORMATS)
        
        # Get asset IDs using the configured selector
        logger.info(f"Fetching {NUM_PHOTOS} photos...")
        asset_ids = client.get_assets(count=NUM_PHOTOS)
        
        # Download the assets
        logger.info(f"Downloading {len(asset_ids)} photos...")
        data = client.download_assets(asset_ids)
        
        # Save the downloaded archive
        archive_path = os.path.join(HASS_IMG_PATH, "photos.zip")
        save_binary_data(data, archive_path)
        
        # Extract photos from the archive
        extracted_files = extract_zip(archive_path, HASS_IMG_PATH)
        logger.info(f"Extracted {len(extracted_files)} files")
        
        # Process the extracted files (convert HEIC to JPG/MP4)
        processed_files = process_media_files(extracted_files, HASS_IMG_PATH)
        logger.info(f"Processed {len(processed_files)} media files")
        
        # Clean up the ZIP file and original HEIC files
        cleanup_file(archive_path)
        for file in extracted_files:
            if file not in processed_files:  # Only delete original if it was converted
                cleanup_file(file)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        # Attempt to clean up ZIP file if it exists
        try:
            cleanup_file(archive_path)
        except Exception:
            pass  # Ignore cleanup errors in error handler

if __name__ == "__main__":
    main() 