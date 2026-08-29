"""Pydantic models for LinkedIn Profile API response."""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class ProfileImages(BaseModel):
    """Profile image URLs."""
    primary: Optional[str] = None
    secondary: List[str] = Field(default_factory=list)

    @field_validator("primary", mode="before")
    @classmethod
    def validate_primary(cls, v):
        if v is None:
            return None
        return str(v)

    @field_validator("secondary", mode="before")
    @classmethod
    def validate_secondary(cls, v):
        if not v:
            return []
        return [str(x) for x in v if x]


class Experience(BaseModel):
    """Work experience model."""
    position_title: Optional[str] = None
    company_name: Optional[str] = None
    company_linkedin_url: Optional[str] = Field(default=None, alias="company_linkedin_url")
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
    institution_linkedin_url: Optional[str] = Field(default=None, alias="institution_linkedin_url")
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
    credential_url: Optional[str] = Field(default=None, alias="credential_url")


class Language(BaseModel):
    """Language model."""
    name: str

    @classmethod
    def from_str(cls, v: str) -> "Language":
        return cls(name=v)


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

    @field_validator("languages", mode="before")
    @classmethod
    def validate_languages(cls, v):
        if not v:
            return []
        res = []
        for item in v:
            if isinstance(item, str):
                res.append(Language(name=item))
            elif isinstance(item, dict):
                res.append(Language(**item))
            elif isinstance(item, Language):
                res.append(item)
        return res

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)

    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)