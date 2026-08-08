"""
Mohamed Job Agent — Database Manager
=====================================
Manages the SQLite database for job tracking, deduplication, and reporting.
"""

import sqlite3
import json
import os
import re
from datetime import datetime, date
from pathlib import Path

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DB_PATH", str(PROJECT_ROOT / "data" / "jobs.db"))
SCHEMA_PATH = PROJECT_ROOT / "config" / "schema.sql"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: str = None) -> None:
    """Initialize the database from the schema file."""
    conn = get_connection(db_path)
    try:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
        conn.commit()
        print(f"[OK] Database initialized at {db_path or DB_PATH}")
    finally:
        conn.close()


def normalize_text(text: str) -> str:
    """Normalize text for deduplication: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # Remove common suffixes/noise
    for suffix in [" inc", " inc.", " ltd", " ltd.", " gmbh", " ag", " se", " b.v.", " bv"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def make_dedup_key(company: str, title: str, location: str = "") -> str:
    """Create a fallback dedup key from normalized company+title+location."""
    parts = [normalize_text(company), normalize_text(title), normalize_text(location or "")]
    return "|".join(parts)


def job_exists(conn: sqlite3.Connection, linkedin_job_id: str = None,
               company: str = None, title: str = None, location: str = None) -> bool:
    """Check if a job already exists (by LinkedIn ID or dedup key)."""
    if linkedin_job_id:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE linkedin_job_id = ?", (linkedin_job_id,)
        ).fetchone()
        if row:
            return True

    if company and title:
        dedup = make_dedup_key(company, title, location)
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE dedup_key = ?", (dedup,)
        ).fetchone()
        if row:
            return True

    return False


def insert_job(conn: sqlite3.Connection, job_data: dict) -> int | None:
    """
    Insert a new job. Returns the row id, or None if duplicate.

    job_data keys:
        linkedin_job_id, title, company, location, workplace_type,
        linkedin_url, source_email_id, source
    """
    linkedin_job_id = job_data.get("linkedin_job_id")
    company = job_data.get("company", "")
    title = job_data.get("title", "")
    location = job_data.get("location", "")

    if job_exists(conn, linkedin_job_id, company, title, location):
        return None

    dedup_key = make_dedup_key(company, title, location)

    # If dedup_key is trivial (all empty parts), make it unique
    if dedup_key.replace("|", "").strip() == "":
        if linkedin_job_id:
            dedup_key = f"linkedin|{linkedin_job_id}"
        else:
            # Generate a unique key from URL or a counter
            url = job_data.get("linkedin_url", "")
            import hashlib
            dedup_key = f"auto|{hashlib.md5((title + company + url).encode()).hexdigest()}"

    try:
        cursor = conn.execute(
            """
            INSERT INTO jobs (
                linkedin_job_id, dedup_key, title, company, location,
                workplace_type, linkedin_url, source, source_email_id,
                discovered_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'NEW')
            """,
            (
                linkedin_job_id,
                dedup_key,
                title,
                company,
                location,
                job_data.get("workplace_type"),
                job_data.get("linkedin_url"),
                job_data.get("source", "linkedin_email"),
                job_data.get("source_email_id"),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Duplicate detected at DB level
        return None


def update_job_status(conn: sqlite3.Connection, job_id: int, status: str, **kwargs) -> None:
    """Update job status and optional additional fields."""
    fields = ["status = ?", "updated_at = datetime('now')"]
    values = [status]
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def update_job_analysis(conn: sqlite3.Connection, job_id: int, analysis: dict) -> None:
    """Store AI analysis results for a job."""
    conn.execute(
        """
        UPDATE jobs SET
            fit_score = ?, technical_score = ?, career_score = ?,
            relocation_score = ?, visa_score = ?,
            decision = ?, analysis_json = ?,
            visa_sponsorship = ?, relocation_support = ?,
            status = ?, analyzed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            analysis.get("fit_score"),
            analysis.get("technical_score"),
            analysis.get("career_score"),
            analysis.get("relocation_score"),
            analysis.get("visa_score"),
            analysis.get("decision"),
            json.dumps(analysis),
            analysis.get("visa_sponsorship"),
            analysis.get("relocation"),
            "ANALYZED",
            job_id,
        ),
    )
    conn.commit()


def update_job_description(conn: sqlite3.Connection, job_id: int,
                           description_data: dict) -> None:
    """Store retrieved job description data."""
    conn.execute(
        """
        UPDATE jobs SET
            full_description = ?, requirements = ?,
            preferred_qualifications = ?, language_requirements = ?,
            experience_requirements = ?, visa_information = ?,
            relocation_information = ?, description_source = ?,
            official_url = ?, ats_platform = ?,
            status = 'FETCHING', updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            description_data.get("full_description"),
            description_data.get("requirements"),
            description_data.get("preferred_qualifications"),
            description_data.get("language_requirements"),
            description_data.get("experience_requirements"),
            description_data.get("visa_information"),
            description_data.get("relocation_information"),
            description_data.get("description_source"),
            description_data.get("official_url"),
            description_data.get("ats_platform"),
            job_id,
        ),
    )
    conn.commit()


def update_job_documents(conn: sqlite3.Connection, job_id: int,
                         cv_file: str = None, motivation_file: str = None,
                         application_answers: str = None) -> None:
    """Store generated document paths."""
    conn.execute(
        """
        UPDATE jobs SET
            cv_file = COALESCE(?, cv_file),
            motivation_file = COALESCE(?, motivation_file),
            application_answers = COALESCE(?, application_answers),
            status = 'DOCUMENTS_READY',
            documents_generated_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (cv_file, motivation_file, application_answers, job_id),
    )
    conn.commit()


def get_jobs_by_status(conn: sqlite3.Connection, status: str) -> list[dict]:
    """Get all jobs with a given status."""
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = ? ORDER BY discovered_at DESC", (status,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_jobs_for_report(conn: sqlite3.Connection, since_date: str = None) -> dict:
    """Get job statistics for the daily report."""
    if since_date is None:
        since_date = date.today().isoformat()

    stats = {}

    stats["total_jobs"] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE date(discovered_at) = ?", (since_date,)
    ).fetchone()[0]

    stats["duplicates_removed"] = 0  # Tracked during insertion

    for status in ["ANALYZED", "SKIPPED", "SHORTLISTED", "DOCUMENTS_READY", "READY_TO_APPLY"]:
        key = f"jobs_{status.lower()}"
        stats[key] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = ? AND date(discovered_at) = ?",
            (status, since_date),
        ).fetchone()[0]

    stats["strong_matches"] = conn.execute(
        """
        SELECT * FROM jobs
        WHERE decision = 'APPLY' AND date(discovered_at) = ?
        ORDER BY fit_score DESC
        """,
        (since_date,),
    ).fetchall()
    stats["strong_matches"] = [dict(r) for r in stats["strong_matches"]]

    stats["review_jobs"] = conn.execute(
        """
        SELECT * FROM jobs
        WHERE decision = 'REVIEW' AND date(discovered_at) = ?
        ORDER BY fit_score DESC
        """,
        (since_date,),
    ).fetchall()
    stats["review_jobs"] = [dict(r) for r in stats["review_jobs"]]

    return stats


def log_daily_run(conn: sqlite3.Connection, run_data: dict) -> int:
    """Log a daily run entry."""
    cursor = conn.execute(
        """
        INSERT INTO daily_runs (
            run_date, total_emails, total_jobs_found, duplicates_removed,
            jobs_analyzed, jobs_skipped, jobs_review, jobs_shortlisted,
            documents_generated, errors, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_data.get("run_date", date.today().isoformat()),
            run_data.get("total_emails", 0),
            run_data.get("total_jobs_found", 0),
            run_data.get("duplicates_removed", 0),
            run_data.get("jobs_analyzed", 0),
            run_data.get("jobs_skipped", 0),
            run_data.get("jobs_review", 0),
            run_data.get("jobs_shortlisted", 0),
            run_data.get("documents_generated", 0),
            run_data.get("errors", 0),
            run_data.get("status", "RUNNING"),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def log_processed_email(conn: sqlite3.Connection, email_id: str,
                        subject: str, jobs_extracted: int) -> None:
    """Record that an email has been processed."""
    conn.execute(
        """
        INSERT OR IGNORE INTO processed_emails (email_id, subject, jobs_extracted)
        VALUES (?, ?, ?)
        """,
        (email_id, subject, jobs_extracted),
    )
    conn.commit()


def is_email_processed(conn: sqlite3.Connection, email_id: str) -> bool:
    """Check if an email has already been processed."""
    row = conn.execute(
        "SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,)
    ).fetchone()
    return row is not None


if __name__ == "__main__":
    init_database()
