# LinkedIn Profile API

A hosted FastAPI service that scrapes LinkedIn profile pages and returns structured JSON data.

## Project Overview

This project reverse engineers LinkedIn profile pages to extract structured data including:
- **name**, **headline**, **location**, **about** 
- **experience** (positions, companies, dates, descriptions)
- **education** (institutions, degrees, dates)
- **skills**, **certifications**, **languages**
- **profile images** (primary and secondary)

## Key Features

- ✅ Authenticated scraping with LinkedIn credentials or session cookie
- ✅ Full profile data extraction (unlike PhantomBuster which only gets 2 recent experiences)
- ✅ FastAPI-powered REST API with HTTPS support
- ✅ Pydantic-validated response schema
- ✅ Production-ready with deployment guides
- ✅ Rate-limit-aware with retry logic

## Local Setup & Installation

### 1. Clone & Install

```bash
git clone https://github.com/your-org/linkedin-profile-api.git
cd linkedin-profile-api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Playwright Browser Setup

This project uses Playwright for authenticated browser scraping. Install the browsers:

```bash
playwright install chromium
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your LinkedIn credentials:

```bash
cp .env.example .env
# Edit .env with your LinkedIn email/password or LI_AT cookie
```

### 4. Run the Server

```bash
# Development
python run.py

# Or directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

## API Documentation

### Endpoint: `GET /api/v1/profile`

**Query Parameters:**
- `url` (required): LinkedIn profile URL (e.g., `https://www.linkedin.com/in/john-doe`)

**Response:** JSON object matching the schema below

### Example Request

```bash
curl "http://localhost:8000/api/v1/profile?url=https://www.linkedin.com/in/john-doe"
```

### Example Response

```json
{
  "name": "John Doe",
  "headline": "Senior Software Engineer at Tech Corp",
  "location": "San Francisco Bay Area",
  "about": "Experienced software engineer with 8+ years of experience in building scalable web applications...",
  "experience": [
    {
      "position_title": "Senior Software Engineer",
      "company_name": "Tech Corp",
      "company_linkedin_url": "https://www.linkedin.com/company/tech-corpof",
      "from_date": "Jan 2020",
      "to_date": "Present",
      "duration": "5 yrs 3 mo",
      "location": "Remote",
      "description": "Led a team of 5 engineers to build a microservices platform processing 1M+ requests daily."
    }
  ],
  "education": [
    {
      "institution_name": "Stanford University",
      "degree": "MS in Computer Science",
      "institution_linkedin_url": "https://www.linkedin.com/school/stanford-university",
      "from_date": "2017",
      "to_date": "2019"
    }
  ],
  "skills": ["Python", "FastAPI", "Playwright", "AWS", "Docker"],
  "certifications": [
    {
      "title": "AWS Certified Solutions Architect",
      "issuer": "Amazon Web Services",
      "issued_date": "2021",
      "credential_id": "ABC123",
      "credential_url": "https://www.credential.com/abc123"
    }
  ],
  "languages": ["English", "Spanish"],
  "profile_images": {
    "primary": "https://media.licdn.com/dms/image/D4E03AQFD...",
    "secondary": [
      "https://media.licdn.com/dms/image/D4E03AQFD..."
    ]
  }
}
```

### Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Invalid or malformed LinkedIn URL |
| 401 | Invalid LinkedIn credentials / authentication failed |
| 422 | Validation error (missing URL parameter) |
| 500 | Scraping failure (page structure changed, rate limited, etc.) |

## Architecture & Technical Approach

### Tech Stack

- **FastAPI**: Modern Python web framework for building APIs
- **Playwright**: Headless browser automation for authenticated LinkedIn scraping
- **Pydantic**: Data validation and serialization with Python type hints
- **python-dotenv**: Environment variable configuration
- **loguru**: Logging utility

### Authentication Strategy

Two options are supported (choose one in `.env`):

1. **Email/Password Login**: The backend logs into LinkedIn using `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`, maintains session cookies, and navigates to profiles to extract data.

2. **LI_AT Cookie**: A pre-existing `li_at` session cookie is set in the browser context, allowing access to profile data without re-entering credentials.

Both approaches use Playwright's `async_api` for concurrent profile scraping with rate-limit detection and retry logic.

### Data Flow

1. API receives LinkedIn profile URL → validates with Pydantic
2. Playwright browser navigates to profile (with authenticated session)
3. Page content is parsed extracting:
   - LD+JSON script tags for structured data
   - DOM selectors for experience, education, skills, etc.
4. Raw data is cleaned, normalized, and mapped to Pydantic models
5. Validated response JSON is returned to client

### Rate Limiting & Reliability

- Requests are rate-limit aware with exponential backoff
- Browser warm-up before LinkedIn navigation
- Automatic detection of checkpoint/authwall pages
- Retry logic for flaky elements

## Known Limitations

| Limitation | Mitigation |
|------------|------------|
| LinkedIn anti-bot detection | Headless mode with fingerprint spoofing; residential proxies optional |
| CAPTCHA challenges | Rate limiting + browser warm-up; manual login fallback |
| Daily rate limits | Recommended max 100 profiles/hour per instance |
| Profile privacy settings | Some data may be restricted based on viewer's connection level |
| Browser overhead | Each request spawns a new browser context; consider connection pooling for high volume |

## Deployment

### Render.com

1. Create new Web Service → GitHub repo → Docker
2. Build Command: `pip install -r requirements.txt && playwright install chromium`
3. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add Environment Variables in Dashboard: `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` (or `LI_AT`)

### Railway.app

1. New Project → Deploy from GitHub
2. Set `NPM_NODE_ENGINE` and add `playwright install` to install script
3. Add env vars in Railway Dashboard

### Fly.io

```bash
fly launch
fly scale count 1
fly env set LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=...
fly deploy
```

## Development

```bash
# Run with hot reload
python run.py

# Run tests
pytest tests/

# Lint
ruff check app/

# Format
black app/
```

## License

MIT