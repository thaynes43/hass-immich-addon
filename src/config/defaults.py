"""
Default configuration values.
"""
from pathlib import Path

# Default configuration file path
DEFAULT_CONFIG_PATH = Path("settings.yaml")

# Immich defaults
IMMICH_URL = None
IMMICH_API_KEY = None

# Photo filter defaults
CITY_FILTER = None
PEOPLE_FILTER = None

# Application defaults
HASS_IMG_PATH = Path("/config/www/immich")
NUM_PHOTOS = 10
UPDATE_INTERVAL_MINUTES = 60
LOG_LEVEL = "INFO" 