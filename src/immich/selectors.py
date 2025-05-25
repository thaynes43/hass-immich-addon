"""
Asset selection strategies for Immich.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging
import time
from datetime import datetime, timedelta
import random
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
    
    def __init__(self, session: ImmichSession, base_url: str, city: Optional[str] = None, person_ids: Optional[List[str]] = None, use_date_filter: bool = False):
        """
        Initialize the random asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            city: Optional city name to filter assets by location
            person_ids: Optional list of person GUIDs to filter assets by people
            use_date_filter: Whether to apply date-based filtering
        """
        self.api = ImmichAPI(session, base_url)
        self.city = city
        self.person_ids = person_ids
        self.use_date_filter = use_date_filter
        
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
        
        # Build request body with only non-None values
        request_body = {
            "size": count,
            "type": "IMAGE"
        }
        
        # Add date filtering if enabled
        if self.use_date_filter:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            random_days = random.randint(0, 365)
            random_date = start_date + timedelta(days=random_days)
            
            request_body.update({
                "takenAfter": random_date.isoformat(),
                "takenBefore": end_date.isoformat()
            })
        
        # Only add filters if they are specified
        if self.person_ids:
            request_body["personIds"] = self.person_ids
            
        if self.city:
            request_body["city"] = self.city

        response = self.api.session.post(
            f"{self.api.base_url}/api/search/random",
            json=request_body
        )
        response.raise_for_status()
        
        asset_ids = [item["id"] for item in response.json()]
        logger.info(f"Successfully retrieved {len(asset_ids)} random asset IDs")
        return asset_ids 