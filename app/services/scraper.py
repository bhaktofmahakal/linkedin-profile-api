"""Playwright-based LinkedIn profile scraper service.

Handles authenticated browser navigation, profile data extraction,
and clean mapping to Pydantic response models.
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

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


class LinkedInScraper:
    """Authenticated LinkedIn profile scraper using Playwright."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Any] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._initialized = False
    
    async def __aenter__(self) -> "LinkedInScraper":
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def start(self) -> None:
        """Initialize Playwright and launch browser."""
        if self._initialized:
            return
        
        try:
            self._playwright = await async_playwright().start()
            
            # Launch browser with appropriate options
            launch_kwargs = {
                "headless": self.headless,
                "slow_mo": 100 if settings.APP_ENV == "development" else 0,
            }
            
            # Add user agent and viewport to avoid detection
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            
            # Create context with storage state if we have a cookie
            context_kwargs = {
                "viewport": {"width": 1280, "height": 720},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            
            # Set up authentication cookie if LI_AT is provided
            if settings.LI_AT_COOKIE:
                context_kwargs["storage_state"] = {
                    "cookies": [
                        {
                            "name": "li_at",
                            "value": settings.LI_AT_COOKIE,
                            "domain": ".linkedin.com",
                            "path": "/",
                        }
                    ]
                }
            
            self._context = await self._browser.new_context(**context_kwargs)
            self._initialized = True
            logger.info("LinkedIn scraper browser started successfully")
            
        except Exception as e:
            await self.close()
            raise RuntimeError(f"Failed to start LinkedIn scraper: {e}")
    
    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._initialized = False
        logger.info("LinkedIn scraper browser closed")
    
    async def scrape_profile(self, profile_url: str) -> LinkedInProfileResponse:
        """Scrape a LinkedIn profile URL and return structured data."""
        
        if not self._initialized:
            await self.start()
        
        if not self._context or not self._browser:
            raise RuntimeError("Browser not initialized")
        
        page = await self._context.new_page()
        
        try:
            logger.info(f"Navigating to profile: {profile_url}")
            
            # Navigate to the profile page
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
            
            # Check for authentication/rate limit blockers
            await self._check_auth_status(page)
            
            # Warm up - wait for page to settle
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Extract data from multiple sources
            profile_data = await self._extract_all_data(page)
            
            return profile_data
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout scraping profile {profile_url}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Timed out scraping profile. The page structure may have changed "
                        "or LinkedIn is rate limiting the request."
            )
        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {e}")
            raise
        finally:
            await page.close()
    
    async def _check_auth_status(self, page: Page) -> None:
        """Check for authentication roadblocks."""
        current_url = page.url
        
        # Check for LinkedIn login page
        if "/login" in current_url or "/checkpoint" in current_url:
            error_msg = "Authentication required. Invalid or expired LinkedIn credentials."
            logger.warning(error_msg)
            raise HTTPException(
                status_code=401,
                detail=error_msg
            )
        
        # Check for authwall
        if "/authwall" in current_url:
            raise HTTPException(
                status_code=401,
                detail="Authentication wall encountered. Credentials may be invalid."
            )
    
    async def _extract_all_data(self, page: Page) -> LinkedInProfileResponse:
        """Extract all profile data from the page."""
        
        # Try to extract LD+JSON structured data first
        ld_json_data = await self._extract_ld_json(page)
        
        # Extract data from DOM selectors
        dom_data = await self._extract_dom_data(page)
        
        # Merge and normalize data
        return self._normalize_data(ld_json_data, dom_data)
    
    async def _extract_ld_json(self, page: Page) -> Dict[str, Any]:
        """Extract LinkedIn LD+JSON structured data."""
        try:
            scripts = await page.locator(
                "//script[@type='application/ld+json']"
            ).all()
            
            for script in scripts:
                try:
                    text_content = await script.text_content()
                    if not text_content.strip():
                        continue
                    
                    data = json.loads(text_content)
                    
                    # Check if this is a Person schema
                    if isinstance(data, dict):
                        if data.get("@type") == "Person":
                            return data
                        # Check within @graph
                        if "@graph" in data:
                            for item in data["@graph"]:
                                if isinstance(item, dict) and item.get("@type") == "Person":
                                    return item
                except (json.JSONDecodeError, Exception):
                    continue
        except Exception as e:
            logger.debug(f"LD+JSON extraction failed: {e}")
        
        return {}
    
    async def _extract_dom_data(self, page: Page) -> Dict[str, Any]:
        """Extract data from DOM selectors."""
        data = {
            "name": "",
            "headline": "",
            "location": "",
            "about": "",
            "experiences": [],
            "educations": [],
            "skills": [],
            "certifications": [],
            "languages": [],
        }
        
        try:
            # Extract name - typically in h1 tag
            name = await self._safe_text(page, "h1")
            if name:
                data["name"] = name.strip()
            
            # Extract headline
            headline = await self._safe_text(page, ".display-flex .text-heading-xxlarge")
            if headline:
                data["headline"] = headline.strip()
            
            # Extract location
            location = await self._safe_text(page, ".text-body-small.inline")
            if location:
                data["location"] = location.strip()
            
            # Extract about section
            about = await self._extract_about(page)
            if about:
                data["about"] = about
            
            # Extract experiences
            data["experiences"] = await self._extract_experiences(page)
            
            # Extract educations
            data["educations"] = await self._extract_educations(page)
            
            # Extract skills
            data["skills"] = await self._extract_skills(page)
            
            # Extract certifications
            data["certifications"] = await self._extract_certifications(page)
            
            # Extract languages
            data["languages"] = await self._extract_languages(page)
            
        except Exception as e:
            logger.warning(f"DOM data extraction had issues: {e}")
        
        return data
    
    async def _safe_text(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract text from a selector."""
        try:
            element = page.locator(selector).first
            if await element.count() == 0:
                return None
            text = await element.text_content(timeout=5000)
            return text.strip() if text else None
        except Exception:
            return None
    
    async def _extract_about(self, page: Page) -> Optional[str]:
        """Extract the about/me section."""
        try:
            # Look for about section - try multiple selectors
            selectors = [
                "[data-section-about]",
                ".about-section",
                ".pv-about-section",
                "//section[contains(@class, 'about')]",
            ]
            
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        # Try to get the full text
                        text = await element.inner_text(timeout=5000)
                        if text and text.strip():
                            # Clean up the text
                            text = " ".join(text.strip().split())
                            return text
                except Exception:
                    continue
            
            # Fallback: look for "About" heading and get following content
            about_heading = page.locator(":has-text('About')").first
            if await about_heading.count() > 0:
                # Get the parent section
                parent = about_heading.locator("xpath=ancestor::*[1]")
                if await parent.count() > 0:
                    text = await parent.inner_text(timeout=5000)
                    if text and text.strip():
                        return text.strip()
                        
        except Exception as e:
            logger.debug(f"About section extraction failed: {e}")
        
        return None
    
    async def _extract_experiences(self, page: Page) -> List[Dict[str, Any]]:
        """Extract work experience data."""
        experiences = []
        
        try:
            # Look for experience section heading
            exp_heading = page.locator(':has-text("Experience")').first
            
            if await exp_heading.count() > 0:
                # Try to find the experience section
                section = exp_heading.locator("xpath=ancestor::*[1]")
                
                # Try different list item patterns
                items = await section.locator(
                    "ul > li, ol > li, .pvs-list__paged-list-item"
                ).all()
                
                for item in items:
                    try:
                        # Try to extract position, company, dates
                        title_elem = item.locator(
                            "span[aria-hidden='true']"
                        ).first
                        
                        title = await self._safe_text_from_locator(title_elem) if await title_elem.count() > 0 else None
                        
                        # Get company name (second text element or link)
                        company = ""
                        links = await item.locator("a").all()
                        if len(links) > 0:
                            href = await links[0].get_attribute("href")
                            company = href or ""
                        
                        # Get date range
                        date_text = await self._safe_text(item, ".date-range")
                        
                        if title or company:
                            experiences.append({
                                "position_title": title or "Unknown Position",
                                "company_name": company.strip("/").split("/")[-1] if company else "Company",
                                "from_date": "",  # Will be parsed if available
                                "to_date": "",
                                "duration": "",
                                "location": "",
                                "description": "",
                            })
                    except Exception:
                        continue
                    
        except Exception as e:
            logger.warning(f"Experience extraction had issues: {e}")
        
        return experiences
    
    async def _extract_educations(self, page: Page) -> List[Dict[str, Any]]:
        """Extract education data."""
        educations = []
        
        try:
            edu_heading = page.locator(':has-text("Education")').first
            
            if await edu_heading.count() > 0:
                section = edu_heading.locator("xpath=ancestor::*[1]")
                items = await section.locator(
                    "ul > li, ol > li, .pvs-list__paged-list-item"
                ).all()
                
                for item in items:
                    try:
                        institution = await self._safe_text(item, "a")
                        degree = await self._safe_text(item, ".degree-info")
                        
                        if institution:
                            educations.append({
                                "institution_name": institution.strip(),
                                "degree": degree.strip() if degree else None,
                                "from_date": "",
                                "to_date": "",
                            })
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.warning(f"Education extraction had issues: {e}")
        
        return educations
    
    async def _extract_skills(self, page: Page) -> List[str]:
        """Extract skills from profile."""
        skills = []
        
        try:
            # Look for skills section
            skills_section = page.locator(':has-text("Skills")').first
            
            if await skills_section.count() > 0:
                # Find skill pills/tags
                skill_elements = skills_section.locator(
                    ".pill-container .pill, .skill-item, [data-skill]"
                ).all()
                
                for skill in skill_elements:
                    try:
                        text = await skill.text_content(timeout=3000)
                        if text and text.strip() and len(text.strip()) > 2:
                            skills.append(text.strip())
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Skills extraction failed: {e}")
        
        # Deduplicate while preserving order
        seen = set()
        unique_skills = []
        for skill in skills:
            if skill not in seen:
                seen.add(skill)
                unique_skills.append(skill)
        
        return unique_skills[:50]  # Limit to 50 skills
    
    async def _extract_certifications(self, page: Page) -> List[Dict[str, Any]]:
        """Extract certifications/accomplishments."""
        certs = []
        
        try:
            # Look for certifications section
            cert_section = page.locator(':has-text("Certifications")').first
            
            if await cert_section.count() > 0:
                items = await cert_section.locator(
                    ".pvs-list__paged-list-item, .certification-item"
                ).all()
                
                for item in items:
                    try:
                        title = await self._safe_text(item, "span:first-child")
                        issuer = await self._safe_text(item, ".issuer")
                        date = await self._safe_text(item, ".date")
                        
                        if title:
                            certs.append({
                                "title": title.strip(),
                                "issuer": issuer.strip() if issuer else None,
                                "issued_date": date.strip() if date else None,
                                "credential_id": None,
                                "credential_url": None,
                            })
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Certifications extraction failed: {e}")
        
        return certs
    
    async def _extract_languages(self, page: Page) -> List[str]:
        """Extract languages from profile."""
        languages = []
        
        try:
            # Look for "Languages" section or "Tiếng Việt" etc.
            lang_section = page.locator(':has-text("Languages")').first
            
            if await lang_section.count() > 0:
                # Find language items
                lang_items = lang_section.locator(
                    "li, .language-item, span[lang]"
                ).all()
                
                for item in lang_items:
                    try:
                        text = await item.text_content(timeout=3000)
                        if text and text.strip():
                            lang = text.strip()
                            if lang and lang not in languages:
                                languages.append(lang)
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Languages extraction failed: {e}")
        
        return languages
    
    def _normalize_data(
        self, 
        ld_json: Dict[str, Any], 
        dom: Dict[str, Any]
    ) -> LinkedInProfileResponse:
        """Normalize and merge LD+JSON and DOM data into response model."""
        
        # Start with DOM data as fallback, LD+JSON as primary
        name = ld_json.get("name", dom.get("name", ""))
        headline = ld_json.get("headline", dom.get("headline", ""))
        location = ld_json.get("location", {}).get("address", dom.get("location", ""))
        about = ld_json.get("summary", dom.get("about", ""))
        
        # Extract experiences
        experiences_data = ld_json.get("worksFor", dom.get("experiences", []))
        experiences = []
        for exp in (experiences_data if isinstance(experiences_data, list) else [experiences_data]):
            experiences.append(Experience(
                position_title=exp.get("title") or exp.get("positionTitle", ""),
                company_name=exp.get("organization", {}).get("name", "") if isinstance(exp.get("organization"), dict) else "",
                company_linkedin_url=exp.get("organization", {}).get("url", ""),
                from_date=exp.get("startDate", ""),
                to_date=exp.get("endDate", ""),
                duration=exp.get("duration", ""),
                location=exp.get("location", {}).get("name", "") if isinstance(exp.get("location"), dict) else "",
                description=exp.get("description", ""),
            ))
        
        # Extract educations
        educations_data = ld_json.get("educations", dom.get("educations", []))
        educations = []
        for edu in (educations_data if isinstance(educations_data, list) else [educations_data]):
            educations.append(Education(
                institution_name=edu.get("school", {}).get("name", "") if isinstance(edu.get("school"), dict) else "",
                degree=edu.get("fieldOfStudy"),
                institution_linkedin_url=edu.get("school", {}).get("url", ""),
                from_date=edu.get("startDate"),
                to_date=edu.get("endDate"),
            ))
        
        # Extract skills from LD+JSON if available, otherwise DOM
        skills = ld_json.get("skills", [])
        if not skills:
            skills = dom.get("skills", [])
        
        # Extract certifications
        certs_data = ld_json.get("certifications", dom.get("certifications", []))
        certifications = []
        for cert in (certs_data if isinstance(certs_data, list) else [certs_data]):
            certifications.append(Certification(
                title=cert.get("title", ""),
                issuer=cert.get("issuer"),
                issued_date=cert.get("issuedDate"),
                credential_id=cert.get("credentialId"),
                credential_url=cert.get("credentialUrl"),
            ))
        
        # Extract languages
        lang_data = ld_json.get("languages", [])
        if not lang_data:
            lang_data = dom.get("languages", [])
        languages = [Language(name=lang) for lang in (lang_data if isinstance(lang_data, list) else [lang_data]) if lang]
        
        # Profile images
        profile_image_url = ld_json.get("image", "")
        if not profile_image_url:
            profile_image_url = dom.get("profile_images", {}).get("primary", "")
        
        secondary_images = ld_json.get("image", "")
        # Extract secondary images from DOM if needed
        
        return LinkedInProfileResponse(
            name=name or "Unknown",
            headline=headline or "",
            location=location or None,
            about=about or None,
            experiences=experiences,
            educations=educations,
            skills=skills[:50],  # Cap at 50
            certifications=certifications,
            languages=languages,
            profile_images=ProfileImages(
                primary=profile_image_url or "",
                secondary=[],  # Will be populated if available
            ),
        )