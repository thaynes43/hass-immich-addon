"""
Immich API client for interacting with Immich photo server.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
import requests

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

class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, config: ImmichConfig):
        """Initialize the client with configuration."""
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Accept": "application/json"
        })
        
    def get_random_assets(self, count: int = 5) -> List[Asset]:
        """
        Get a specified number of random assets from Immich.
        
        Args:
            count: Number of random assets to retrieve
            
        Returns:
            List of Asset objects containing photo information
            
        Raises:
            requests.RequestException: If the API request fails
        """
        print("IMMICH URL:")
        print(f"{self.config.url}/api/search/random")

        try:
            response = self.session.post(
                f"{self.config.url}/api/search/random",
                json={"count": count}
            )
            response.raise_for_status()
            
            assets = []
            for item in response.json():
                asset = Asset(
                    id=item["id"],
                    filename=item["originalFileName"],
                    thumbnail_url=f"{self.config.url}/api/asset/thumbnail/{item['id']}"
                )
                assets.append(asset)
                
            logger.info(f"Successfully retrieved {len(assets)} random assets")
            return assets
            
        except requests.RequestException as e:
            logger.error(f"Failed to get random assets: {e}")
            raise 