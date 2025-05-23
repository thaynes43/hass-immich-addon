"""
Asset selection strategies for Immich.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging
from .immich_api import ImmichSession, ImmichAPI

logger = logging.getLogger(__name__)

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
    
    def __init__(self, session: ImmichSession, base_url: str, city: Optional[str] = None, person_ids: Optional[List[str]] = None):
        """
        Initialize the random asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            city: Optional city name to filter assets by location
            person_ids: Optional list of person GUIDs to filter assets by people
        """
        self.api = ImmichAPI(session, base_url)
        self.city = city
        self.person_ids = person_ids
        
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
        print(f"POST url: {self.api.base_url}/api/search/random")

        request_body = {
            "size": count,
            "type": "IMAGE",
            "withPeople": bool(self.person_ids)  # Only set True if we're filtering by people
        }
        
        if self.city:
            request_body["city"] = self.city
            
        if self.person_ids:
            request_body["personIds"] = self.person_ids

        response = self.api.session.post(
            f"{self.api.base_url}/api/search/random",
            json=request_body
        )
        response.raise_for_status()
        
        asset_ids = [item["id"] for item in response.json()]
        logger.info(f"Successfully retrieved {len(asset_ids)} random asset IDs")
        return asset_ids 