"""
YAML configuration file handling.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import yaml

from .defaults import *
from .schema import ImmichConfig, PhotoFilters, AppConfig
from .env import parse_datetime

def load_yaml_config(config_path: Path) -> AppConfig:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return None
        
    with open(config_path) as f:
        yaml_config = yaml.safe_load(f)
    
    if not yaml_config:
        return None
        
    # Extract Immich configuration
    immich_section = yaml_config.get('immich', {})
    immich_config = ImmichConfig(
        url=immich_section.get('url', IMMICH_URL),
        api_key=immich_section.get('api_key', IMMICH_API_KEY)
    )
    
    # Extract filter configurations
    filters: List[PhotoFilters] = []
    filters_section = yaml_config.get('filters', [])
    
    # Helper function to parse dates from YAML
    def parse_yaml_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            if isinstance(date_str, datetime):
                return date_str
            return parse_datetime(date_str)
        except ValueError as e:
            raise ValueError(f"Invalid date format in YAML: {e}")
    
    # Handle both single filter (old format) and multiple filters (new format)
    if isinstance(filters_section, dict):
        # Single filter set (legacy format)
        filters.append(PhotoFilters(
            name="default",
            selector_type=filters_section.get('selector_type', 'random'),
            search_query=filters_section.get('search_query'),
            city=filters_section.get('city', CITY_FILTER),
            people=filters_section.get('people', PEOPLE_FILTER),
            taken_after=parse_yaml_date(filters_section.get('taken_after')),
            taken_before=parse_yaml_date(filters_section.get('taken_before'))
        ))
    elif isinstance(filters_section, list):
        # Multiple filter sets
        for idx, filter_config in enumerate(filters_section):
            if not isinstance(filter_config, dict):
                continue
            
            name = filter_config.get('name', f"filter-{idx+1}")
            filters.append(PhotoFilters(
                name=name,
                selector_type=filter_config.get('selector_type', 'random'),
                search_query=filter_config.get('search_query'),
                city=filter_config.get('city'),
                people=filter_config.get('people', []),
                taken_after=parse_yaml_date(filter_config.get('taken_after')),
                taken_before=parse_yaml_date(filter_config.get('taken_before'))
            ))
    
    # If no filters were configured, add a default one
    if not filters:
        filters.append(PhotoFilters(
            name="default",
            city=CITY_FILTER,
            people=PEOPLE_FILTER,
            taken_after=None,
            taken_before=None
        ))
    
    # Create full configuration
    config = AppConfig(
        immich=immich_config,
        hass_img_path=Path(yaml_config.get('hass_img_path', HASS_IMG_PATH)),
        num_photos=yaml_config.get('num_photos', NUM_PHOTOS),
        update_interval_minutes=yaml_config.get('update_interval_minutes', UPDATE_INTERVAL_MINUTES),
        log_level=yaml_config.get('log_level', LOG_LEVEL),
        filters=filters
    )
    
    return config

def save_yaml_config(config: AppConfig, config_path: Path) -> None:
    """Save configuration to YAML file."""
    yaml_config = {
        'immich': {
            'url': config.immich.url,
            'api_key': config.immich.api_key
        },
        'hass_img_path': str(config.hass_img_path),
        'num_photos': config.num_photos,
        'update_interval_minutes': config.update_interval_minutes,
        'log_level': config.log_level,
        'filters': [
            {
                'name': f.name,
                'selector_type': f.selector_type,
                'search_query': f.search_query,
                'city': f.city,
                'people': f.people,
                'taken_after': f.taken_after,
                'taken_before': f.taken_before
            }
            for f in config.filters
        ]
    }
    
    with open(config_path, 'w') as f:
        yaml.safe_dump(yaml_config, f, default_flow_style=False) 