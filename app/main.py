"""Main FastAPI application for LinkedIn Profile API."""

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from core.config import settings
from core.dependencies import get_public_profile_url
from .routes.profile import router as profile_router

# Initialize FastAPI app
app = FastAPI(
    title="LinkedIn Profile API",
    description="""
    A hosted API that scrapes LinkedIn profile pages and returns structured JSON data.
    
    Extracts: name, headline, location, about, experience, education, skills, 
    certifications, languages, and profile images.
    
    Requires LinkedIn authentication via credentials (LINKEDIN_EMAIL/LINKEDIN_PASSWORD)
    or session cookie (LI_AT).
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set all CORS origins to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(profile_router)


@app.get(
    "/",
    tags=["root"],
    summary="Root endpoint",
    description="Root endpoint returning API information.",
)
async def root() -> dict:
    """Root endpoint returning basic API info."""
    return {
        "name": "LinkedIn Profile API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational",
    }


@app.get(
    "/health",
    tags=["root"],
    summary="Health check endpoint",
    description="Return the health status of the API service.",
)
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
    }


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler."""
    return {
        "error": "Not found",
        "detail": "The requested endpoint does not exist.",
    }, 404


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler."""
    return {
        "error": "Internal server error",
        "detail": "An unexpected error occurred.",
    }, 500