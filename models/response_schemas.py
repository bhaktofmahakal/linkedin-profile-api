"""Pydantic models for LinkedIn Profile API response."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class ProfileImages(BaseModel):
    """Profile image URLs."""
    primary: HttpUrl
    secondary: List[HttpUrl] = Field(default_factory=list)


class Experience(BaseModel):
    """Work experience model."""
    position_title: Optional[str] = None
    company_name: Optional[str] = None
    company_linkedin_url: Optional[HttpUrl] = Field(default=None, alias="company_linkedin_url")
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

    class Config:
        populate_by_name = True


class Education(BaseModel):
    """Education model."""
    institution_name: Optional[str] = None
    degree: Optional[str] = None
    institution_linkedin_url: Optional[HttpUrl] = Field(default=None, alias="institution_linkedin_url")
    from_date: Optional[str] = None
    to_date: Optional[str] = None

    class Config:
        populate_by_name = True


class Certification(BaseModel):
    """Certification/accomplishment model."""
    title: str
    issuer: Optional[str] = None
    issued_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[HttpUrl] = Field(default=None, alias="credential_url")


class Language(BaseModel):
    """Language model."""
    name: str


class LinkedInProfileResponse(BaseModel):
    """Full LinkedIn profile response schema."""
    name: str
    headline: str
    location: Optional[str] = None
    about: Optional[str] = None
    experiences: List[Experience] = Field(default_factory=list)
    educations: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    profile_images: ProfileImages = Field(default_factory=ProfileImages)

    class Config:
        populate_by_name = True
        json_encoders = {
            HttpUrl: lambda v: str(v)
        }

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)

    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)