"""
Mohamed Job Agent — Test Suite
================================
Tests for email parsing, deduplication, AI response parsing, and database operations.
"""

import json
import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Add project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "browser-agent"))

from email_parser import (
    parse_email, is_linkedin_job_alert, should_skip_email,
    extract_linkedin_job_id, clean_linkedin_url,
    extract_jobs_from_html, extract_jobs_from_text,
)
from db_manager import (
    get_connection, init_database, insert_job, job_exists,
    make_dedup_key, normalize_text, update_job_status,
    update_job_analysis, log_processed_email, is_email_processed,
)
from ai_analyzer import (
    parse_ai_response, validate_analysis, apply_decision_thresholds,
    extract_cv_content, extract_letter_content,
    load_career_profile, build_analysis_prompt,
)
from job_retriever import detect_ats_platform, build_careers_search_query

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture_emails():
    """Load sample email fixtures."""
    with open(FIXTURES_DIR / "sample_emails.json", "r") as f:
        return json.load(f)


class TestEmailFiltering(unittest.TestCase):
    """Test email identification and filtering."""

    def test_linkedin_job_alert_valid(self):
        self.assertTrue(is_linkedin_job_alert(
            "jobs-noreply@linkedin.com",
            "3 new jobs match your alert",
        ))

    def test_linkedin_non_alert_rejected(self):
        self.assertFalse(is_linkedin_job_alert(
            "noreply@example.com",
            "3 new jobs",
        ))

    def test_application_confirmation_skipped(self):
        self.assertTrue(should_skip_email("Your application was sent to Continental AG"))
        self.assertTrue(should_skip_email("Application was sent successfully"))

    def test_problem_email_skipped(self):
        self.assertTrue(should_skip_email("Problem with your job alert"))

    def test_valid_alert_not_skipped(self):
        self.assertFalse(should_skip_email("5 new jobs match your alert for Embedded"))


class TestJobExtraction(unittest.TestCase):
    """Test job extraction from emails."""

    def setUp(self):
        self.emails = load_fixture_emails()

    def test_multiple_jobs_extracted(self):
        """Email with 3 jobs should yield 3 results."""
        email = self.emails[0]  # email_001: 3 jobs
        jobs = parse_email(email)
        self.assertEqual(len(jobs), 3)

    def test_duplicate_within_second_email(self):
        """Email 002 contains job 3912345001 which was also in email 001."""
        email = self.emails[1]  # email_002: 5 jobs but one is duplicate
        jobs = parse_email(email)
        # Should have unique IDs within the email itself
        ids = [j["linkedin_job_id"] for j in jobs]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs within single email")

    def test_application_confirmation_ignored(self):
        """Application confirmation emails should yield zero jobs."""
        email = self.emails[2]  # email_003_skip
        jobs = parse_email(email)
        self.assertEqual(len(jobs), 0)

    def test_malformed_link_handled(self):
        """Malformed links should not crash parser."""
        email = self.emails[3]  # email_004_malformed
        jobs = parse_email(email)
        # Should at least extract the valid job
        valid_jobs = [j for j in jobs if j.get("linkedin_job_id")]
        self.assertGreaterEqual(len(valid_jobs), 1)

    def test_text_only_email(self):
        """Plain text emails should still extract jobs."""
        email = self.emails[4]  # email_005_text_only
        jobs = parse_email(email)
        self.assertGreaterEqual(len(jobs), 1)

    def test_missing_location(self):
        """Jobs with missing location should still be extracted."""
        email = self.emails[6]  # email_007_no_location
        jobs = parse_email(email)
        self.assertGreaterEqual(len(jobs), 1)

    def test_problem_email_skipped(self):
        """'Problem with your job alert' emails should yield zero jobs."""
        email = self.emails[7]  # email_008_problem
        jobs = parse_email(email)
        self.assertEqual(len(jobs), 0)


class TestLinkedInURLParsing(unittest.TestCase):
    """Test LinkedIn URL parsing utilities."""

    def test_extract_job_id_standard(self):
        self.assertEqual(
            extract_linkedin_job_id("https://www.linkedin.com/jobs/view/3912345678/"),
            "3912345678",
        )

    def test_extract_job_id_with_tracking(self):
        self.assertEqual(
            extract_linkedin_job_id(
                "https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=abc"
            ),
            "3912345678",
        )

    def test_extract_job_id_current_job(self):
        self.assertEqual(
            extract_linkedin_job_id("https://linkedin.com/jobs?currentJobId=3912345678"),
            "3912345678",
        )

    def test_clean_url(self):
        cleaned = clean_linkedin_url(
            "https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=abc&utm_source=email"
        )
        self.assertEqual(cleaned, "https://www.linkedin.com/jobs/view/3912345678/")

    def test_empty_url(self):
        self.assertIsNone(extract_linkedin_job_id(""))
        self.assertIsNone(extract_linkedin_job_id(None))


class TestDeduplication(unittest.TestCase):
    """Test job deduplication logic."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        init_database(self.db_path)
        self.conn = get_connection(self.db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_insert_new_job(self):
        job_id = insert_job(self.conn, {
            "linkedin_job_id": "111",
            "title": "Embedded Engineer",
            "company": "TestCo",
            "location": "Berlin",
        })
        self.assertIsNotNone(job_id)

    def test_duplicate_linkedin_id_rejected(self):
        insert_job(self.conn, {
            "linkedin_job_id": "222",
            "title": "Embedded Engineer",
            "company": "TestCo",
        })
        result = insert_job(self.conn, {
            "linkedin_job_id": "222",
            "title": "Different Title",
            "company": "DifferentCo",
        })
        self.assertIsNone(result)

    def test_duplicate_dedup_key_rejected(self):
        insert_job(self.conn, {
            "title": "AUTOSAR Developer",
            "company": "Continental AG",
            "location": "Frankfurt",
        })
        result = insert_job(self.conn, {
            "title": "AUTOSAR Developer",
            "company": "Continental AG",
            "location": "Frankfurt",
        })
        self.assertIsNone(result)

    def test_normalize_text(self):
        self.assertEqual(normalize_text("  Continental  AG  "), "continental")
        self.assertEqual(normalize_text("Bosch GmbH"), "bosch")
        self.assertEqual(normalize_text("Example Ltd."), "example")

    def test_email_processing_tracking(self):
        log_processed_email(self.conn, "email_001", "Test Subject", 3)
        self.assertTrue(is_email_processed(self.conn, "email_001"))
        self.assertFalse(is_email_processed(self.conn, "email_999"))


class TestAIResponseParsing(unittest.TestCase):
    """Test AI response parsing and validation."""

    def test_parse_json_in_code_fence(self):
        response = '```json\n{"fit_score": 85, "decision": "APPLY"}\n```'
        result = parse_ai_response(response)
        self.assertEqual(result["fit_score"], 85)

    def test_parse_raw_json(self):
        response = '{"fit_score": 70, "decision": "REVIEW"}'
        result = parse_ai_response(response)
        self.assertEqual(result["decision"], "REVIEW")

    def test_parse_json_with_surrounding_text(self):
        response = 'Here is my analysis:\n{"fit_score": 50}\nHope this helps!'
        result = parse_ai_response(response)
        self.assertEqual(result["fit_score"], 50)

    def test_parse_invalid_json(self):
        result = parse_ai_response("This is not JSON at all")
        self.assertIsNone(result)

    def test_validate_complete_analysis(self):
        analysis = {
            "fit_score": 85, "technical_score": 88, "career_score": 82,
            "relocation_score": 75, "visa_score": 60, "decision": "APPLY",
            "matched_skills": ["C"], "missing_required_skills": [],
            "missing_optional_skills": [], "experience_match": "STRONG",
            "language_constraints": "NONE", "location_constraints": "NONE",
            "visa_sponsorship": "UNKNOWN", "relocation": "LIKELY",
            "risk_flags": [], "explanation": "Good match.",
            "recommended_cv_focus": [], "recommended_keywords": [],
        }
        is_valid, errors = validate_analysis(analysis)
        self.assertTrue(is_valid, f"Validation errors: {errors}")

    def test_validate_missing_fields(self):
        analysis = {"fit_score": 85}
        is_valid, errors = validate_analysis(analysis)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_threshold_apply(self):
        analysis = {"fit_score": 85, "decision": "REVIEW"}
        result = apply_decision_thresholds(analysis)
        self.assertEqual(result["decision"], "APPLY")

    def test_threshold_skip(self):
        analysis = {"fit_score": 40, "decision": "APPLY"}
        result = apply_decision_thresholds(analysis)
        self.assertEqual(result["decision"], "SKIP")

    def test_extract_cv_markers(self):
        text = "blah\n---CV_START---\nCV content here\n---CV_END---\nmore"
        self.assertEqual(extract_cv_content(text), "CV content here")

    def test_extract_letter_markers(self):
        text = "---LETTER_START---\nDear Hiring Manager\n---LETTER_END---"
        self.assertEqual(extract_letter_content(text), "Dear Hiring Manager")


class TestATSDetection(unittest.TestCase):
    """Test ATS platform detection."""

    def test_workday(self):
        self.assertEqual(
            detect_ats_platform("https://continental.wd3.myworkdayjobs.com/external"),
            "Workday",
        )

    def test_greenhouse(self):
        self.assertEqual(
            detect_ats_platform("https://boards.greenhouse.io/company/jobs/123"),
            "Greenhouse",
        )

    def test_lever(self):
        self.assertEqual(
            detect_ats_platform("https://jobs.lever.co/company/abc-123"),
            "Lever",
        )

    def test_smartrecruiters(self):
        self.assertEqual(
            detect_ats_platform("https://jobs.smartrecruiters.com/Company/12345"),
            "SmartRecruiters",
        )

    def test_unknown_url(self):
        self.assertIsNone(detect_ats_platform("https://www.example.com/careers"))


class TestCareerProfile(unittest.TestCase):
    """Test career profile loading and structure."""

    def test_profile_loads(self):
        profile = load_career_profile()
        self.assertEqual(profile["candidate"]["full_name"], "Mohamed Almalky")

    def test_profile_immutable_flag(self):
        profile = load_career_profile()
        self.assertTrue(profile["immutable_master"])

    def test_profile_has_skill_levels(self):
        profile = load_career_profile()
        c_level = profile["skills"]["programming_languages"]["C"]["level"]
        self.assertEqual(c_level, "EXPERIENCE")

    def test_profile_has_relationships(self):
        profile = load_career_profile()
        comm_stack = profile["skill_relationships"]["AUTOSAR_Communication_Stack"]
        self.assertIn("COM", comm_stack)
        self.assertIn("PduR", comm_stack)


class TestSearchQueries(unittest.TestCase):
    """Test search query generation."""

    def test_careers_query(self):
        query = build_careers_search_query("Continental", "Embedded Engineer", "Frankfurt, Germany")
        self.assertIn("Continental", query)
        self.assertIn("careers", query)
        self.assertIn("Embedded Engineer", query)


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        init_database(self.db_path)
        self.conn = get_connection(self.db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_update_status(self):
        job_id = insert_job(self.conn, {
            "linkedin_job_id": "333",
            "title": "Test", "company": "Test",
        })
        update_job_status(self.conn, job_id, "ANALYZED")
        row = self.conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(row["status"], "ANALYZED")

    def test_update_analysis(self):
        job_id = insert_job(self.conn, {
            "linkedin_job_id": "444",
            "title": "Test", "company": "Test",
        })
        analysis = {
            "fit_score": 85, "technical_score": 90, "career_score": 80,
            "relocation_score": 70, "visa_score": 60, "decision": "APPLY",
            "visa_sponsorship": "LIKELY", "relocation": "LIKELY",
        }
        update_job_analysis(self.conn, job_id, analysis)
        row = self.conn.execute("SELECT fit_score, decision FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(row["fit_score"], 85)
        self.assertEqual(row["decision"], "APPLY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
