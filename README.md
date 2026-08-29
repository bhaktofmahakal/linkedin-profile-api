# LinkedIn Profile API

A hosted FastAPI service that extracts LinkedIn profile data using **pure HTTP REST requests** to LinkedIn's internal Voyager API — no browser, no Playwright, purely reverse-engineered.

## Project Overview

This project reverse engineers LinkedIn's Voyager API to extract structured profile data. By making direct HTTP calls to undocumented LinkedIn endpoints, we achieve the same data extraction as browser-based scrapers but with:

- **Zero browser overhead** — faster, cheaper, more reliable
- **No headless browser detection** — avoids LinkedIn's anti-bot mechanisms
- **Direct API access** — cleaner data, fewer parsing edge cases
- **Production-ready** — suitable for deployment on any HTTPS-capable platform

### Data Extracted

- **name**, **headline**, **location**, **about**
- **experience** (positions, companies, dates, descriptions)
- **education** (institutions, degrees, dates)
- **skills**, **certifications**, **languages**
- **profile images** (primary and secondary)

## Key Features

- ✅ **100% Browserless** — direct HTTP requests to Voyager API
- ✅ Full profile data extraction (unlike PhantomBuster which only gets 2 recent experiences)
- ✅ FastAPI-powered REST API with HTTPS support
- ✅ Pydantic-validated response schema
- ✅ Production-ready with deployment guides
- ✅ Session cookie authentication (LI_AT)

## Local Setup & Installation

### 1. Clone & Install

```bash
git clone https://github.com/bhaktofmahakal/linkedin-profile-api.git
cd linkedin-profile-api
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and provide LinkedIn session cookie:

```bash
cp .env.example .env
```

Edit `.env` with your authentication method:

**Option A: LI_AT Session Cookie** (recommended)
- Log into LinkedIn in your browser
- Inspect application cookies, copy the `li_at` value
- Paste into `LI_AT` variable in `.env`

**Option B: Email & Password** (alternative)
- `LINKEDIN_EMAIL=your_linkedin_email@example.com`
- `LINKEDIN_PASSWORD=your_linkedin_password`

```env
# Required: LinkedIn session cookie (get from browser devtools → Application → Cookies)
LI_AT=your_li_at_cookie_value_here

# Optional: Email/password fallback
LINKEDIN_EMAIL=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password

# Application settings
APP_ENV=development
```

### 3. Start the Server

```bash
python run.py
```

The API will be available at `http://localhost:8000`.

### 4. Test the API

**cURL:**

```bash
curl "http://localhost:8000/api/v1/profile?url=https://www.linkedin.com/in/example"
```

**Python:**

```python
import requests

resp = requests.get(
    "http://localhost:8000/api/v1/profile",
    params={"url": "https://www.linkedin.com/in/example"}
)
print(resp.json())
```

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
| 401 | Invalid LinkedIn credentials / expired LI_AT cookie |
| 422 | Validation error (missing URL parameter) |
| 500 | API request failure (rate limited, profile restricted, network error) |

## Architecture & Technical Approach

### Tech Stack

- **FastAPI**: Modern Python web framework for building APIs
- **httpx**: Async HTTP client for direct Voyager API requests
- **Pydantic**: Data validation and serialization with Python type hints
- **python-dotenv**: Environment variable configuration
- **loguru**: Logging utility

### Authentication Strategy

The solution uses direct HTTP authentication to LinkedIn's Voyager API:

1. **LI_AT Cookie** (primary): A valid `li_at` session cookie obtained from LinkedIn's login flow
   - Set in the `.env` file: `LI_AT=your_cookie_value`
   - The `LinkedInVoyagerClient` automatically includes this cookie in all API requests
   - LinkedIn requests must include valid cookies to access profile data

2. **Session Management**: 
   - The `li_at` cookie handles authenticated session maintenance
   - Requests include proper `User-Agent`, `Accept`, and `X-LI-Language` headers
   - API returns 401 if cookie is expired/invalid, prompting user to refresh

### Data Flow

1. API receives LinkedIn profile URL → validates with Pydantic
2. `LinkedInVoyagerClient` constructs Voyager API requests with proper headers and cookies
3. Direct HTTP GET requests to `https://www.linkedin.com/voyager/api/identity/profiles/{id}` and related endpoints
4. Raw JSON payloads are parsed and mapped to Pydantic models
5. Validated response JSON is returned to client

### Rate Limiting & Reliability

- Requests include proper headers to mimic legitimate browser traffic
- Exponential backoff on 429 (Too Many Responses) responses
- Automatic handling of 401 responses (expired session)
- Graceful degradation when optional fields are missing

## Known Limitations

| Limitation | Mitigation |
|------------|------------|
| LinkedIn API schema changes | Monitor Voyager endpoints; update parsing logic as needed |
| Session cookie expiration | Requires periodic `LI_AT` cookie refresh; optional email/password fallback |
| Rate limiting | Recommended max 100 profiles/hour; respect `429` responses with backoff |
| Profile privacy settings | Some data restricted based on viewer's connection level |
| Unknown endpoint stability | Voyager API is undocumented — may change without notice |

## Deployment

### Render.com

Deploy to Render using the included `render.yaml` blueprint:

1. **Connect Repository**
   - Go to [Render.com](https://render.com) and create a new account.
   - Click **New Web Service** → **Connect Repository** → select `linkedin-profile-api`.
   - GitHub: `https://github.com/bhaktofmahakal/linkedin-profile-api`.

2. **Service Settings**
   - **Name**: `linkedin-profile-api` (or your preferred name).
   - **Environment**: `Python`.
   - **Build Command**: `pip install -r requirements.txt`.
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

3. **Environment Variables**
   - In the **Dashboard**, add the following environment variables:
     - `LI_AT`: Your LinkedIn session cookie value (required).
     - `LINKEDIN_EMAIL`: Your LinkedIn email (optional, for fallback auth).
     - `LINKEDIN_PASSWORD`: Your LinkedIn password (optional, for fallback auth).
     - `APP_ENV`: `production`.
     - `API_V1_STR`: `/api/v1`.

4. **Deploy**
   - Click **Create Web Service**. Render will build and start your container.
   - The service will be live at `https://linkedin-profile-api.onrender.com`.

5. **Verify**
   - Visit `https://linkedin-profile-api.onrender.com/health` — should return `{"status":"ok"}`.
   - Test the profile endpoint: `https://linkedin-profile-api.onrender.com/api/v1/profile?url=https://www.linkedin.com/in/example`.

### Railway.app

1. New Project → Deploy from GitHub.
2. Build Command: `pip install -r requirements.txt`.
3. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Set env vars in Railway Dashboard: `LI_AT`, `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, `APP_ENV=production`.

### Fly.io

```bash
fly launch
fly scale count 1
fly env set LI_AT=... LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=... APP_ENV=production
fly deploy
```

### Procfile

The repository includes a `Procfile` for compatibility with platforms that read it directly:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Git Repository & Submission

### Initial Commit

The repository contains a single meaningful commit:

```
feat: complete production-ready LinkedIn Profile API implementation
```

### .gitignore Protection

The `.env` file and `__pycache__` directories are explicitly gitignored to prevent credential leakage:

```
.env
*.pyc
__pycache__
.venv
venv
node_modules
output/
results/
*.db
```

### Verification Checklist (Engineer Hiring Challenge)

- [x] API publicly over HTTPS
- [x] Accepts LinkedIn profile URL input
- [x] Returns: name, headline, location, about, experience, education, skills, certifications, languages, profile images
- [x] Uses backend LinkedIn credentials (LI_AT cookie)
- [x] Public GitHub repository with complete source code
- [x] README with setup instructions, API documentation, approach, and known limitations
- [x] Credentials out of repository (.env not committed)
- [x] Single meaningful git commit with proper message

## License

MIT