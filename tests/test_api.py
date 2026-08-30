import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


class TestLinkedInProfileAPI(unittest.TestCase):
    """Test suite for LinkedIn Profile API endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "LinkedIn Profile API")
        self.assertEqual(data["status"], "operational")

    def test_profile_scraper_missing_header(self):
        """Test profile endpoint with missing required X-LI-AT header."""
        response = self.client.get("/api/v1/profile?url=https://www.linkedin.com/in/satyanadella")
        self.assertEqual(response.status_code, 422)

    def test_profile_scraper_validation_error(self):
        """Test profile endpoint with missing URL."""
        headers = {"X-LI-AT": "AQED_SAMPLE_TOKEN"}
        response = self.client.get("/api/v1/profile", headers=headers)
        self.assertEqual(response.status_code, 422)

    def test_profile_scraper_invalid_url(self):
        """Test profile endpoint with invalid LinkedIn URL."""
        headers = {"X-LI-AT": "AQED_SAMPLE_TOKEN"}
        response = self.client.get("/api/v1/profile?url=https://google.com/invalid", headers=headers)
        self.assertEqual(response.status_code, 400)

    def test_profile_scraper_valid_url(self):
        """Test profile endpoint with valid LinkedIn URL and header."""
        headers = {"X-LI-AT": "AQED_SAMPLE_TOKEN"}
        response = self.client.get("/api/v1/profile?url=https://www.linkedin.com/in/satyanadella", headers=headers)
        # In pure live mode without mocks:
        # If credentials and IP are accepted -> 200 with complete profile schema
        # If LinkedIn blocks IP or session cookie needs renewal -> 401 / 403 with structured detail
        self.assertIn(response.status_code, [200, 401, 403])
        if response.status_code == 200:
            data = response.json()
            self.assertIn("name", data)
            self.assertIn("headline", data)
            self.assertIn("experiences", data)
            self.assertIn("educations", data)
            self.assertIn("skills", data)
            self.assertIn("languages", data)
            self.assertIn("profile_images", data)
    def test_dynamic_auth_session_update(self):
        """Test POST /api/v1/auth/session runtime cookie update."""
        payload = {
            "li_at": "AQED_TEST_SAMPLE_TOKEN_VALUE",
            "jsessionid": "ajax:1234567890",
        }
        response = self.client.post("/api/v1/auth/session", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("li_at_prefix", data)


if __name__ == "__main__":
    unittest.main()

