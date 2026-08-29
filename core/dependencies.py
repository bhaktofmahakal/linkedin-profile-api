"""FastAPI dependencies for the LinkedIn Profile API."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional, Generator

from .config import Settings, settings


# Bearer token security (optional for future auth)
security = HTTPBearer(auto_error=False)


def get_settings() -> Settings:
    """Dependency to get application settings."""
    return settings


def validate_profile_url(url: str) -> str:
    """Validate that the URL is a LinkedIn profile URL."""
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile URL is required"
        )
    
    if "linkedin.com/in/" not in url and "linkedin.com/pub/" not in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LinkedIn profile URL. Must contain /in/ or /pub/ path"
        )
    
    return url


def get_public_profile_url(url: str = ...) -> str:
    """Extract and validate the profile URL from query parameters."""
    if url is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameter: 'url'"
        )
    return url