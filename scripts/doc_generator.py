"""
Mohamed Job Agent — Document Generator
========================================
Generates CV, Motivation Letter, and application documents.
Uses python-docx for DOCX creation.
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = PROJECT_ROOT / "generated"
CV_DIR = GENERATED_DIR / "cv"
MOTIVATION_DIR = GENERATED_DIR / "motivation"
APPLICATIONS_DIR = GENERATED_DIR / "applications"

# Ensure directories exist
for d in [CV_DIR, MOTIVATION_DIR, APPLICATIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def sanitize_filename(text: str) -> str:
    """Create a safe filename from text."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:50]


def generate_filename(company: str, job_id: str, doc_type: str, ext: str) -> str:
    """Generate standardized filename: Mohamed_Almalky_<Company>_<JobID>_<Type>.<ext>"""
    company_clean = sanitize_filename(company)
    job_id_clean = sanitize_filename(job_id or "unknown")
    return f"Mohamed_Almalky_{company_clean}_{job_id_clean}_{doc_type}.{ext}"


def save_cv_text(content: str, company: str, job_id: str) -> dict:
    """Save CV content as text file (DOCX/PDF generation requires python-docx)."""
    txt_name = generate_filename(company, job_id, "CV", "txt")
    txt_path = CV_DIR / txt_name
    with open(txt_path, "w") as f:
        f.write(content)
    return {"txt": str(txt_path), "filename_base": txt_name.rsplit(".", 1)[0]}


def save_motivation_text(content: str, company: str, job_id: str) -> dict:
    """Save Motivation Letter content as text file."""
    txt_name = generate_filename(company, job_id, "Motivation", "txt")
    txt_path = MOTIVATION_DIR / txt_name
    with open(txt_path, "w") as f:
        f.write(content)
    return {"txt": str(txt_path), "filename_base": txt_name.rsplit(".", 1)[0]}


def save_application_answers(answers: dict, company: str, job_id: str) -> str:
    """Save application answers as JSON."""
    filename = generate_filename(company, job_id, "Answers", "json")
    filepath = APPLICATIONS_DIR / filename
    with open(filepath, "w") as f:
        json.dump(answers, f, indent=2)
    return str(filepath)


def generate_cv_docx(content: str, company: str, job_id: str) -> str:
    """
    Generate a DOCX CV file using python-docx.
    Returns the file path, or saves as txt if python-docx is unavailable.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Set default font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)

        # Parse content into sections
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                doc.add_paragraph("")
                continue
            # Detect section headers (lines in ALL CAPS or starting with ##)
            if line.startswith("## ") or line.startswith("# "):
                heading_text = line.lstrip("#").strip()
                doc.add_heading(heading_text, level=1 if line.startswith("# ") else 2)
            elif line.startswith("### "):
                doc.add_heading(line.lstrip("#").strip(), level=3)
            elif line.startswith("- ") or line.startswith("• "):
                doc.add_paragraph(line[2:].strip(), style="List Bullet")
            else:
                doc.add_paragraph(line)

        docx_name = generate_filename(company, job_id, "CV", "docx")
        docx_path = CV_DIR / docx_name
        doc.save(str(docx_path))
        return str(docx_path)

    except ImportError:
        # Fallback to text
        result = save_cv_text(content, company, job_id)
        return result["txt"]


def generate_motivation_docx(content: str, company: str, job_id: str) -> str:
    """Generate a DOCX Motivation Letter."""
    try:
        from docx import Document
        from docx.shared import Pt

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

        # Add date
        date_para = doc.add_paragraph(datetime.now().strftime("%B %d, %Y"))
        doc.add_paragraph("")

        # Add content paragraphs
        for para in content.split("\n\n"):
            para = para.strip()
            if para:
                doc.add_paragraph(para)

        docx_name = generate_filename(company, job_id, "Motivation", "docx")
        docx_path = MOTIVATION_DIR / docx_name
        doc.save(str(docx_path))
        return str(docx_path)

    except ImportError:
        result = save_motivation_text(content, company, job_id)
        return result["txt"]


def generate_all_documents(job: dict, analysis: dict,
                           cv_content: str, letter_content: str,
                           answers: dict = None) -> dict:
    """
    Generate all application documents for a job.

    Returns dict with file paths for each document.
    """
    company = job.get("company", "Unknown")
    job_id = job.get("linkedin_job_id", job.get("id", "unknown"))

    result = {
        "cv_txt": None, "cv_docx": None,
        "motivation_txt": None, "motivation_docx": None,
        "answers_json": None,
    }

    # CV
    if cv_content:
        txt_result = save_cv_text(cv_content, company, job_id)
        result["cv_txt"] = txt_result["txt"]
        result["cv_docx"] = generate_cv_docx(cv_content, company, job_id)

    # Motivation Letter
    if letter_content:
        txt_result = save_motivation_text(letter_content, company, job_id)
        result["motivation_txt"] = txt_result["txt"]
        result["motivation_docx"] = generate_motivation_docx(letter_content, company, job_id)

    # Application Answers
    if answers:
        result["answers_json"] = save_application_answers(answers, company, job_id)

    return result


if __name__ == "__main__":
    # Test document generation
    test_cv = """# Mohamed Almalky
## Professional Summary
Embedded Software Engineer with 5+ years of automotive experience.

## Technical Skills
- C, C++
- AUTOSAR Classic (COM, PduR, DCM, DEM)
- CAN, UDS, OBD

## Professional Experience
### Valeo Egypt — Embedded Software Engineer
- Configured and integrated AUTOSAR BSW modules
- Developed diagnostic services using UDS/DCM
"""
    result = save_cv_text(test_cv, "Continental", "3912345678")
    print(f"CV saved: {result}")
