"""
Immich API client for interacting with Immich photo server.
"""
import logging
import os
from dataclasses import dataclass
from typing import List, Optional
import requests
from .selectors import AssetSelector

logger = logging.getLogger(__name__)

@dataclass
class ImmichConfig:
    """Configuration for Immich client."""
    url: str
    api_key: str
    
    def __post_init__(self):
        """Ensure URL doesn't end with a slash."""
        self.url = self.url.rstrip('/')

@dataclass
class Asset:
    """Represents an Immich asset (photo)."""
    id: str
    filename: str
    thumbnail_url: str

    def save_to_directory(self, directory: str, client: 'ImmichClient') -> str:
        """
        Save the asset to the specified directory.
        
        Args:
            directory: Directory path where the asset should be saved
            client: ImmichClient instance to use for downloading
            
        Returns:
            Path to the saved file
            
        Raises:
            OSError: If file cannot be written
            requests.RequestException: If download fails
        """
        # Ensure filename is safe and unique
        safe_filename = os.path.basename(self.filename)
        file_path = os.path.join(directory, safe_filename)
        
        # Download and save the asset
        data = client.download_assets([self.id])
        
        with open(file_path, 'wb') as f:
            f.write(data)
            
        logger.info(f"Saved asset {self.id} to {file_path}")
        return file_path

class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, config: ImmichConfig, asset_selector: AssetSelector):
        """
        Initialize the client with configuration and asset selector.
        
        Args:
            config: ImmichConfig instance with connection details
            asset_selector: Strategy for selecting assets from Immich
        """
        self.config = config
        self.asset_selector = asset_selector
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": config.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def get_assets(self, count: int = 5) -> List[str]:
        """
        Get asset IDs using the configured selector strategy.
        
        Args:
            count: Number of assets to retrieve
            
        Returns:
            List of asset IDs
            
        Raises:
            requests.RequestException: If the API request fails
        """
        return self.asset_selector.get_assets(count)

    def download_assets(self, asset_ids: List[str]) -> bytes:
        """
        Download assets by their IDs.
        
        Args:
            asset_ids: List of asset IDs to download
            
        Returns:
            Binary data containing the downloaded assets
            
        Raises:
            requests.RequestException: If the download fails
        """
        try:
            # Create a new session with modified headers for binary download
            download_session = requests.Session()
            download_session.headers.update({
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/octet-stream"
            })
            
            response = download_session.post(
                f"{self.config.url}/api/download/archive",
                json={"assetIds": asset_ids}
            )
            response.raise_for_status()
            
            logger.info(f"Successfully downloaded {len(asset_ids)} assets")
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"Failed to download assets: {e}")
            raise 