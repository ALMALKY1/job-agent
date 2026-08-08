"""
Mohamed Job Agent — Main Pipeline Orchestrator
================================================
Coordinates the entire daily job processing pipeline.
Can run standalone (using fixtures) or be triggered by n8n.
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from db_manager import (
    get_connection, init_database, insert_job, update_job_status,
    update_job_analysis, update_job_description, update_job_documents,
    get_jobs_by_status, log_daily_run, log_processed_email,
    is_email_processed,
)
from email_parser import parse_email
from ai_analyzer import (
    build_analysis_prompt, build_cv_prompt, build_motivation_prompt,
    parse_ai_response, validate_analysis, apply_decision_thresholds,
    extract_cv_content, extract_letter_content,
)
from job_retriever import create_retrieval_plan, parse_job_description_response
from doc_generator import generate_all_documents
from daily_report import generate_daily_report

# Load .env if available
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def process_emails(emails: list[dict], db_path: str = None) -> dict:
    """
    Phase 1: Parse emails and extract jobs.
    Returns statistics dict.
    """
    conn = get_connection(db_path)
    stats = {"total_emails": 0, "total_jobs": 0, "duplicates": 0, "new_jobs": 0}

    try:
        for email_data in emails:
            email_id = email_data.get("id", "")

            # Skip already processed emails
            if is_email_processed(conn, email_id):
                stats["duplicates"] += 1
                continue

            stats["total_emails"] += 1

            # Extract jobs from this email
            jobs = parse_email(email_data)
            extracted_count = 0

            for job in jobs:
                stats["total_jobs"] += 1
                row_id = insert_job(conn, {
                    "linkedin_job_id": job.get("linkedin_job_id"),
                    "title": job.get("job_title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "location": job.get("location", ""),
                    "workplace_type": job.get("workplace_type", ""),
                    "linkedin_url": job.get("linkedin_url", ""),
                    "source_email_id": email_id,
                })
                if row_id:
                    stats["new_jobs"] += 1
                    extracted_count += 1
                else:
                    stats["duplicates"] += 1

            # Log this email as processed
            log_processed_email(
                conn, email_id,
                email_data.get("subject", ""),
                extracted_count,
            )

        print(f"[Pipeline] Emails: {stats['total_emails']}, "
              f"Jobs found: {stats['total_jobs']}, "
              f"New: {stats['new_jobs']}, "
              f"Duplicates: {stats['duplicates']}")
    finally:
        conn.close()

    return stats


def analyze_jobs_mock(db_path: str = None) -> dict:
    """
    Phase 2 (Mock): Analyze jobs without actual OpenAI calls.
    In production, n8n handles OpenAI integration.

    This mock demonstrates the pipeline flow and data structure.
    """
    conn = get_connection(db_path)
    stats = {"analyzed": 0, "skipped": 0, "shortlisted": 0, "review": 0}

    try:
        new_jobs = get_jobs_by_status(conn, "NEW")
        print(f"[Pipeline] {len(new_jobs)} new jobs to analyze")

        for job in new_jobs:
            # Build the prompt (for demonstration / n8n export)
            prompt = build_analysis_prompt(job)

            # Mock analysis based on title keywords
            title_lower = (job.get("title") or "").lower()
            company_lower = (job.get("company") or "").lower()

            # Simple heuristic scoring for testing
            score = 50  # baseline
            if any(kw in title_lower for kw in ["embedded", "autosar", "ecu", "bsw"]):
                score += 25
            if any(kw in title_lower for kw in ["firmware", "diagnostics", "can"]):
                score += 15
            if any(kw in title_lower for kw in ["marketing", "sales", "hr", "finance"]):
                score -= 40
            if any(kw in (job.get("location") or "").lower()
                   for kw in ["germany", "netherlands", "sweden", "austria"]):
                score += 10

            score = max(0, min(100, score))

            mock_analysis = {
                "fit_score": score,
                "technical_score": score + 5 if score > 50 else score - 5,
                "career_score": score,
                "relocation_score": 70,
                "visa_score": 50,
                "decision": "APPLY" if score >= 80 else ("REVIEW" if score >= 65 else "SKIP"),
                "matched_skills": ["C", "AUTOSAR"] if score >= 65 else [],
                "missing_required_skills": [],
                "missing_optional_skills": [],
                "experience_match": "STRONG" if score >= 80 else "ADEQUATE",
                "language_constraints": "NONE",
                "location_constraints": "NONE",
                "visa_sponsorship": "UNKNOWN",
                "relocation": "LIKELY",
                "risk_flags": [],
                "explanation": f"Mock analysis. Score: {score}. Title: {job.get('title')}",
                "recommended_cv_focus": ["AUTOSAR", "Embedded C", "CAN"],
                "recommended_keywords": ["AUTOSAR", "embedded", "CAN"],
            }

            mock_analysis = apply_decision_thresholds(mock_analysis)
            update_job_analysis(conn, job["id"], mock_analysis)

            decision = mock_analysis["decision"]
            if decision == "APPLY":
                update_job_status(conn, job["id"], "SHORTLISTED")
                stats["shortlisted"] += 1
            elif decision == "REVIEW":
                stats["review"] += 1
            else:
                update_job_status(conn, job["id"], "SKIPPED")
                stats["skipped"] += 1

            stats["analyzed"] += 1

        print(f"[Pipeline] Analyzed: {stats['analyzed']}, "
              f"Shortlisted: {stats['shortlisted']}, "
              f"Review: {stats['review']}, "
              f"Skipped: {stats['skipped']}")
    finally:
        conn.close()

    return stats


def generate_documents_mock(db_path: str = None) -> dict:
    """
    Phase 3 (Mock): Generate documents for shortlisted jobs.
    In production, n8n handles OpenAI-based generation.
    """
    conn = get_connection(db_path)
    stats = {"documents_generated": 0}

    try:
        shortlisted = get_jobs_by_status(conn, "SHORTLISTED")
        print(f"[Pipeline] {len(shortlisted)} shortlisted jobs need documents")

        for job in shortlisted:
            analysis = json.loads(job.get("analysis_json", "{}"))

            # Mock CV content
            cv_content = f"""# Mohamed Almalky
## Embedded Software Engineer

### Professional Summary
Embedded Software Engineer with 5+ years of automotive experience,
specializing in AUTOSAR Classic BSW configuration and integration.

### Tailored for: {job.get('title')} at {job.get('company')}

### Technical Skills
- Embedded C, C++
- AUTOSAR Classic: {', '.join(analysis.get('recommended_keywords', []))}
- Tools: DaVinci Developer, DaVinci Configurator, CANoe
"""

            # Mock Motivation Letter
            letter_content = f"""Dear Hiring Manager,

I am writing to express my interest in the {job.get('title')} position
at {job.get('company')} in {job.get('location', 'Europe')}.

With over 5 years of experience in embedded automotive software development,
including extensive work with AUTOSAR Classic BSW modules, I am confident
in my ability to contribute effectively to your team.

I am particularly drawn to this opportunity because of the alignment with
my experience in {', '.join(analysis.get('matched_skills', ['AUTOSAR', 'embedded C'])[:3])}.

I am fully prepared to relocate and look forward to the opportunity to
discuss how my background aligns with your requirements.

Best regards,
Mohamed Almalky
"""

            docs = generate_all_documents(
                job, analysis, cv_content, letter_content,
            )

            update_job_documents(
                conn, job["id"],
                cv_file=docs.get("cv_docx") or docs.get("cv_txt"),
                motivation_file=docs.get("motivation_docx") or docs.get("motivation_txt"),
            )
            stats["documents_generated"] += 1

        print(f"[Pipeline] Documents generated: {stats['documents_generated']}")
    finally:
        conn.close()

    return stats


def run_daily_pipeline(emails: list[dict] = None, db_path: str = None) -> dict:
    """
    Run the complete daily pipeline.

    If no emails provided, loads from test fixtures.
    """
    # Initialize database
    init_database(db_path)

    # Load test fixtures if no emails provided
    if emails is None:
        fixtures_path = PROJECT_ROOT / "tests" / "fixtures" / "sample_emails.json"
        with open(fixtures_path) as f:
            emails = json.load(f)
        print(f"[Pipeline] Loaded {len(emails)} fixture emails")

    # Log the run
    conn = get_connection(db_path)
    run_id = log_daily_run(conn, {"run_date": date.today().isoformat()})
    conn.close()

    # Phase 1: Email processing
    print("\n" + "=" * 50)
    print("PHASE 1: Email Processing")
    print("=" * 50)
    email_stats = process_emails(emails, db_path)

    # Phase 2: Job analysis
    print("\n" + "=" * 50)
    print("PHASE 2: Job Analysis (Mock)")
    print("=" * 50)
    analysis_stats = analyze_jobs_mock(db_path)

    # Phase 3: Document generation
    print("\n" + "=" * 50)
    print("PHASE 3: Document Generation (Mock)")
    print("=" * 50)
    doc_stats = generate_documents_mock(db_path)

    # Phase 4: Daily report
    print("\n" + "=" * 50)
    print("PHASE 4: Daily Report")
    print("=" * 50)
    report = generate_daily_report(db_path=db_path)

    # Update run log
    conn = get_connection(db_path)
    conn.execute(
        """UPDATE daily_runs SET
           completed_at = datetime('now'),
           total_emails = ?, total_jobs_found = ?,
           duplicates_removed = ?, jobs_analyzed = ?,
           jobs_skipped = ?, jobs_review = ?,
           jobs_shortlisted = ?, documents_generated = ?,
           status = 'COMPLETED'
           WHERE id = ?""",
        (
            email_stats["total_emails"],
            email_stats["total_jobs"],
            email_stats["duplicates"],
            analysis_stats["analyzed"],
            analysis_stats["skipped"],
            analysis_stats["review"],
            analysis_stats["shortlisted"],
            doc_stats["documents_generated"],
            run_id,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "email_stats": email_stats,
        "analysis_stats": analysis_stats,
        "doc_stats": doc_stats,
    }


if __name__ == "__main__":
    print("🚀 Mohamed Job Agent — Daily Pipeline")
    print(f"   Date: {date.today().isoformat()}")
    print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
    print()
    results = run_daily_pipeline()
    print("\n✅ Pipeline completed successfully!")
    print(json.dumps(results, indent=2))
