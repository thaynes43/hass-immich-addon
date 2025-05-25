"""
Configuration settings for the application.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional

# Clear existing environment variables that we manage
managed_vars = [
    "IMMICH_URL",
    "IMMICH_API_KEY",
    "HASS_IMG_PATH",
    "NUM_PHOTOS",
    "CITY_FILTER",
    "PEOPLE_FILTER",
    "DATE_FILTER"
]
for var in managed_vars:
    if var in os.environ:
        del os.environ[var]

# Load environment variables from .env file
load_dotenv()

def get_required_env(key: str) -> str:
    """Get a required environment variable or raise an exception."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Required environment variable '{key}' is not set. Please set it in your .env file.")
    return value

def get_int_env(key: str, default: int) -> int:
    """Get an integer environment variable with validation."""
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

def ensure_directory_exists(path: str) -> None:
    """
    Ensure the specified directory exists and is writable.
    Creates it if it doesn't exist.
    
    Args:
        path: Directory path to check/create
        
    Raises:
        OSError: If directory cannot be created or is not writable
    """
    directory = Path(path)
    try:
        # Create directory and any parent directories if they don't exist
        directory.mkdir(parents=True, exist_ok=True)
        
        # Test if directory is writable by trying to create a temporary file
        test_file = directory / '.write_test'
        try:
            test_file.touch()
            test_file.unlink()  # Clean up test file
        except OSError as e:
            raise OSError(f"Directory '{path}' is not writable: {e}")
            
        print(f"Successfully validated directory: {path}")
        
    except OSError as e:
        raise OSError(f"Failed to create or access directory '{path}': {e}")

# Immich settings
IMMICH_URL = get_required_env("IMMICH_URL")
IMMICH_API_KEY = get_required_env("IMMICH_API_KEY")

# Home Assistant settings
HASS_IMG_PATH = os.getenv("HASS_IMG_PATH", "/config/www/immich-photos")  # Default path in Home Assistant

# Application settings
NUM_PHOTOS = get_int_env("NUM_PHOTOS", 15)  # Default to 15 photos if not specified

# Optional filters
CITY_FILTER = os.getenv("CITY_FILTER")
PEOPLE_FILTER = os.getenv("PEOPLE_FILTER", "")
DATE_FILTER = os.getenv("DATE_FILTER", "").lower() == "true"  # Default to False if not set TODO refactor this into a start and end date filter

# Ensure the image directory exists and is writable
ensure_directory_exists(HASS_IMG_PATH)

# Log all environment variables
print("\nEnvironment Variables:")
print(f"IMMICH_URL: {IMMICH_URL}")
print(f"IMMICH_API_KEY: {'*' * len(IMMICH_API_KEY)}")  # Mask API key for security
print(f"HASS_IMG_PATH: {HASS_IMG_PATH}")
print(f"NUM_PHOTOS: {NUM_PHOTOS}")
print(f"CITY_FILTER: {CITY_FILTER}")
print(f"PEOPLE_FILTER: {PEOPLE_FILTER}")
print(f"DATE_FILTER: {DATE_FILTER}")

def get_people_list() -> Optional[List[str]]:
    """
    Get list of people names from environment variable.
    
    Returns:
        List of people names if PEOPLE_FILTER is set, None otherwise
    """
    if not PEOPLE_FILTER:
        return None
    
    # Split by comma and strip whitespace from each name
    return [name.strip() for name in PEOPLE_FILTER.split(",") if name.strip()]