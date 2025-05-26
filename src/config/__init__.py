"""
Configuration management for the application.
"""
from pathlib import Path
from typing import Optional

from .schema import AppConfig, ImmichConfig, PhotoFilters
from .defaults import *
from .env import load_env_config
from .yaml_config import load_yaml_config, save_yaml_config
from .cli import parse_args

def load_config() -> AppConfig:
    """
    Load configuration from all sources in priority order:
    1. Command line arguments (highest priority)
    2. Environment variables
    3. YAML config file
    4. Default values (lowest priority)
    """
    # Parse command line arguments
    args = parse_args()
    
    # Load base configuration from environment
    config = load_env_config()
    
    # Try to load and merge YAML configuration
    yaml_config = load_yaml_config(args.config)
    if yaml_config:
        # Update non-None values from YAML config
        if yaml_config.immich.url:
            config.immich.url = yaml_config.immich.url
        if yaml_config.immich.api_key:
            config.immich.api_key = yaml_config.immich.api_key
        if yaml_config.hass_img_path:
            config.hass_img_path = yaml_config.hass_img_path
        if yaml_config.num_photos:
            config.num_photos = yaml_config.num_photos
        if yaml_config.update_interval_minutes:
            config.update_interval_minutes = yaml_config.update_interval_minutes
        if yaml_config.log_level:
            config.log_level = yaml_config.log_level
        if yaml_config.filters:
            config.filters = yaml_config.filters
    
    # Override with command line arguments
    if args.log_level:
        config.log_level = args.log_level
    if args.immich_url:
        config.immich.url = args.immich_url
    if args.immich_api_key:
        config.immich.api_key = args.immich_api_key
    
    # Validate final configuration
    config.validate()
    
    return config 