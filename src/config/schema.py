"""
Configuration schema and validation.
"""
from dataclasses import dataclass
from typing import Optional, List, Sequence, Literal
from pathlib import Path
import logging
from datetime import datetime

@dataclass
class ImmichConfig:
    """Immich-specific configuration."""
    url: Optional[str] = None
    api_key: Optional[str] = None
    
    def validate(self) -> None:
        """Validate Immich configuration."""
        if not self.url:
            raise ValueError("Immich URL is required but was not provided in any configuration source")
        if not self.api_key:
            raise ValueError("Immich API key is required but was not provided in any configuration source")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("Immich URL must start with http:// or https://")

@dataclass
class PhotoFilters:
    """Configuration for photo filtering."""
    name: str
    selector_type: Literal["random", "smart", "smart-rng"] = "random"
    search_query: Optional[str] = None
    max_search_results: Optional[int] = None
    city: Optional[str] = None
    people: Optional[List[str]] = None
    taken_after: Optional[datetime] = None
    taken_before: Optional[datetime] = None

    def validate(self) -> None:
        """Validate filter configuration."""
        if self.selector_type not in ["random", "smart", "smart-rng"]:
            raise ValueError(f"Invalid selector type: {self.selector_type}")
        if self.selector_type in ["smart", "smart-rng"] and not self.search_query:
            raise ValueError("search_query is required when using smart or smart-rng selector")
        if self.selector_type == "random" and self.search_query:
            raise ValueError("search_query should not be set when using random selector")
        if self.max_search_results is not None:
            if self.selector_type != "smart-rng":
                raise ValueError("max_search_results can only be set when using smart-rng selector")
            if self.max_search_results <= 0 or self.max_search_results > 1000:
                raise ValueError("max_search_results must be between 1 and 1000 (Immich limit)")

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        parts = [f"Filter set '{self.name}' using {self.selector_type} selector"]
        if self.search_query:
            parts.append(f'searching for "{self.search_query}"')
        if self.city:
            parts.append(f"in {self.city}")
        if self.people:
            parts.append(f"with people {', '.join(self.people)}")
        if self.taken_after or self.taken_before:
            date_parts = []
            if self.taken_after:
                date_parts.append(f"after {self.taken_after.isoformat()}")
            if self.taken_before:
                date_parts.append(f"before {self.taken_before.isoformat()}")
            parts.append(" and ".join(date_parts))
        return " ".join(parts)

@dataclass
class AppConfig:
    """Application configuration."""
    immich: ImmichConfig
    hass_img_path: Path
    num_photos: int
    update_interval_minutes: int
    log_level: str
    filters: Sequence[PhotoFilters]  # Now a sequence of filter sets

    def validate(self) -> None:
        """
        Validate the configuration after all sources have been loaded.
        Raises ValueError if any required fields are missing or invalid.
        """
        # Validate Immich configuration
        self.immich.validate()
        
        # Validate log level
        if self.log_level.upper() not in logging._nameToLevel:
            raise ValueError(f"Invalid log level: {self.log_level}")
        
        # Validate numeric values
        if self.num_photos <= 0:
            raise ValueError("num_photos must be positive")
        if self.update_interval_minutes <= 0:
            raise ValueError("update_interval_minutes must be positive")
            
        # Validate paths
        if not self.hass_img_path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {self.hass_img_path.parent}")
            
        # Create image directory if it doesn't exist
        self.hass_img_path.mkdir(parents=True, exist_ok=True)
        
        # Validate filters
        if not self.filters:
            raise ValueError("At least one filter set must be configured")
        
        # Validate filter names are unique
        filter_names = [f.name for f in self.filters]
        if len(filter_names) != len(set(filter_names)):
            raise ValueError("Filter set names must be unique")
            
        # Validate each filter's configuration
        for f in self.filters:
            f.validate() 