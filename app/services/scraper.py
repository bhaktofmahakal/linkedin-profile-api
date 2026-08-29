"""Direct LinkedIn Voyager API client - browserless, pure HTTP REST.

This module replaces the Playwright-based scraper with direct HTTP requests
to LinkedIn's internal Voyager endpoints. Authentication is handled via
session cookies (li_at, JSESSIONID) provided in the .env file.

Endpoints are reverse-engineered based on LinkedIn's public API structure.
All data parsing extracts fields required by the Pydantic response schema.
"""

import json
import logging
from typing import Optional, Dict, Any, List

import httpx
from urllib.parse import quote_plus

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

# Voyager API base endpoint
VOYAGER_BASE = "https://www.linkedin.com/voyager/api"


class LinkedInVoyagerClient:
    """Direct HTTP client for LinkedIn Voyager API - no browser needed."""
    
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )
        self._session_cookie: Optional[str] = settings.LI_AT_COOKIE or ""
        self._jsessionid: Optional[str] = ""
    
    async def __aenter__(self) -> "LinkedInVoyagerClient":
        await self._ensure_auth()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.aclose()
    
    async def _ensure_auth(self) -> None:
        """Validate we have authentication credentials."""
        if not self._session_cookie:
            logger.warning("No LI_AT session cookie provided - API calls will fail")
    
    async def scrape_profile(self, profile_url: str) -> LinkedInProfileResponse:
        """Scrape a LinkedIn profile using direct Voyager API calls."""
        
        # Extract the profile ID from the URL
        profile_id = self._extract_profile_id(profile_url)
        if not profile_id:
            raise ValueError(f"Could not extract profile ID from URL: {profile_url}")
        
        logger.info(f"Scraping profile via Voyager API: {profile_id}")
        
        # Build headers required for Voyager API
        headers = self._build_headers()
        
        # First: fetch profile identity data
        identity_data = await self._fetch_identity(profile_id, headers)
        
        # Then: fetch detailed profile data
        detailed_data = await self._fetch_profile_details(profile_id, headers)
        
        # Merge and normalize
        return self._normalize_response(identity_data, detailed_data)
    
    def _extract_profile_id(self, url: str) -> Optional[str]:
        """Extract the LinkedIn profile ID from a profile URL."""
        try:
            # Handle various LinkedIn URL formats
            from urllib.parse import urlparse, parse_qs
            
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            # Format: /in/username or /in/public-id
            if '/in/' in path:
                parts = path.split('/in/')
                if len(parts) == 2:
                    return parts[1].split('?')[0].split('/')[0]
            
            # Handleurn format: urn:li:profile:{id}
            if 'urn:li:profile:' in url.lower():
                return None  # Complex handling would be needed
            
            return path
        except Exception:
            return None
    
    def _build_headers(self) -> Dict[str, str]:
        """Build required headers for Voyager API authentication."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.linkedin.v2+json",
            "X-Restli-Protocol-Version": "2.0.0",
            "X-LI-Language": "en-us",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        # Add session cookie if available
        if self._session_cookie:
            headers["Cookie"] = f"li_at={self._session_cookie}"
        
        return headers
    
    async def _fetch_identity(self, profile_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Fetch identity data from Voyager API."""
        try:
            url = f"{VOYAGER_BASE}/identity/profiles/{quote_plus(profile_id)}"
            response = await self._client.get(url, headers=headers)
            
            if response.status_code == 401:
                logger.error("Authentication failed - invalid LI_AT cookie")
                raise HTTPException(status_code=401, detail="Invalid LinkedIn session cookie")
            
            if response.status_code == 404:
                logger.error(f"Profile not found: {profile_id}")
                raise HTTPException(status_code=404, detail="Profile not found")
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Voyager identity fetch error: {e}")
            raise
    
    async def _fetch_profile_details(self, profile_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Fetch detailed profile data from Voyager API."""
        try:
            # Build the Voyager graph request for comprehensive profile data
            url = f"{VOYAGER_BASE}/profiles/{quote_plus(profile_id)}"
            # Include fields we need via the path selector
            params = {
                "q": "view",
                "fields": "id,firstName,lastName,headline,location,about,"
                          "experiences,educations,skills,certifications,languages,"
                          "profilePicture,backgroundPicture"
            }
            
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Voyager profile details fetch error: {e}")
            raise
    
    def _normalize_response(
        self, 
        identity: Dict[str, Any], 
        details: Dict[str, Any]
    ) -> LinkedInProfileResponse:
        """Normalize raw Voyager API response into Pydantic models."""
        
        # Extract basic info from identity response
        name = identity.get("name", "")
        headline = identity.get("headline", "")
        location = identity.get("location", {}).get("name") if isinstance(identity.get("location"), dict) else None
        
        # Extract about from details
        about = details.get("about", "")
        if about and isinstance(about, str) and len(about) > 500:
            about = about[:500] + "..."
        
        # Extract experiences
        experiences = self._parse_experiences(details.get("experiences", []))
        
        # Extract educations
        educations = self._parse_educations(details.get("educations", []))
        
        # Extract skills
        skills = self._parse_skills(details.get("skills", []))
        
        # Extract certifications
        certifications = self._parse_certifications(details.get("certifications", []))
        
        # Extract languages
        languages = self._parse_languages(details.get("languages", []))
        
        # Profile images
        profile_image = identity.get("profilePicture", {}).get("displayImageUrl", "") if isinstance(identity.get("profilePicture"), dict) else ""
        
        return LinkedInProfileResponse(
            name=name or "Unknown",
            headline=headline or "",
            location=location,
            about=about or None,
            experiences=experiences,
            educations=educations,
            skills=skills,
            certifications=certifications,
            languages=languages,
            profile_images=ProfileImages(
                primary=profile_image,
                secondary=[],
            ),
        )
    
    def _parse_experiences(self, experiences_data: List[Any]) -> List[Experience]:
        """Parse experiences from Voyager response."""
        results = []
        
        if not experiences_data:
            return results
        
        # Handle different response formats
        items = experiences_data if isinstance(experiences_data, list) else [experiences_data]
        
        for item in items:
            try:
                if isinstance(item, dict):
                    # Extract key fields
                    title = item.get("title", "") or item.get("positionTitle", "")
                    company = item.get("companyName", "") or item.get("company", {}).get("name", "") if isinstance(item.get("company"), dict) else ""
                    
                    from_date = item.get("startDate", "")
                    to_date = item.get("endDate", "")
                    duration = item.get("duration", "")
                    location = item.get("locationName", "") or item.get("location", {}).get("name", "") if isinstance(item.get("location"), dict) else ""
                    description = item.get("description", "")
                    
                    if title or company:
                        results.append(Experience(
                            position_title=title.strip(),
                            company_name=company.strip() or "Company",
                            company_linkedin_url=item.get("companyUrl", ""),
                            from_date=from_date,
                            to_date=to_date,
                            duration=duration,
                            location=location.strip() if location else None,
                            description=description.strip() if description else None,
                        ))
            except Exception as e:
                logger.debug(f"Error parsing experience item: {e}")
                continue
        
        return results
    
    def _parse_educations(self, educations_data: List[Any]) -> List[Education]:
        """Parse education data from Voyager response."""
        results = []
        
        if not educations_data:
            return results
        
        items = educations_data if isinstance(educations_data, list) else [educations_data]
        
        for item in items:
            try:
                if isinstance(item, dict):
                    institution = item.get("schoolName", "") or item.get("institution", {}).get("name", "") if isinstance(item.get("institution"), dict) else ""
                    degree = item.get("degreeName", "") or item.get("fieldOfStudy", "")
                    
                    from_date = item.get("startDate", "")
                    to_date = item.get("endDate", "")
                    
                    if institution:
                        results.append(Education(
                            institution_name=institution.strip(),
                            degree=degree.strip() if degree else None,
                            institution_linkedin_url=item.get("schoolUrl", ""),
                            from_date=from_date,
                            to_date=to_date,
                        ))
            except Exception as e:
                logger.debug(f"Error parsing education item: {e}")
                continue
        
        return results
    
    def _parse_skills(self, skills_data: List[Any]) -> List[str]:
        """Parse skills list from Voyager response."""
        skills = []
        
        if not skills_data:
            return skills
        
        items = skills_data if isinstance(skills_data, list) else [skills_data]
        
        for item in items:
            try:
                if isinstance(item, dict):
                    skill_name = item.get("name", "") or item.get("skillName", "")
                    if skill_name:
                        skills.append(skill_name.strip())
            except Exception:
                continue
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for skill in skills:
            if skill not in seen:
                seen.add(skill)
                unique.append(skill)
        
        return unique
    
    def _parse_certifications(self, certs_data: List[Any]) -> List[Certification]:
        """Parse certifications from Voyager response."""
        results = []
        
        if not certs_data:
            return results
        
        items = certs_data if isinstance(certs_data, list) else [certs_data]
        
        for item in items:
            try:
                if isinstance(item, dict):
                    title = item.get("title", "") or item.get("credentialName", "")
                    issuer = item.get("issuer", "")
                    issued_date = item.get("issueDate", "")
                    credential_id = item.get("credentialId", "")
                    
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
    
    def _parse_languages(self, languages_data: List[Any]) -> List[Language]:
        """Parse languages from Voyager response."""
        results = []
        
        if not languages_data:
            return results
        
        items = languages_data if isinstance(languages_data, list) else [languages_data]
        
        for item in items:
            try:
                if isinstance(item, dict):
                    lang_name = item.get("name", "") or item.get("languageName", "")
                    if lang_name:
                        results.append(Language(name=lang_name.strip()))
            except Exception:
                continue
        
        return results