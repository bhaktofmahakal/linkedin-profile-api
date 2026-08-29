"""Pure HTTP LinkedIn API client using linkedin-api library - No browser, no Playwright.

This module uses the `linkedin-api` Python library to make direct REST API calls
to LinkedIn's Voyager endpoints. Authentication is handled via backend LinkedIn
credentials (email/password) stored in the .env file.

All data extraction and mapping is handled by the library, and we parse the
returned JSON into our Pydantic response models.
"""

import logging
from typing import Optional, Dict, Any, List

from linkedin_api import Linkedin

from core.config import settings
from models.response_schemas import (
    LinkedInProfileResponse,
    Experience,
    Education,
    Certification,
    Language,
    ProfileImages,
)

logger = logging.getLogger(__name__)


# Initialize LinkedIn API client with backend credentials
# These are read from environment variables in .env
linkedin_api = Linkedin(
    username=settings.LINKEDIN_EMAIL or "",
    password=settings.LINKEDIN_PASSWORD or "",
)


def scrape_profile(profile_url: str) -> LinkedInProfileResponse:
    """Scrape a LinkedIn profile using the linkedin-api library.
    
    This function makes a direct HTTP REST call to LinkedIn's internal Voyager API
    via the linkedin-api library, extracting all required profile data without
    needing a headless browser or Playwright.
    
    Args:
        profile_url: LinkedIn profile URL (e.g., https://www.linkedin.com/in/username)
    
    Returns:
        LinkedInProfileResponse with all available profile data
        
    Raises:
        ValueError: If the profile URL is invalid or data cannot be retrieved
    """
    # Extract the public profile ID from the URL
    # e.g., "https://www.linkedin.com/in/username" -> "username"
    from urllib.parse import urlparse
    
    parsed = urlparse(profile_url.strip())
    path_parts = parsed.path.strip("/").split("/")
    public_id = path_parts[-1] if path_parts else ""
    
    if not public_id:
        raise ValueError(f"Could not extract profile ID from URL: {profile_url}")
    
    logger.info(f"Scraping profile via linkedin-api library: {public_id}")
    
    try:
        # Make the direct API call using the library
        # This internally hits LinkedIn's Voyager API endpoints
        profile_data = linkedin_api.get_profile(public_id)
        
        # Map the raw API response to our Pydantic response model
        return _map_to_response_model(profile_data)
        
    except Exception as e:
        logger.error(f"Failed to scrape profile {public_id}: {e}")
        raise ValueError(f"Failed to scrape LinkedIn profile: {e}")


def _map_to_response_model(profile_data: Dict[str, Any]) -> LinkedInProfileResponse:
    """Map the raw LinkedIn API response to our Pydantic response model."""
    
    # Extract basic personal information
    first_name = profile_data.get("firstName", "") or ""
    last_name = profile_data.get("lastName", "") or ""
    name = f"{first_name} {last_name}".strip() or "Unknown"
    
    headline = profile_data.get("headline", "") or ""
    location = profile_data.get("locationName") or profile_data.get("geographicLocation", {}).get("name") if isinstance(profile_data.get("geographicLocation"), dict) else None
    
    # About/summary section
    about = profile_data.get("summary") or profile_data.get("about") or ""
    if about and len(about) > 500:
        about = about[:500] + "..."
    
    # Parse experiences
    experiences = _parse_experiences(profile_data.get("experience", []))
    
    # Parse educations
    educations = _parse_educations(profile_data.get("education", []))
    
    # Parse skills
    skills = _parse_skills(profile_data.get("skills", []))
    
    # Parse certifications
    certifications = _parse_certifications(profile_data.get("certifications", []))
    
    # Parse languages
    languages = _parse_languages(profile_data.get("languages", []))
    
    # Profile images
    display_picture = profile_data.get("displayPictureUrl", "") or ""
    # Also try secondary image URLs
    background_picture = profile_data.get("backgroundPictureUrl", "") or ""
    
    return LinkedInProfileResponse(
        name=name,
        headline=headline or "",
        location=location,
        about=about or None,
        experiences=experiences,
        educations=educations,
        skills=skills,
        certifications=certifications,
        languages=languages,
        profile_images=ProfileImages(
            primary=display_picture,
            secondary=[background_picture] if background_picture else [],
        ),
    )


def _parse_experiences(experience_data: Any) -> List[Experience]:
    """Parse experience data from LinkedIn API response."""
    results = []
    
    if not experience_data:
        return results
    
    # Handle different response formats
    items = experience_data if isinstance(experience_data, list) else [experience_data]
    
    for item in items:
        try:
            if isinstance(item, dict):
                # Extract position title
                title = item.get("title") or item.get("positionTitle") or ""
                
                # Extract company
                company_info = item.get("company") or {}
                company_name = company_info.get("name") if isinstance(company_info, dict) else ""
                company_url = company_info.get("url", "") if isinstance(company_info, dict) else ""
                
                # Extract dates
                start_date = item.get("startDate") or ""
                end_date = item.get("endDate") or ""
                duration = item.get("duration") or ""
                
                # Extract location
                location_info = item.get("location") or {}
                location_name = location_info.get("name") if isinstance(location_info, dict) else ""
                
                # Extract description
                description = item.get("description") or ""
                
                if title or company_name:
                    results.append(Experience(
                        position_title=title.strip(),
                        company_name=company_name.strip() or "Company",
                        company_linkedin_url=company_url,
                        from_date=start_date,
                        to_date=end_date,
                        duration=duration,
                        location=location_name.strip() if location_name else None,
                        description=description.strip() if description else None,
                    ))
        except Exception as e:
            logger.debug(f"Error parsing experience item: {e}")
            continue
    
    return results


def _parse_educations(education_data: Any) -> List[Education]:
    """Parse education data from LinkedIn API response."""
    results = []
    
    if not education_data:
        return results
    
    items = education_data if isinstance(education_data, list) else [education_data]
    
    for item in items:
        try:
            if isinstance(item, dict):
                # Extract institution
                school_info = item.get("school") or item.get("institution") or {}
                institution_name = school_info.get("name") if isinstance(school_info, dict) else ""
                institution_url = school_info.get("url", "") if isinstance(school_info, dict) else ""
                
                # Extract degree
                degree = item.get("degreeName") or item.get("degree") or ""
                
                # Extract dates
                start_date = item.get("startDate") or ""
                end_date = item.get("endDate") or ""
                
                if institution_name:
                    results.append(Education(
                        institution_name=institution_name.strip(),
                        degree=degree.strip() if degree else None,
                        institution_linkedin_url=institution_url,
                        from_date=start_date,
                        to_date=end_date,
                    ))
        except Exception as e:
            logger.debug(f"Error parsing education item: {e}")
            continue
    
    return results


def _parse_skills(skills_data: Any) -> List[str]:
    """Parse skills list from LinkedIn API response."""
    skills = []
    
    if not skills_data:
        return skills
    
    items = skills_data if isinstance(skills_data, list) else [skills_data]
    
    for item in items:
        try:
            if isinstance(item, dict):
                skill_name = item.get("name") or item.get("skillName") or ""
                if skill_name:
                    skills.append(skill_name.strip())
        except Exception:
            continue
    
    # Deduplicate while preserving order
    seen = set()
    unique_skills = []
    for skill in skills:
        if skill not in seen:
            seen.add(skill)
            unique_skills.append(skill)
    
    return unique_skills


def _parse_certifications(certs_data: Any) -> List[Certification]:
    """Parse certifications from LinkedIn API response."""
    results = []
    
    if not certs_data:
        return results
    
    items = certs_data if isinstance(certs_data, list) else [certs_data]
    
    for item in items:
        try:
            if isinstance(item, dict):
                title = item.get("title") or item.get("credentialName") or ""
                issuer = item.get("issuer") or ""
                issued_date = item.get("issueDate") or item.get("issuedDate") or ""
                credential_id = item.get("credentialId") or ""
                
                if title:
                    results.append(Certification(
                        title=title.strip(),
                        issuer=issuer.strip() if issuer else None,
                        issued_date=issued_date.strip() if issued_date else None,
                        credential_id=credential_id.strip() if credential_id else None,
                        credential_url=item.get("credentialUrl", ""),
                    ))
        except Exception:
            continue
    
    return results


def _parse_languages(languages_data: Any) -> List[Language]:
    """Parse languages from LinkedIn API response."""
    results = []
    
    if not languages_data:
        return results
    
    items = languages_data if isinstance(languages_data, list) else [languages_data]
    
    for item in items:
        try:
            if isinstance(item, dict):
                lang_name = item.get("name") or item.get("languageName") or ""
                if lang_name:
                    results.append(Language(name=lang_name.strip()))
        except Exception:
            continue
    
    return results