"""
API Integration Tests for Mohamed Job Agent Worker API
======================================================
Tests the FastAPI endpoints in scripts/api_server.py.
"""

import unittest
import os
import shutil
import tempfile
import json
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure scripts directory is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from api_server import app
from db_manager import init_database

class TestWorkerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_api.db")
        init_database(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["service"], "job-worker")
        self.assertIn("libreoffice", data)
        self.assertIn("pdftotext", data)

    def test_parse_email_endpoint(self):
        import time
        unique_email_id = f"email_test_{int(time.time()*1000)}"
        payload = {
            "id": unique_email_id,
            "subject": "3 new jobs for Embedded Engineer",
            "sender": "jobs-noreply@linkedin.com",
            "from": "jobs-noreply@linkedin.com",
            "body_html": '<a href="https://www.linkedin.com/comm/jobs/view/3999999001/">Embedded Dev</a>'
        }
        response = self.client.post("/parse-email", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["extracted_jobs"][0]["linkedin_job_id"], "3999999001")

    def test_process_job_endpoint(self):
        payload = {
            "linkedin_job_id": "3999999002",
            "title": "AUTOSAR SW Engineer",
            "company": "Continental",
            "location": "Germany",
            "full_description": "Embedded C, AUTOSAR Classic, CAN, UDS"
        }
        response = self.client.post("/process-job", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["inserted"])
        self.assertIsNotNone(data["job_id"])

    def test_fetch_description_endpoint(self):
        process_payload = {
            "title": "Embedded Software Engineer",
            "company": "Valeo",
            "location": "Germany",
            "linkedin_job_id": "3999999999"
        }
        res1 = self.client.post("/process-job", json=process_payload)
        job_id = res1.json()["job_id"]

        fetch_payload = {
            "job_id": job_id,
            "raw_html_or_text": "Requirements: 5+ years of Embedded C, AUTOSAR Classic, CAN. Language: English fluent. Visa: Work authorization available.",
            "official_url": "https://valeo.wd3.myworkdayjobs.com/careers/job/123",
            "description_source": "Workday ATS"
        }
        res2 = self.client.post("/fetch-description", json=fetch_payload)
        self.assertEqual(res2.status_code, 200)
        data = res2.json()
        self.assertEqual(data["status"], "FETCHED")
        self.assertTrue(data["is_complete"])

    def test_analyze_job_endpoint(self):
        job_payload = {
            "job": {
                "id": 1,
                "title": "ECU Engineer",
                "company": "ZF Group",
                "location": "Netherlands",
                "full_description": "C, AUTOSAR, CAN"
            }
        }
        response = self.client.post("/analyze-job", json=job_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("analysis_prompt", data)
        self.assertIn("ats_prompt", data)

    def test_save_analysis_endpoint(self):
        payload = {
            "job_id": 1,
            "analysis": {
                "fit_score": 85.0,
                "technical_score": 90.0,
                "career_score": 80.0,
                "relocation_score": 90.0,
                "visa_score": 80.0,
                "decision": "APPLY",
                "matched_skills": ["AUTOSAR", "Embedded C"],
                "missing_required_skills": [],
                "visa_sponsorship": "LIKELY",
                "relocation": "CONFIRMED"
            }
        }
        response = self.client.post("/save-analysis", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["saved"])

    def test_generate_documents_endpoint(self):
        payload = {
            "job": {
                "id": 999,
                "title": "Embedded Software Developer",
                "company": "ZF Group",
                "location": "Eindhoven, Netherlands",
                "linkedin_job_id": "3999999003"
            },
            "ats_keywords": {
                "required": ["AUTOSAR", "Embedded C", "CAN", "UDS"],
                "preferred": ["Vector DaVinci", "CANoe", "Python"]
            }
        }
        response = self.client.post("/generate-documents", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["all_valid"])
        self.assertEqual(data["status"], "DOCUMENTS_READY")
        self.assertEqual(data["pdf_validation_status"], "PASSED")
        self.assertIsNotNone(data["documents"]["cv_pdf"])
        self.assertTrue(os.path.exists(data["documents"]["cv_pdf"]))

    def test_daily_report_endpoint(self):
        response = self.client.post("/daily-report")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("report", data)
        self.assertIn("summary", data)

if __name__ == "__main__":
    unittest.main()
