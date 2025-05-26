"""
Main application entry point.
"""
import logging
import os
import sys
import asyncio
from pathlib import Path

# Add the parent directory to Python path for local development
if os.path.basename(os.getcwd()) == 'src':
    sys.path.append(os.path.dirname(os.getcwd()))
else:
    sys.path.append(os.getcwd())

from config import load_config
from photo_updater import PhotoUpdater

async def main():
    """Main entry point for the application."""
    # Load configuration
    config = load_config()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting hass-immich-addon...")
    
    # Create and run the photo updater
    updater = PhotoUpdater(config)
    await updater.run()

if __name__ == "__main__":
    asyncio.run(main()) 