"""
Configuration settings for the application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Immich settings
IMMICH_URL = os.getenv("IMMICH_URL", "https://localhost:3001")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")

