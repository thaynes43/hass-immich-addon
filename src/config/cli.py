"""
Command line argument handling.
"""
import argparse
from pathlib import Path
from datetime import datetime
from typing import Literal
from .env import get_config_path

def parse_datetime(value: str) -> datetime:
    """Parse datetime from ISO format string."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid datetime format. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), got: {value}"
        ) from e

def parse_selector_type(value: str) -> Literal["random", "smart", "smart-rng"]:
    """Parse and validate selector type."""
    if value not in ["random", "smart", "smart-rng"]:
        raise argparse.ArgumentTypeError(
            f"Invalid selector type. Must be one of: random, smart, smart-rng. Got: {value}"
        )
    return value

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Home Assistant Immich Photo Addon",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=get_config_path(),
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override the logging level"
    )
    
    parser.add_argument(
        "--immich-url",
        help="Override the Immich server URL"
    )
    
    parser.add_argument(
        "--immich-api-key",
        help="Override the Immich API key"
    )

    parser.add_argument(
        "--taken-after",
        type=parse_datetime,
        help="Override the taken after date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    )

    parser.add_argument(
        "--taken-before",
        type=parse_datetime,
        help="Override the taken before date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    )

    parser.add_argument(
        "--selector-type",
        type=parse_selector_type,
        choices=["random", "smart", "smart-rng"],
        help="Override the selector type (random, smart, or smart-rng)"
    )

    parser.add_argument(
        "--search-query",
        help="Override the search query (required when selector-type is smart)"
    )
    
    return parser.parse_args() 