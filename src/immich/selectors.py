"""
Asset selection strategies for Immich.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging
from datetime import datetime
from .immich_api import ImmichSession, ImmichAPI
import random

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
    
    def __init__(self, 
                 session: ImmichSession, 
                 base_url: str, 
                 city: Optional[str] = None, 
                 person_ids: Optional[List[str]] = None,
                 taken_after: Optional[datetime] = None,
                 taken_before: Optional[datetime] = None):
        """
        Initialize the random asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            city: Optional city name to filter assets by location
            person_ids: Optional list of person GUIDs to filter assets by people
            taken_after: Optional datetime to filter assets taken after this time
            taken_before: Optional datetime to filter assets taken before this time
        """
        self.api = ImmichAPI(session, base_url)
        self.city = city
        self.person_ids = person_ids
        self.taken_after = taken_after
        self.taken_before = taken_before
        
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
        logger.debug(f"Getting {count} assets")
        
        # Build request body with only non-None values
        request_body = {
            "size": count,
            "type": "IMAGE"
        }
        
        # Add date filtering if either date is specified
        if self.taken_after:
            request_body["takenAfter"] = self.taken_after.isoformat()
        if self.taken_before:
            request_body["takenBefore"] = self.taken_before.isoformat()
        
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

class SmartSearchAssetSelector(AssetSelector):
    """Selects assets using Immich's smart search functionality."""
    
    def __init__(self, 
                 session: ImmichSession, 
                 base_url: str,
                 search_query: str,
                 city: Optional[str] = None, 
                 person_ids: Optional[List[str]] = None,
                 taken_after: Optional[datetime] = None,
                 taken_before: Optional[datetime] = None):
        """
        Initialize the smart search asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            search_query: The search query to find relevant assets
            city: Optional city name to filter assets by location
            person_ids: Optional list of person GUIDs to filter assets by people
            taken_after: Optional datetime to filter assets taken after this time
            taken_before: Optional datetime to filter assets taken before this time
        """
        self.api = ImmichAPI(session, base_url)
        self.search_query = search_query
        self.city = city
        self.person_ids = person_ids
        self.taken_after = taken_after
        self.taken_before = taken_before
        
    def get_assets(self, count: int = 5) -> List[str]:
        """
        Get a specified number of assets using smart search from Immich.
        
        Args:
            count: Maximum number of assets to retrieve
            
        Returns:
            List of asset IDs
            
        Raises:
            requests.RequestException: If the API request fails
        """
        logger.debug(f'Getting up to {count} assets matching "{self.search_query}"')
        
        # Build request body with required fields
        request_body = {
            "query": self.search_query,
            "type": "IMAGE",
            "size": count
        }
        
        # Add optional filters if specified
        if self.taken_after:
            request_body["takenAfter"] = self.taken_after.isoformat()
        if self.taken_before:
            request_body["takenBefore"] = self.taken_before.isoformat()
        if self.person_ids:
            request_body["personIds"] = self.person_ids
        if self.city:
            request_body["city"] = self.city

        response = self.api.session.post(
            f"{self.api.base_url}/api/search/smart",
            json=request_body
        )
        response.raise_for_status()
        
        # Smart search returns a response with both albums and assets sections
        response_data = response.json()
        
        # Get asset IDs from the assets section
        assets_section = response_data.get("assets", {})
        asset_ids = [item["id"] for item in assets_section.get("items", [])]
        
        # Also check albums section for additional assets
        albums_section = response_data.get("albums", {})
        for album in albums_section.get("items", []):
            if "assets" in album:
                asset_ids.extend(asset["id"] for asset in album["assets"])
        
        logger.info(f'Successfully retrieved {len(asset_ids)} assets matching "{self.search_query}"')
        return asset_ids 

class RandomSmartSearchAssetSelector(AssetSelector):
    """Selects random assets from smart search results in Immich."""
    
    def __init__(self, 
                 session: ImmichSession, 
                 base_url: str,
                 search_query: str,
                 max_search_results: int = 250,
                 city: Optional[str] = None, 
                 person_ids: Optional[List[str]] = None,
                 taken_after: Optional[datetime] = None,
                 taken_before: Optional[datetime] = None):
        """
        Initialize the random smart search asset selector.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
            search_query: The search query to find relevant assets
            max_search_results: Maximum number of search results to fetch for randomization (1-1000)
            city: Optional city name to filter assets by location
            person_ids: Optional list of person GUIDs to filter assets by people
            taken_after: Optional datetime to filter assets taken after this time
            taken_before: Optional datetime to filter assets taken before this time
        """
        self.api = ImmichAPI(session, base_url)
        self.search_query = search_query
        self.max_search_results = max_search_results
        self.city = city
        self.person_ids = person_ids
        self.taken_after = taken_after
        self.taken_before = taken_before
        
    def get_assets(self, count: int = 5) -> List[str]:
        """
        Get a specified number of randomly selected assets from smart search results.
        
        Args:
            count: Number of random assets to select from search results
            
        Returns:
            List of asset IDs randomly selected from search results
            
        Raises:
            requests.RequestException: If the API request fails
        """
        logger.debug(f'Getting up to {self.max_search_results} assets matching "{self.search_query}" then randomly selecting {count}')
        
        # Build request body with configurable size limit
        request_body = {
            "query": self.search_query,
            "type": "IMAGE",
            "size": self.max_search_results
        }
        
        # Add optional filters if specified
        if self.taken_after:
            request_body["takenAfter"] = self.taken_after.isoformat()
        if self.taken_before:
            request_body["takenBefore"] = self.taken_before.isoformat()
        if self.person_ids:
            request_body["personIds"] = self.person_ids
        if self.city:
            request_body["city"] = self.city

        response = self.api.session.post(
            f"{self.api.base_url}/api/search/smart",
            json=request_body
        )
        response.raise_for_status()
        
        # Smart search returns a response with both albums and assets sections
        response_data = response.json()
        
        # Get asset IDs from the assets section
        assets_section = response_data.get("assets", {})
        asset_ids = [item["id"] for item in assets_section.get("items", [])]
        
        # Also check albums section for additional assets
        albums_section = response_data.get("albums", {})
        for album in albums_section.get("items", []):
            if "assets" in album:
                asset_ids.extend(asset["id"] for asset in album["assets"])
        
        # Remove duplicates while preserving order
        unique_asset_ids = list(dict.fromkeys(asset_ids))
        
        logger.info(f'Found {len(unique_asset_ids)} total assets matching "{self.search_query}"')
        
        # Randomly select the requested number of assets
        if len(unique_asset_ids) <= count:
            # If we have fewer or equal assets than requested, return all
            selected_asset_ids = unique_asset_ids
        else:
            # Randomly sample the requested count
            selected_asset_ids = random.sample(unique_asset_ids, count)
        
        logger.info(f'Randomly selected {len(selected_asset_ids)} assets from search results')
        return selected_asset_ids 