"""
Main application entry point.
"""
import logging
from config import IMMICH_URL, IMMICH_API_KEY, NUM_PHOTOS
from immich.client import ImmichClient, ImmichConfig

# Configure logging
logging.basicConfig(level=logging.INFO)

def main():
    # Create Immich client
    config = ImmichConfig(
        url=IMMICH_URL,
        api_key=IMMICH_API_KEY
    )
    client = ImmichClient(config)
    
    try:
        # Get random assets using configured number of photos
        assets = client.get_random_assets(count=NUM_PHOTOS)
        
        # Print asset information
        for asset in assets:
            print(f"Asset ID: {asset.id}")
            print(f"Filename: {asset.filename}")
            print(f"Thumbnail URL: {asset.thumbnail_url}")
            print("---")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 