"""LinkedIn Voyager API client for real-time live profile data extraction.

Uses pure HTTP requests to reverse-engineer LinkedIn's Voyager REST API (no browser, no mock data).
Extracts: name, headline, location, about, experience, education, skills,
certifications, languages, and profile images directly from live LinkedIn responses.
"""

import json
import logging
import socket
from typing import Optional, Dict, Any, List

import httpx
from fastapi import HTTPException
from urllib.parse import quote_plus, urlparse

from core.config import settings
from models.response_schemas import (
    LinkedInProfileResponse,
    Experience,
    Education,
    Certification,
    Language,
    ProfileImages,
)

# Force IPv4 socket resolution on Windows to avoid IPv6 connection resets
try:
    orig_getaddrinfo = socket.getaddrinfo
    def _getaddrinfo_ipv4(*args, **kwargs):
        responses = orig_getaddrinfo(*args, **kwargs)
        ipv4_responses = [r for r in responses if r[0] == socket.AF_INET]
        return ipv4_responses if ipv4_responses else responses
    socket.getaddrinfo = _getaddrinfo_ipv4
except Exception:
    pass

try:
    from linkedin_api import Linkedin as LinkedinLib
    LINKEDIN_API_AVAILABLE = True
except ImportError:
    LINKEDIN_API_AVAILABLE = False

logger = logging.getLogger(__name__)

# Voyager API base endpoint
VOYAGER_BASE = "https://www.linkedin.com/voyager/api"


class LinkedInVoyagerClient:
    """Live HTTP client for LinkedIn Voyager API."""
    
    def __init__(self):
        proxy_url = settings.PROXY_URL or None
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
            proxy=proxy_url,
        )
        self._li_at: str = settings.LI_AT_COOKIE.strip() if settings.LI_AT_COOKIE else ""
        self._linkedin_api: Optional[Any] = None
        self._initialized = False
    
    async def __aenter__(self) -> "LinkedInVoyagerClient":
        await self._ensure_initialized()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.aclose()
    
    async def _ensure_initialized(self) -> None:
        """Verify authentication configuration."""
        if self._initialized:
            return
        
        if self._li_at:
            logger.info("Using LI_AT cookie authentication")
            self._initialized = True
            return
        
        if LINKEDIN_API_AVAILABLE and settings.LINKEDIN_EMAIL and settings.LINKEDIN_PASSWORD:
            logger.info("Using Email/Password authentication fallback")
            try:
                self._linkedin_api = LinkedinLib(
                    username=settings.LINKEDIN_EMAIL,
                    password=settings.LINKEDIN_PASSWORD
                )
                self._initialized = True
                return
            except Exception as e:
                logger.warning(f"Email/Password authentication error: {e}")
        
        self._initialized = True
    
    def _build_headers(self) -> Dict[str, str]:
        """Build headers with CSRF and session cookies."""
        csrf = (settings.JSESSIONID.strip().strip('"') if settings.JSESSIONID else "") or "ajax:8473628492048291"
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "X-Restli-Protocol-Version": "2.0.0",
            "X-LI-Language": "en-us",
            "Accept-Language": "en-US,en;q=0.9",
            "csrf-token": csrf,
            "Cookie": f'li_at={self._li_at}; JSESSIONID="{csrf}";',
        }
    
    async def scrape_profile(self, profile_url: str) -> LinkedInProfileResponse:
        """Scrape a live LinkedIn profile using direct Voyager API calls."""
        await self._ensure_initialized()
        
        profile_id = self._extract_profile_id(profile_url)
        if not profile_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract a valid LinkedIn profile username/ID from URL: {profile_url}"
            )
        
        if not self._li_at and not self._linkedin_api:
            raise HTTPException(
                status_code=401,
                detail="Missing LinkedIn credentials. Please provide a valid LI_AT cookie in .env"
            )
        
        logger.info(f"Scraping live profile for username: {profile_id}")
        
        if self._li_at:
            return await self._scrape_with_voyager(profile_id)
        else:
            return await self._scrape_with_linkedin_lib(profile_id)
    
    async def _scrape_with_voyager(self, profile_id: str) -> LinkedInProfileResponse:
        """Query live LinkedIn Voyager Dash API endpoint with LI_AT cookie."""
        headers = self._build_headers()
        
        dash_url = (
            f"{VOYAGER_BASE}/identity/dash/profiles"
            f"?q=memberIdentity&memberIdentity={quote_plus(profile_id)}"
            f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-35"
        )
        
        try:
            response = await self._client.get(dash_url, headers=headers)
            
            # Handle authentication / redirect issues
            if response.status_code == 302:
                # 302 redirect usually indicates invalidated session or login challenge
                loc = response.headers.get("location", "")
                set_cookies = response.headers.get_list("set-cookie")
                is_cookie_deleted = any("delete me" in c for c in set_cookies)
                
                if is_cookie_deleted or "login" in loc or "checkpoint" in loc:
                    raise HTTPException(
                        status_code=401,
                        detail="LinkedIn rejected the LI_AT cookie (session expired or logged out). Please update LI_AT in .env with a fresh cookie from your browser."
                    )
                else:
                    # Retry with propagated cookies
                    extra_cookies = "; ".join([c.split(";")[0] for c in set_cookies if c])
                    headers["Cookie"] = f"{headers['Cookie']} {extra_cookies}"
                    response = await self._client.get(loc or dash_url, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="LinkedIn authentication failed (401 Unauthorized). LI_AT cookie is invalid or expired."
                )
            
            if response.status_code in (403, 999):
                raise HTTPException(
                    status_code=403,
                    detail=f"LinkedIn anti-bot protection triggered (HTTP {response.status_code}). LinkedIn is blocking this IP. Use a residential proxy via PROXY_URL or Cloudflare Tunnel from a residential IP."
                )
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"LinkedIn profile not found for username '{profile_id}'."
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"LinkedIn Voyager API returned HTTP {response.status_code}: {response.text[:300]}"
                )
            
            data = response.json()
            return self._parse_dash_response(data, profile_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching Voyager profile for {profile_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to LinkedIn Voyager API: {str(e)}"
            )
    
    def _parse_dash_response(self, data: Dict[str, Any], profile_id: str) -> LinkedInProfileResponse:
        """Parse live LinkedIn Dash JSON into LinkedInProfileResponse."""
        included = data.get("included", [])
        
        name = ""
        headline = ""
        location = None
        about = None
        display_picture = None
        secondary_images: List[str] = []
        
        experiences: List[Experience] = []
        educations: List[Education] = []
        skills: List[str] = []
        certifications: List[Certification] = []
        languages: List[Language] = []
        
        for item in included:
            if not isinstance(item, dict):
                continue
            t = item.get("$type", "")
            
            # Profile basic info
            if "identity.profile.Profile" in t:
                fn = (item.get("firstName") or "").strip()
                ln = (item.get("lastName") or "").strip()
                if fn or ln:
                    name = f"{fn} {ln}".strip()
                headline = item.get("headline") or headline
                location = item.get("locationName") or item.get("geoCountryName") or location
                about = item.get("summary") or item.get("about") or about
                
                # Profile avatar
                pic = item.get("profilePicture")
                if isinstance(pic, dict):
                    display_picture = (
                        pic.get("displayImageReference", {}).get("vectorImage", {}).get("rootUrl")
                        or pic.get("displayPictureUrl")
                    )
            
            # Positions / Experience
            elif "identity.profile.Position" in t and "PositionGroup" not in t:
                title = (item.get("title") or "").strip()
                company = (item.get("companyName") or "").strip()
                desc = item.get("description")
                loc = item.get("locationName")
                date_range = item.get("dateRange")
                from_date = None
                to_date = None
                if isinstance(date_range, dict):
                    start = date_range.get("start")
                    end = date_range.get("end")
                    if isinstance(start, dict) and start.get("year"):
                        m = start.get("month")
                        from_date = f"{m}/{start['year']}" if m else str(start["year"])
                    if isinstance(end, dict) and end.get("year"):
                        m = end.get("month")
                        to_date = f"{m}/{end['year']}" if m else str(end["year"])
                    elif date_range:
                        to_date = "Present"
                if title or company:
                    experiences.append(Experience(
                        position_title=title or "Position",
                        company_name=company or "Company",
                        company_linkedin_url=item.get("companyUrn") or item.get("companyUrl"),
                        from_date=from_date,
                        to_date=to_date,
                        location=str(loc).strip() if loc else None,
                        description=str(desc).strip() if desc else None,
                    ))
            
            # Educations
            elif "identity.profile.Education" in t:
                school = (item.get("schoolName") or "").strip()
                degree = item.get("degreeName") or item.get("fieldOfStudy")
                date_range = item.get("dateRange")
                from_date = None
                to_date = None
                if isinstance(date_range, dict):
                    start = date_range.get("start")
                    end = date_range.get("end")
                    if isinstance(start, dict) and start.get("year"):
                        from_date = str(start.get("year"))
                    if isinstance(end, dict) and end.get("year"):
                        to_date = str(end.get("year"))
                if school:
                    educations.append(Education(
                        institution_name=school,
                        degree=str(degree).strip() if degree else None,
                        institution_linkedin_url=item.get("schoolUrn") or item.get("schoolUrl"),
                        from_date=from_date,
                        to_date=to_date,
                    ))
            
            # Skills
            elif "identity.profile.Skill" in t:
                skill_name = (item.get("name") or item.get("skillName") or "").strip()
                if skill_name and skill_name not in skills:
                    skills.append(skill_name)
                    
            # Certifications
            elif "identity.profile.Certification" in t:
                cert_name = (item.get("name") or item.get("title") or "").strip()
                issuer = item.get("authority") or item.get("issuer")
                if cert_name:
                    certifications.append(Certification(
                        title=cert_name,
                        issuer=str(issuer).strip() if issuer else None,
                        credential_id=item.get("licenseNumber"),
                        credential_url=item.get("url"),
                    ))
                    
            # Languages
            elif "identity.profile.Language" in t:
                lang = item.get("name")
                if lang and isinstance(lang, str) and lang.strip():
                    languages.append(Language(name=lang.strip()))
        
        if not name:
            name = profile_id.replace("-", " ").title()
                    
        return LinkedInProfileResponse(
            name=name,
            headline=str(headline) if headline else "",
            location=str(location) if location else None,
            about=str(about) if about else None,
            experiences=experiences,
            educations=educations,
            skills=skills,
            certifications=certifications,
            languages=languages,
            profile_images=ProfileImages(
                primary=display_picture,
                secondary=secondary_images,
            ),
        )
    
    async def _scrape_with_linkedin_lib(self, profile_id: str) -> LinkedInProfileResponse:
        """Scrape profile using linkedin-api library fallback with email/password."""
        if not self._linkedin_api:
            raise HTTPException(status_code=401, detail="linkedin-api library not initialized")
        
        try:
            profile_data = self._linkedin_api.get_profile(profile_id, force=True)
            first_name = profile_data.get("firstName", "") or ""
            last_name = profile_data.get("lastName", "") or ""
            name = f"{first_name} {last_name}".strip() or "LinkedIn Member"
            headline = profile_data.get("headline", "") or ""
            location = profile_data.get("locationName")
            about = profile_data.get("summary") or profile_data.get("about")
            
            experiences = self._parse_experiences(profile_data.get("experience", []))
            educations = self._parse_educations(profile_data.get("education", []))
            skills = self._parse_skills(profile_data.get("skills", []))
            certifications = self._parse_certifications(profile_data.get("certifications", []))
            languages = self._parse_languages(profile_data.get("languages", []))
            display_picture = profile_data.get("displayPictureUrl")
            
            return LinkedInProfileResponse(
                name=name,
                headline=headline,
                location=location,
                about=about,
                experiences=experiences,
                educations=educations,
                skills=skills,
                certifications=certifications,
                languages=languages,
                profile_images=ProfileImages(
                    primary=display_picture,
                    secondary=[],
                ),
            )
        except Exception as e:
            logger.error(f"Email/password scrape error: {e}")
            raise HTTPException(status_code=500, detail=f"Email/password authentication scraping failed: {str(e)}")
    
    def _extract_profile_id(self, url: str) -> Optional[str]:
        """Extract the LinkedIn profile ID from a profile URL."""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            if path.startswith('in/'):
                return path[3:].split('?')[0].strip('/')
            parts = path.split('/')
            if 'in' in parts:
                idx = parts.index('in')
                if idx + 1 < len(parts):
                    return parts[idx + 1].split('?')[0].strip('/')
            return None
        except Exception:
            return None
    
    def _parse_experiences(self, experiences_data: Any) -> List[Experience]:
        results = []
        if not experiences_data:
            return results
        items = experiences_data if isinstance(experiences_data, list) else [experiences_data]
        for item in items:
            try:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("positionTitle", "")
                    company = item.get("companyName") or (item.get("company", {}).get("name") if isinstance(item.get("company"), dict) else "")
                    if title or company:
                        results.append(Experience(
                            position_title=title.strip() if title else "Position",
                            company_name=company.strip() if company else "Company",
                            company_linkedin_url=item.get("companyUrl"),
                            from_date=item.get("startDate"),
                            to_date=item.get("endDate"),
                            duration=item.get("duration"),
                            location=item.get("locationName"),
                            description=item.get("description"),
                        ))
            except Exception:
                continue
        return results
    
    def _parse_educations(self, educations_data: Any) -> List[Education]:
        results = []
        if not educations_data:
            return results
        items = educations_data if isinstance(educations_data, list) else [educations_data]
        for item in items:
            try:
                if isinstance(item, dict):
                    institution = item.get("schoolName") or (item.get("institution", {}).get("name") if isinstance(item.get("institution"), dict) else "")
                    degree = item.get("degreeName") or item.get("fieldOfStudy")
                    if institution:
                        results.append(Education(
                            institution_name=institution.strip(),
                            degree=degree.strip() if degree else None,
                            institution_linkedin_url=item.get("schoolUrl"),
                            from_date=item.get("startDate"),
                            to_date=item.get("endDate"),
                        ))
            except Exception:
                continue
        return results
    
    def _parse_skills(self, skills_data: Any) -> List[str]:
        skills = []
        if not skills_data:
            return skills
        items = skills_data if isinstance(skills_data, list) else [skills_data]
        for item in items:
            try:
                if isinstance(item, dict):
                    skill_name = item.get("name") or item.get("skillName", "")
                    if skill_name and skill_name not in skills:
                        skills.append(skill_name.strip())
                elif isinstance(item, str) and item.strip() and item not in skills:
                    skills.append(item.strip())
            except Exception:
                continue
        return skills
    
    def _parse_certifications(self, certs_data: Any) -> List[Certification]:
        results = []
        if not certs_data:
            return results
        items = certs_data if isinstance(certs_data, list) else [certs_data]
        for item in items:
            try:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("credentialName", "")
                    if title:
                        results.append(Certification(
                            title=title.strip(),
                            issuer=item.get("issuer"),
                            issued_date=item.get("issueDate"),
                            credential_id=item.get("credentialId"),
                            credential_url=item.get("credentialUrl"),
                        ))
            except Exception:
                continue
        return results
    
    def _parse_languages(self, languages_data: Any) -> List[Language]:
        results = []
        if not languages_data:
            return results
        items = languages_data if isinstance(languages_data, list) else [languages_data]
        for item in items:
            try:
                if isinstance(item, str) and item.strip():
                    results.append(Language(name=item.strip()))
                elif isinstance(item, dict):
                    lang_name = item.get("name") or item.get("languageName", "")
                    if lang_name and isinstance(lang_name, str):
                        results.append(Language(name=lang_name.strip()))
            except Exception:
                continue
        return results