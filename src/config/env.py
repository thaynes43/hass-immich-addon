"""
Environment variable configuration handling.
"""
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

from .defaults import *
from .schema import ImmichConfig, PhotoFilters, AppConfig

def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime from ISO format string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid datetime format. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), got: {value}") from e

def load_env_config() -> AppConfig:
    """Load configuration from environment variables."""
    # Load .env file if it exists
    env_file = Path('.env')
    if env_file.exists():
        load_dotenv(env_file)
    
    # Helper function to get integer env vars
    def get_int_env(key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            int_value = int(value)
            if int_value <= 0:
                raise ValueError(f"Environment variable '{key}' must be a positive integer")
            return int_value
        except ValueError:
            raise ValueError(f"Environment variable '{key}' must be a valid positive integer, got '{value}'")
    
    # Helper function to get list from comma-separated string
    def get_list_env(key: str) -> Optional[List[str]]:
        value = os.getenv(key)
        if not value:
            return None
        return [item.strip() for item in value.split(",") if item.strip()]
    
    # Load Immich configuration
    immich_config = ImmichConfig(
        url=os.getenv("IMMICH_URL"),
        api_key=os.getenv("IMMICH_API_KEY")
    )
    
    # Create a single filter set from environment variables if any are set
    filters = []
    if any([
        os.getenv("CITY_FILTER"),
        os.getenv("PEOPLE_FILTER"),
        os.getenv("TAKEN_AFTER"),
        os.getenv("TAKEN_BEFORE"),
        os.getenv("SELECTOR_TYPE"),
        os.getenv("SEARCH_QUERY")
    ]):
        filters.append(PhotoFilters(
            name="Filter from Environment Variables",
            selector_type=os.getenv("SELECTOR_TYPE", "random"),
            search_query=os.getenv("SEARCH_QUERY"),
            city=os.getenv("CITY_FILTER", CITY_FILTER),
            people=get_list_env("PEOPLE_FILTER"),
            taken_after=parse_datetime(os.getenv("TAKEN_AFTER")),
            taken_before=parse_datetime(os.getenv("TAKEN_BEFORE"))
        ))
    else:
        # Add default filter if no environment variables are set
        filters.append(PhotoFilters(
            name="default",
            selector_type="random",
            search_query=None,
            city=CITY_FILTER,
            people=PEOPLE_FILTER,
            taken_after=None,
            taken_before=None
        ))
    
    # Create and return full configuration
    config = AppConfig(
        immich=immich_config,
        hass_img_path=Path(os.getenv("HASS_IMG_PATH", HASS_IMG_PATH)),
        num_photos=get_int_env("NUM_PHOTOS", NUM_PHOTOS),
        update_interval_minutes=get_int_env("UPDATE_INTERVAL_MINUTES", UPDATE_INTERVAL_MINUTES),
        log_level=os.getenv("LOG_LEVEL", LOG_LEVEL),
        filters=filters
    )
    
    return config 