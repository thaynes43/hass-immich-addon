"""
Asset selection strategies for Immich.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
import logging

logger = logging.getLogger(__name__)

class ImmichSession(Protocol):
    """Protocol defining the required Immich session interface."""
    def post(self, url: str, json: dict) -> any:
        """Make a POST request to Immich API."""
        ...

class AssetSelector(ABC):
    """Abstract base class for asset selection strategies."""
    
    @abstractmethod
    def get_assets(self, count: int = 5) -> List[str]:
        """
        Get a list of asset IDs using the implemented strategy.
        
        Args:
            count: Number of assets to retrieve
            
        Returns:
            List of asset IDs
            
        Raises:
            requests.RequestException: If the API request fails
        """
        pass

class RandomAssetSelector(AssetSelector):
    """Selects random assets from Immich."""
    
    def __init__(self, session: ImmichSession, base_url: str, city: Optional[str] = None):
        """
        Initialize the random asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            city: Optional city name to filter assets by location
        """
        self.session = session
        self.base_url = base_url.rstrip('/')
        self.city = city
        
    def get_assets(self, count: int = 5) -> List[str]:
        """
        Get a specified number of random asset IDs from Immich.
        
        Args:
            count: Number of random assets to retrieve
            
        Returns:
            List of asset IDs
            
        Raises:
            requests.RequestException: If the API request fails
        """
        print(f"POST url: {self.base_url}/api/search/random")

        request_body = {
            "size": count,
            "type": "IMAGE"
        }
        
        if self.city:
            request_body["city"] = self.city

        response = self.session.post(
            f"{self.base_url}/api/search/random",
            json=request_body
        )
        response.raise_for_status()
        
        asset_ids = [item["id"] for item in response.json()]
        logger.info(f"Successfully retrieved {len(asset_ids)} random asset IDs")
        return asset_ids 