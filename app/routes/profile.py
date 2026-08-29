"""Profile scraping route for LinkedIn Profile API - Voyager API direct calls."""

from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional

from core.dependencies import validate_profile_url, get_settings, get_public_profile_url
from models.response_schemas import LinkedInProfileResponse
from ..services.scraper import LinkedInVoyagerClient

router = APIRouter(prefix="/api/v1", tags=["profile"])


@router.get(
    "/profile",
    response_model=LinkedInProfileResponse,
    summary="Scrape a LinkedIn profile via Voyager API (browserless)",
    description="Accepts a LinkedIn profile URL and returns structured JSON data using direct REST API requests to LinkedIn's Voyager endpoints. "
                "No browser required - uses session cookie authentication.",
)
async def scrape_profile(
    url: str = Query(
        ...,
        description="LinkedIn profile URL to scrape (e.g., https://www.linkedin.com/in/username)",
        examples=["https://www.linkedin.com/in/satyanadella"],
    ),
    settings: "Settings" = Depends(get_settings),
) -> LinkedInProfileResponse:
    """
    Scrape a LinkedIn profile using direct Voyager API calls.
    
    This endpoint uses pure HTTP REST requests to LinkedIn's internal Voyager API,
    eliminating the need for a headless browser. Authentication is handled via
    the LI_AT session cookie stored in the backend .env file.
    
    If LinkedIn's anti-bot systems block the cloud IP, the API gracefully returns
    a structured fallback profile JSON instead of crashing with a 500 error.
    
    Args:
        url: LinkedIn profile URL to scrape
        settings: Application settings (injected via dependency)
    
    Returns:
        LinkedInProfileResponse with all available profile data
        
    Raises:
        400: Invalid URL format
        401: Invalid LinkedIn credentials (missing or expired LI_AT cookie)
        422: Validation error (missing URL parameter)
        500: API request failure (unexpected error)
    """
    from urllib.parse import urlparse
    
    # Validate the URL
    validated_url = validate_profile_url(url)
    
    # Extract clean profile URL (remove tracking params)
    parsed = urlparse(validated_url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # Use the Voyager API client to scrape the profile
    async with LinkedInVoyagerClient() as scraper:
        try:
            result = await scraper.scrape_profile(clean_url)
            return result
        except HTTPException as e:
            # Re-raise HTTPException from the scraper (401 invalid credentials, 404 profile not found,
            # or other API errors). The LinkedIn IP block fallback is handled internally in
            # scrape_profile() which returns a fallback response normally.
            raise
        except Exception as e:
            logger.error(f"Profile scraping failed for {validated_url}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to scrape profile. "
                        f"The LinkedIn profile may have restricted visibility, "
                        f"the session cookie may be expired, or LinkedIn's API structure changed."
            )