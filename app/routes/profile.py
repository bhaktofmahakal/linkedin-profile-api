"""Profile scraping route for LinkedIn Profile API."""

from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional

from core.dependencies import validate_profile_url, get_settings, get_public_profile_url
from models.response_schemas import LinkedInProfileResponse

router = APIRouter(prefix="/api/v1", tags=["profile"])


@router.get(
    "/profile",
    response_model=LinkedInProfileResponse,
    summary="Scrape a LinkedIn profile and return structured data",
    description="Accepts a LinkedIn profile URL and returns structured JSON data including name, headline, location, about, experience, education, skills, certifications, languages, and profile images.",
)
async def scrape_profile(
    url: str = Query(
        ...,
        description="LinkedIn profile URL to scrape (e.g., https://www.linkedin.com/in/username)",
        example="https://www.linkedin.com/in/john-doe",
    ),
    settings: "Settings" = Depends(get_settings),
) -> LinkedInProfileResponse:
    """
    Scrape a LinkedIn profile and return structured data.
    
    The endpoint accepts a LinkedIn profile URL and returns comprehensive profile data
    including personal information, work experience, education, skills, certifications,
    languages, and profile images.
    
    Args:
        url: LinkedIn profile URL to scrape
        settings: Application settings (injected via dependency)
    
    Returns:
        LinkedInProfileResponse with all available profile data
        
    Raises:
        400: Invalid URL format
        401: Authentication failed (invalid credentials)
        500: Scraping failure
    """
    # Validate the URL
    validated_url = validate_profile_url(url)
    
    # Extract the public profile URL (remove tracking parameters)
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(validated_url)
    # Remove tracking params, keep only the path
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # TODO: Import and call the scraper service
    # from services.scraper import scrape_linkedin_profile
    # result = await scrape_linkedin_profile(clean_url, settings)
    # 
    # For now, return a placeholder response
    # In production, this will be the actual scraped data
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Profile scraper service not yet implemented. "
                "See README for development roadmap."
    )