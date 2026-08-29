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

    def test_profile_scraper_validation_error(self):
        """Test profile endpoint with missing URL."""
        response = self.client.get("/api/v1/profile")
        self.assertEqual(response.status_code, 422)

    def test_profile_scraper_invalid_url(self):
        """Test profile endpoint with invalid LinkedIn URL."""
        response = self.client.get("/api/v1/profile?url=https://google.com/invalid")
        self.assertEqual(response.status_code, 400)

    def test_profile_scraper_valid_url(self):
        """Test profile endpoint with valid LinkedIn URL."""
        response = self.client.get("/api/v1/profile?url=https://www.linkedin.com/in/satyanadella")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("name", data)
        self.assertIn("headline", data)
        self.assertIn("experiences", data)
        self.assertIn("educations", data)
        self.assertIn("skills", data)
        self.assertIn("languages", data)
        self.assertIn("profile_images", data)


if __name__ == "__main__":
    unittest.main()
