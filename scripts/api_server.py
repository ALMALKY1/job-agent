"""
Mohamed Job Agent — Worker API Server (FastAPI)
================================================
Exposes lightweight HTTP endpoints for n8n and orchestrators.
Reuses existing python modules without duplicating business logic.
"""

import os
import sys
import shutil
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from db_manager import (
    get_connection, init_database, insert_job, update_job_status,
    update_job_analysis, update_job_description, update_job_documents,
    get_jobs_by_status, get_job_by_id, log_daily_run, log_processed_email,
    is_email_processed,
)
from email_parser import parse_email
from job_retriever import parse_job_description_response, detect_ats_platform
from ai_analyzer import (
    build_analysis_prompt, build_ats_analysis_prompt, build_cv_prompt,
    build_motivation_prompt, parse_ai_response, validate_analysis,
    apply_decision_thresholds,
)
from doc_generator import generate_all_documents
from ats_validator import validate_cv_pdf, validate_motivation_pdf
from daily_report import generate_daily_report, get_daily_summary

app = FastAPI(
    title="Mohamed Job Agent Worker API",
    description="Worker service for job parsing, AI analysis prompts, ATS document generation, and validation.",
    version="1.0.0",
)


# Initialize DB on startup
@app.on_event("startup")
def startup_db():
    init_database()


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class ParseEmailRequest(BaseModel):
    id: Optional[str] = "email_001"
    subject: Optional[str] = ""
    sender: Optional[str] = ""
    from_addr: Optional[str] = Field(default="", alias="from")
    body_html: Optional[str] = None
    body_text: Optional[str] = None


class ProcessJobRequest(BaseModel):
    linkedin_job_id: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = ""
    workplace_type: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    official_url: Optional[str] = ""
    source_email_id: Optional[str] = ""
    full_description: Optional[str] = None
    requirements: Optional[str] = None
    preferred_qualifications: Optional[str] = None
    ats_platform: Optional[str] = None


class FetchDescriptionRequest(BaseModel):
    job_id: int
    raw_html_or_text: Optional[str] = None
    official_url: Optional[str] = None
    description_source: Optional[str] = "LinkedIn"


class AnalyzeJobRequest(BaseModel):
    job_id: Optional[int] = None
    job: Optional[Dict[str, Any]] = None


class SaveAnalysisRequest(BaseModel):
    job_id: int
    analysis: Dict[str, Any]


class GenerateDocumentsRequest(BaseModel):
    job_id: Optional[int] = None
    job: Optional[Dict[str, Any]] = None
    cv_content: Optional[str] = None
    letter_content: Optional[str] = None
    ats_keywords: Optional[Dict[str, Any]] = None
    answers: Optional[Dict[str, Any]] = None


class ValidatePDFRequest(BaseModel):
    pdf_path: str
    ats_keywords: Optional[Dict[str, Any]] = None
    doc_type: Optional[str] = "CV"  # "CV" or "Motivation"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Verify worker health and system dependencies."""
    libreoffice_available = shutil.which("libreoffice") is not None
    pdftotext_available = shutil.which("pdftotext") is not None

    db_ok = False
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    status = "ok" if (libreoffice_available and pdftotext_available and db_ok) else "degraded"

    return {
        "status": status,
        "service": "job-worker",
        "libreoffice": libreoffice_available,
        "pdftotext": pdftotext_available,
        "database": db_ok,
    }


@app.post("/parse-email")
def parse_email_endpoint(payload: ParseEmailRequest):
    """Parse a single LinkedIn alert email and return extracted jobs."""
    email_data = payload.model_dump()
    if not email_data.get("from"):
        email_data["from"] = payload.from_addr or payload.sender or "jobs-noreply@linkedin.com"
    if not email_data.get("html"):
        email_data["html"] = payload.body_html or ""
    if not email_data.get("text"):
        email_data["text"] = payload.body_text or ""
    conn = get_connection()
    try:
        email_id = payload.id or ""
        if email_id and is_email_processed(conn, email_id):
            return {
                "email_id": email_id,
                "already_processed": True,
                "extracted_jobs": [],
                "count": 0,
            }

        jobs = parse_email(email_data)
        new_jobs_inserted = 0

        for job in jobs:
            job_dict = {
                "linkedin_job_id": job.get("linkedin_job_id"),
                "title": job.get("job_title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "location": job.get("location", ""),
                "workplace_type": job.get("workplace_type", ""),
                "linkedin_url": job.get("linkedin_url", ""),
                "source_email_id": email_id,
            }
            row_id = insert_job(conn, job_dict)
            if row_id:
                new_jobs_inserted += 1

        if email_id:
            log_processed_email(conn, email_id, payload.subject or "", len(jobs))

        return {
            "email_id": email_id,
            "already_processed": False,
            "extracted_jobs": jobs,
            "count": len(jobs),
            "new_inserted": new_jobs_inserted,
        }
    finally:
        conn.close()


@app.post("/process-job")
def process_job_endpoint(payload: ProcessJobRequest):
    """Insert or update a job in the SQLite tracker database."""
    conn = get_connection()
    try:
        job_data = payload.model_dump()
        row_id = insert_job(conn, job_data)
        if not row_id and payload.linkedin_job_id:
            row = conn.execute(
                "SELECT id FROM jobs WHERE linkedin_job_id = ?",
                (payload.linkedin_job_id,),
            ).fetchone()
            row_id = row["id"] if row else None

        if row_id and payload.full_description:
            update_job_description(conn, row_id, {
                "full_description": payload.full_description,
                "requirements": payload.requirements,
                "preferred_qualifications": payload.preferred_qualifications,
                "official_url": payload.official_url,
                "ats_platform": payload.ats_platform,
            })

        return {
            "job_id": row_id,
            "inserted": bool(row_id),
            "status": "FETCHED" if payload.full_description else "NEW",
        }
    finally:
        conn.close()


@app.post("/fetch-description")
def fetch_description_endpoint(payload: FetchDescriptionRequest):
    """
    Parse and store full job description.
    If full_description text is missing or empty, sets status = 'JD_RETRIEVAL_INCOMPLETE'.
    """
    conn = get_connection()
    try:
        job = get_job_by_id(conn, payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found")

        raw_text = payload.raw_html_or_text or job.get("full_description") or ""
        parsed = parse_job_description_response(raw_text)
        full_desc = parsed.get("full_description", "").strip()

        if payload.official_url:
            parsed["official_url"] = payload.official_url
            parsed["ats_platform"] = detect_ats_platform(payload.official_url)
        if payload.description_source:
            parsed["description_source"] = payload.description_source

        if full_desc and len(full_desc) > 30:
            update_job_description(conn, payload.job_id, parsed)
            conn.execute("UPDATE jobs SET status = 'FETCHED' WHERE id = ?", (payload.job_id,))
            conn.commit()
            return {
                "job_id": payload.job_id,
                "status": "FETCHED",
                "full_description_length": len(full_desc),
                "is_complete": True,
            }
        else:
            update_job_status(conn, payload.job_id, "JD_RETRIEVAL_INCOMPLETE")
            return {
                "job_id": payload.job_id,
                "status": "JD_RETRIEVAL_INCOMPLETE",
                "full_description_length": 0,
                "is_complete": False,
            }
    finally:
        conn.close()


@app.post("/analyze-job")
def analyze_job_endpoint(payload: AnalyzeJobRequest):
    """
    Build AI analysis prompts for a job.
    Optionally updates the job record if analysis payload is returned.
    """
    job_data = payload.job
    conn = get_connection()
    try:
        if not job_data and payload.job_id:
            row = get_job_by_id(conn, payload.job_id)
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            job_data = dict(row)

        if not job_data:
            raise HTTPException(status_code=400, detail="Must provide job_id or job object")

        analysis_prompt = build_analysis_prompt(job_data)
        ats_prompt = build_ats_analysis_prompt(job_data)

        return {
            "job_id": payload.job_id or job_data.get("id"),
            "analysis_prompt": analysis_prompt,
            "ats_prompt": ats_prompt,
        }
    finally:
        conn.close()


@app.post("/save-analysis")
def save_analysis_endpoint(payload: SaveAnalysisRequest):
    """Store OpenAI job analysis JSON into the database."""
    conn = get_connection()
    try:
        update_job_analysis(conn, payload.job_id, payload.analysis)
        return {"job_id": payload.job_id, "status": "ANALYZED", "saved": True}
    finally:
        conn.close()


@app.post("/generate-documents")
def generate_documents_endpoint(payload: GenerateDocumentsRequest):
    """
    Full document generation pipeline:
    DOCX Generation → PDF Conversion → PDF ATS Validation → Storage
    """
    conn = get_connection()
    try:
        job = payload.job
        if not job and payload.job_id:
            row = get_job_by_id(conn, payload.job_id)
            if not row:
                raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found")
            job = dict(row)

        if not job:
            raise HTTPException(status_code=400, detail="Must provide job_id or job object")

        job_id = job.get("id") or payload.job_id
        analysis = json.loads(job.get("analysis_json", "{}")) if isinstance(job.get("analysis_json"), str) else (job.get("analysis_json") or {})

        ats_keywords = payload.ats_keywords or {
            "required": ["AUTOSAR", "Embedded C", "CAN", "UDS"],
            "preferred": ["Vector DaVinci", "CANoe", "Python"],
        }

        cv_content = payload.cv_content or f"""# Mohamed Almalky
Mohamed Almalky
Contact: mohamed@almalky.dev | Cairo, Egypt | Relocation Willing

## Professional Summary
Embedded Software Engineer with 5+ years of automotive experience,
specializing in AUTOSAR Classic BSW configuration, CAN communication stack, and UDS diagnostics.

## Technical Skills
- Programming: Embedded C, C++, Python
- Automotive Standards: AUTOSAR Classic (COM, PduR, CanIf, CanSM, DCM, DEM), CAN, UDS
- Tools: Vector DaVinci Configurator, DaVinci Developer, CANoe, Lauterbach TRACE32

## Professional Experience
### Embedded Software Engineer — Valeo Egypt
- Integrated and configured AUTOSAR BSW modules for European OEM projects
- Developed diagnostic services using Unified Diagnostic Services (UDS) and Controller Area Network (CAN)
- Tailored for: {job.get('title')} at {job.get('company')}

## Education
- B.Sc. in Electrical / Embedded Engineering
"""

        letter_content = payload.letter_content or f"""Mohamed Almalky
Mohamed Almalky
Cairo, Egypt

Dear Hiring Manager,

I am writing to express my interest in the {job.get('title')} position at {job.get('company')} in {job.get('location', 'Europe')}.

With over 5 years of experience in embedded automotive software development, including extensive work with AUTOSAR Classic BSW modules, CAN communication, and UDS diagnostics, I am confident in my ability to contribute effectively to your engineering team.

I am particularly drawn to this opportunity at {job.get('company')} because of the alignment with my technical background and experience.

I am fully prepared to relocate to {job.get('location', 'Europe')} and look forward to discussing how my skills match your requirements.

Sincerely,
Mohamed Almalky
"""

        docs = generate_all_documents(
            job=job,
            analysis=analysis,
            cv_content=cv_content,
            letter_content=letter_content,
            ats_keywords=ats_keywords,
            answers=payload.answers,
        )

        all_valid = docs.get("all_valid", False)
        validation_status = "PASSED" if all_valid else "FAILED"
        status = "DOCUMENTS_READY" if all_valid else "FAILED"

        if job_id:
            update_job_documents(
                conn,
                job_id=job_id,
                cv_file=docs.get("cv_docx"),
                cv_pdf_file=docs.get("cv_pdf"),
                motivation_file=docs.get("motivation_docx"),
                motivation_pdf_file=docs.get("motivation_pdf"),
                application_answers=docs.get("answers_json"),
                ats_score=docs.get("cv_ats_score", 0),
                ats_keywords_found=docs.get("cv_ats_keywords_found", []),
                ats_keywords_missing=docs.get("cv_ats_keywords_missing", []),
                pdf_validation_status=validation_status,
                ats_analysis=ats_keywords,
                status=status,
            )

        return {
            "job_id": job_id,
            "status": status,
            "pdf_validation_status": validation_status,
            "all_valid": all_valid,
            "documents": docs,
        }
    finally:
        conn.close()


@app.post("/validate-pdf")
def validate_pdf_endpoint(payload: ValidatePDFRequest):
    """Validate a PDF file for ATS readability and keyword presence."""
    pdf_path = payload.pdf_path
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")

    if payload.doc_type.upper() == "CV":
        result = validate_cv_pdf(pdf_path, payload.ats_keywords)
    else:
        result = validate_motivation_pdf(pdf_path)

    return result


@app.post("/daily-report")
def daily_report_endpoint():
    """Generate daily report text and metrics summary."""
    report_text = generate_daily_report()
    summary = get_daily_summary()

    return {
        "report": report_text,
        "summary": summary,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
