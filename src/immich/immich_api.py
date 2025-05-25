"""
Common utilities for interacting with the Immich API.
"""
from typing import Dict, Protocol
import logging

logger = logging.getLogger(__name__)

class ImmichSession(Protocol):
    """Protocol defining the required Immich session interface."""
    def post(self, url: str, json: dict) -> any:
        """Make a POST request to Immich API."""
        ...
        
    def get(self, url: str) -> any:
        """Make a GET request to Immich API."""
        ...

class ImmichAPI:
    """Utility class for common Immich API operations."""
    
    def __init__(self, session: ImmichSession, base_url: str):
        """
        Initialize the Immich API utility.
        
        Args:
            session: Session object for making API requests
            base_url: Base URL of the Immich server
        """
        self.session = session
        self.base_url = base_url.rstrip('/')
        
    def get_people(self) -> Dict[str, str]:
        """
        Get all people from Immich and their IDs.
        
        Returns:
            Dictionary mapping person names to their IDs
        
        Raises:
            requests.RequestException: If the API request fails
        """
        response = self.session.get(f"{self.base_url}/api/people")
        response.raise_for_status()
        
        people = response.json()
        people_dict = {person["name"]: person["id"] for person in people["people"]}

        # Info level - high level summary
        logger.info(f"Retrieved {len(people_dict)} people from Immich")
             
        # Debug level - detailed information about each person
        #for name, id in people_dict.items():
        #    logger.debug(f"Found person: {name} (ID: {id})")
        
        return people_dict 