"""Core configuration for the LinkedIn Profile API."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings loaded from environment."""
    
    # LinkedIn Authentication (choose one method)
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")
    LI_AT_COOKIE: str = os.getenv("LI_AT", "")
    JSESSIONID: str = os.getenv("JSESSIONID", "")
    
    # Application settings
    APP_ENV: str = os.getenv("APP_ENV", "development")
    API_V1_STR: str = "/api/v1"
    PROXY_URL: str = os.getenv("PROXY_URL", "")
    
    # Scraping settings
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: float = 2.0
    REQUEST_TIMEOUT: int = 30000  # 30 seconds
    
    # Rate limiting
    MAX_PROFILES_PER_HOUR: int = 100


# Singleton instance
settings = Settings()