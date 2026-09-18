"""
Common utilities for interacting with the Immich API.
"""
from datetime import date, datetime, timezone
from typing import Dict, Optional, Protocol, Union
import logging

logger = logging.getLogger(__name__)

# Immich >= 3.2 validates date filters strictly: the value must carry a UTC
# designator ("Z") or a numeric offset ("+HH:MM"). A naive ISO timestamp such as
# "2023-01-01T00:00:00" is rejected with
# 400 {"message": "Validation failed", "errors": [{"code": "invalid_format", ...}]}.
# Every datetime that goes on the wire must therefore pass through
# to_immich_datetime().


def to_immich_datetime(value: Union[datetime, date, str]) -> str:
    """
    Serialize a date/datetime into the timezone-qualified form Immich requires.

    A naive datetime (and a plain date) is interpreted as UTC and rendered with a
    "Z" suffix, e.g. "2023-01-01T00:00:00.000Z". A timezone-aware datetime keeps
    its own offset, e.g. "2023-01-01T00:00:00.000-05:00" (UTC-aware values are
    still rendered with "Z"). Strings are parsed first so that a value that never
    went through the config parsers is normalized the same way.

    Args:
        value: datetime, date or ISO-8601 string to serialize

    Returns:
        ISO-8601 timestamp string with millisecond precision and a timezone

    Raises:
        TypeError: If value is not a datetime, date or string
        ValueError: If value is a string that is not valid ISO-8601
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as e:
            raise ValueError(
                f"Invalid datetime for Immich request. Expected ISO format, got: {value}"
            ) from e

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        # datetime is a subclass of date, so this branch is plain dates only
        # (PyYAML turns an unquoted `taken_after: 2023-01-01` into a date).
        dt = datetime.combine(value, datetime.min.time())
    else:
        raise TypeError(
            f"Expected a datetime, date or ISO string for an Immich date filter, got: {type(value).__name__}"
        )

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # Timezone-less configuration values are treated as UTC.
        dt = dt.replace(tzinfo=timezone.utc)

    formatted = dt.isoformat(timespec="milliseconds")
    if formatted.endswith("+00:00"):
        formatted = formatted[: -len("+00:00")] + "Z"
    return formatted


def apply_date_filters(
    request_body: dict,
    taken_after: Optional[Union[datetime, date, str]] = None,
    taken_before: Optional[Union[datetime, date, str]] = None,
) -> dict:
    """
    Add takenAfter/takenBefore filters to an Immich search request body.

    This is the single serialization choke point for datetimes that go on the
    wire; every selector must use it instead of calling isoformat() itself.

    Args:
        request_body: The request body to add the filters to (mutated in place)
        taken_after: Optional lower bound for the asset's taken-at timestamp
        taken_before: Optional upper bound for the asset's taken-at timestamp

    Returns:
        The same request body, for convenience
    """
    if taken_after:
        request_body["takenAfter"] = to_immich_datetime(taken_after)
    if taken_before:
        request_body["takenBefore"] = to_immich_datetime(taken_before)
    return request_body

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