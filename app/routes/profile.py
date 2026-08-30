import logging
from urllib.parse import urlparse
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Query, Header, Depends, HTTPException, status

from core.config import Settings
from core.dependencies import validate_profile_url, get_settings, get_public_profile_url
from models.response_schemas import LinkedInProfileResponse
from app.services.scraper import LinkedInVoyagerClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["profile"])


class SessionUpdateRequest(BaseModel):
    li_at: str = Field(..., description="LinkedIn li_at session cookie value")
    jsessionid: Optional[str] = Field(None, description="Optional LinkedIn JSESSIONID cookie value")


@router.post(
    "/auth/session",
    summary="Dynamically update active LinkedIn session cookie (Runtime)",
    description="Updates the active in-memory LinkedIn session cookie on the running server instantly without requiring a redeployment or dashboard access.",
)
async def update_session(
    payload: SessionUpdateRequest,
    settings: Settings = Depends(get_settings),
):
    settings.LI_AT_COOKIE = payload.li_at.strip()
    if payload.jsessionid:
        settings.JSESSIONID = payload.jsessionid.strip()
    return {
        "status": "success",
        "message": "LinkedIn session cookie updated successfully in runtime memory.",
        "li_at_prefix": payload.li_at[:15] + "...",
    }


@router.get(
    "/profile",
    response_model=LinkedInProfileResponse,
    summary="Scrape a LinkedIn profile via Voyager API (browserless)",
    description="Accepts a LinkedIn profile URL and returns structured JSON data using direct REST API requests to LinkedIn's Voyager endpoints. "
                "Requires 'X-LI-AT' session cookie header for authentication.",
)
async def scrape_profile(
    url: str = Query(
        ...,
        description="LinkedIn profile URL to scrape (e.g., https://www.linkedin.com/in/username)",
        examples=["https://www.linkedin.com/in/satyanadella"],
    ),
    x_li_at: str = Header(
        ...,
        alias="X-LI-AT",
        description="LinkedIn LI_AT session cookie (Required for authenticated Voyager API access)",
    ),
    x_jsessionid: Optional[str] = Header(
        None,
        alias="X-JSESSIONID",
        description="Optional dynamic LinkedIn JSESSIONID cookie",
    ),
    settings: Settings = Depends(get_settings),
) -> LinkedInProfileResponse:
    """
    Scrape a LinkedIn profile using direct live Voyager API calls.
    
    This endpoint uses pure HTTP REST requests to LinkedIn's internal Voyager API,
    eliminating the need for a headless browser. Authentication is handled via
    the LI_AT session cookie stored in backend configuration or passed via X-LI-AT header.
    
    Args:
        url: LinkedIn profile URL to scrape
        x_li_at: Optional dynamic LI_AT cookie for this request
        x_jsessionid: Optional dynamic JSESSIONID cookie
        settings: Application settings (injected via dependency)
    
    Returns:
        LinkedInProfileResponse with all available live profile data
        
    Raises:
        400: Invalid URL format
        401: Invalid LinkedIn credentials (missing or expired LI_AT cookie)
        403: LinkedIn anti-bot / IP block
        404: Profile not found
        422: Validation error (missing URL parameter)
        500: API request failure
    """
    # Validate the URL
    validated_url = validate_profile_url(url)
    
    # Extract clean profile URL (remove tracking params)
    parsed = urlparse(validated_url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # Use the Voyager API client to scrape the profile
    async with LinkedInVoyagerClient(li_at=x_li_at, jsessionid=x_jsessionid) as scraper:
        try:
            result = await scraper.scrape_profile(clean_url)
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Profile scraping failed for {validated_url}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to scrape profile: {str(e)}"
            )