"""
Mohamed Job Agent — Document Generator (ATS-Optimized)
=======================================================
Generates ATS-optimized CVs and Motivation Letters.

Pipeline:
    Job Description → ATS Analysis → Tailored Content
    → DOCX Generation → PDF Conversion → ATS Validation
    → Final PDF Files

DOCX is the intermediate format; PDF is the final artifact.
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = PROJECT_ROOT / "generated"
CV_DIR = GENERATED_DIR / "cv"
MOTIVATION_DIR = GENERATED_DIR / "motivation"
APPLICATIONS_DIR = GENERATED_DIR / "applications"

# Ensure directories exist
for d in [CV_DIR, MOTIVATION_DIR, APPLICATIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Filename Utilities
# ---------------------------------------------------------------------------

def sanitize_filename(text: str) -> str:
    """Create a safe filename from text."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:50]


def generate_filename(company: str, job_id: str, doc_type: str, ext: str) -> str:
    """
    Generate standardized filename.

    Format: Mohamed_Almalky_<Company>_<JobID>_<Type>.<ext>
    """
    company_clean = sanitize_filename(company)
    job_id_clean = sanitize_filename(str(job_id) if job_id else "unknown")
    return f"Mohamed_Almalky_{company_clean}_{job_id_clean}_{doc_type}.{ext}"


# ---------------------------------------------------------------------------
# ATS-Optimized DOCX Generation
# ---------------------------------------------------------------------------

def generate_cv_docx(content: str, company: str, job_id: str) -> str:
    """
    Generate an ATS-optimized CV as DOCX.

    ATS Rules enforced:
    - Single-column layout
    - No text boxes, graphics, icons, or skill bars
    - No photos
    - Standard section headings
    - Standard readable font (Calibri)
    - Simple bullet points
    - All text selectable and machine-readable
    """
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # -- Page margins (standard ATS-safe: 1 inch / 2.54 cm) --
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    # -- Default style: Calibri 11pt --
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    paragraph_format = style.paragraph_format
    paragraph_format.space_after = Pt(4)
    paragraph_format.space_before = Pt(0)

    # -- Heading styles --
    for level in [1, 2, 3]:
        heading_style = doc.styles[f"Heading {level}"]
        heading_style.font.name = "Calibri"
        heading_style.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
        heading_style.paragraph_format.space_before = Pt(12 if level == 1 else 8)
        heading_style.paragraph_format.space_after = Pt(4)
        if level == 1:
            heading_style.font.size = Pt(16)
        elif level == 2:
            heading_style.font.size = Pt(13)
            heading_style.font.bold = True
        else:
            heading_style.font.size = Pt(11)
            heading_style.font.bold = True

    # -- Parse markdown-style content into DOCX --
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Heading 1: "# Title"
        if stripped.startswith("# ") and not stripped.startswith("## "):
            text = stripped[2:].strip()
            para = doc.add_heading(text, level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Heading 2: "## Section"
        elif stripped.startswith("## "):
            text = stripped[3:].strip()
            heading = doc.add_heading(text.upper(), level=2)
            # Add a subtle bottom border via a thin line
            _add_heading_border(heading)

        # Heading 3: "### Sub-section"
        elif stripped.startswith("### "):
            text = stripped[4:].strip()
            doc.add_heading(text, level=3)

        # Bullet point: "- " or "• "
        elif stripped.startswith("- ") or stripped.startswith("• "):
            text = stripped[2:].strip()
            para = doc.add_paragraph(style="List Bullet")
            _add_formatted_text(para, text)

        # Bold line: "**text**"
        elif stripped.startswith("**") and stripped.endswith("**"):
            text = stripped[2:-2].strip()
            para = doc.add_paragraph()
            run = para.add_run(text)
            run.bold = True

        # Regular paragraph
        else:
            para = doc.add_paragraph()
            _add_formatted_text(para, stripped)

        i += 1

    # -- Save DOCX --
    docx_name = generate_filename(company, job_id, "CV", "docx")
    docx_path = CV_DIR / docx_name
    doc.save(str(docx_path))
    return str(docx_path)


def generate_motivation_docx(content: str, company: str, job_id: str) -> str:
    """
    Generate an ATS-safe Motivation Letter as DOCX.

    Simple, professional letter format.
    """
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Default style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = Pt(16)

    # Date
    date_para = doc.add_paragraph(datetime.now().strftime("%B %d, %Y"))
    date_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph("")  # spacer

    # Content paragraphs
    paragraphs = content.split("\n\n")
    for para_text in paragraphs:
        para_text = para_text.strip()
        if not para_text:
            continue
        # Handle single newlines within a paragraph
        para_text = para_text.replace("\n", " ")
        para = doc.add_paragraph()
        _add_formatted_text(para, para_text)

    # Closing
    doc.add_paragraph("")
    closing = doc.add_paragraph("Mohamed Almalky")
    closing.runs[0].bold = True

    # Save
    docx_name = generate_filename(company, job_id, "Motivation_Letter", "docx")
    docx_path = MOTIVATION_DIR / docx_name
    doc.save(str(docx_path))
    return str(docx_path)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _add_formatted_text(paragraph, text: str):
    """Add text with basic inline formatting support (bold, italic)."""
    # Handle **bold** and *italic* markers
    parts = re.split(r"(\*\*.*?\*\*|\*.*?\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("*") and part.endswith("*") and not part.startswith("**"):
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        else:
            paragraph.add_run(part)


def _add_heading_border(heading):
    """Add a subtle bottom border to a heading paragraph (ATS-safe)."""
    try:
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        pPr = heading._element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "999999")
        pBdr.append(bottom)
        pPr.append(pBdr)
    except Exception:
        pass  # Non-critical formatting


# ---------------------------------------------------------------------------
# PDF Conversion & Validation Pipeline
# ---------------------------------------------------------------------------

def generate_cv_pdf(content: str, company: str, job_id: str,
                    ats_keywords: dict = None) -> dict:
    """
    Full CV generation pipeline: Content → DOCX → PDF → ATS Validation.

    Returns:
        {
            "cv_pdf": path or None,
            "cv_docx": path or None (only if DEBUG_KEEP_DOCX),
            "ats_validation": validation dict,
            "ats_score": int,
            "success": bool,
        }
    """
    try:
        from scripts.pdf_converter import convert_docx_to_pdf, cleanup_docx
        from scripts.ats_validator import validate_cv_pdf
    except ImportError:
        from pdf_converter import convert_docx_to_pdf, cleanup_docx
        from ats_validator import validate_cv_pdf

    result = {
        "cv_pdf": None,
        "cv_docx": None,
        "ats_validation": None,
        "ats_score": 0,
        "success": False,
        "errors": [],
    }

    # Step 1: Generate DOCX
    try:
        docx_path = generate_cv_docx(content, company, job_id)
        result["cv_docx"] = docx_path
    except Exception as e:
        result["errors"].append(f"DOCX generation failed: {e}")
        return result

    # Step 2: Convert to PDF
    try:
        pdf_path = convert_docx_to_pdf(docx_path, str(CV_DIR))
        result["cv_pdf"] = pdf_path
    except Exception as e:
        result["errors"].append(f"PDF conversion failed: {e}")
        return result

    # Step 3: ATS Validation
    validation = validate_cv_pdf(pdf_path, ats_keywords)
    result["ats_validation"] = validation
    result["ats_score"] = validation.get("ats_readability_score", 0)

    if validation.get("validation_passed"):
        result["success"] = True
        # Clean up intermediate DOCX
        cleanup_docx(docx_path)
        if not Path(docx_path).exists():
            result["cv_docx"] = None
    else:
        result["errors"].extend(validation.get("errors", []))
        result["errors"].append("ATS validation failed — documents NOT marked ready")

    return result


def generate_motivation_pdf(content: str, company: str, job_id: str) -> dict:
    """
    Full Motivation Letter pipeline: Content → DOCX → PDF → Validation.
    """
    try:
        from scripts.pdf_converter import convert_docx_to_pdf, cleanup_docx
        from scripts.ats_validator import validate_motivation_pdf
    except ImportError:
        from pdf_converter import convert_docx_to_pdf, cleanup_docx
        from ats_validator import validate_motivation_pdf

    result = {
        "motivation_pdf": None,
        "motivation_docx": None,
        "validation": None,
        "success": False,
        "errors": [],
    }

    # Step 1: Generate DOCX
    try:
        docx_path = generate_motivation_docx(content, company, job_id)
        result["motivation_docx"] = docx_path
    except Exception as e:
        result["errors"].append(f"DOCX generation failed: {e}")
        return result

    # Step 2: Convert to PDF
    try:
        pdf_path = convert_docx_to_pdf(docx_path, str(MOTIVATION_DIR))
        result["motivation_pdf"] = pdf_path
    except Exception as e:
        result["errors"].append(f"PDF conversion failed: {e}")
        return result

    # Step 3: Validation
    validation = validate_motivation_pdf(pdf_path)
    result["validation"] = validation

    if validation.get("validation_passed"):
        result["success"] = True
        cleanup_docx(docx_path)
        if not Path(docx_path).exists():
            result["motivation_docx"] = None
    else:
        result["errors"].extend(validation.get("errors", []))

    return result


# ---------------------------------------------------------------------------
# Application Answers
# ---------------------------------------------------------------------------

def save_application_answers(answers: dict, company: str, job_id: str) -> str:
    """Save application answers as JSON."""
    filename = generate_filename(company, job_id, "Answers", "json")
    filepath = APPLICATIONS_DIR / filename
    with open(filepath, "w") as f:
        json.dump(answers, f, indent=2)
    return str(filepath)


# ---------------------------------------------------------------------------
# Complete Document Generation
# ---------------------------------------------------------------------------

def generate_all_documents(job: dict, analysis: dict,
                           cv_content: str, letter_content: str,
                           ats_keywords: dict = None,
                           answers: dict = None) -> dict:
    """
    Generate all application documents with full ATS pipeline.

    Pipeline per document:
        Content → DOCX → PDF → ATS Validation

    Returns dict with paths and validation results.
    """
    company = job.get("company", "Unknown")
    job_id = job.get("linkedin_job_id", job.get("id", "unknown"))

    result = {
        "cv_pdf": None,
        "cv_docx": None,
        "motivation_pdf": None,
        "motivation_docx": None,
        "answers_json": None,
        "cv_ats_score": 0,
        "cv_ats_validation": None,
        "motivation_validation": None,
        "cv_ats_keywords_found": [],
        "cv_ats_keywords_missing": [],
        "all_valid": False,
        "errors": [],
    }

    cv_ok = False
    letter_ok = False

    # CV Pipeline
    if cv_content:
        try:
            cv_result = generate_cv_pdf(cv_content, company, job_id, ats_keywords)
            result["cv_pdf"] = cv_result.get("cv_pdf")
            result["cv_docx"] = cv_result.get("cv_docx")
            result["cv_ats_score"] = cv_result.get("ats_score", 0)
            result["cv_ats_validation"] = cv_result.get("ats_validation")
            cv_ok = cv_result.get("success", False)

            if cv_result.get("ats_validation"):
                v = cv_result["ats_validation"]
                result["cv_ats_keywords_found"] = v.get("required_keywords_found", [])
                result["cv_ats_keywords_missing"] = v.get("required_keywords_missing", [])

            if not cv_ok:
                result["errors"].extend(cv_result.get("errors", []))
        except ImportError as e:
            # python-docx not installed — fall back to text
            result["errors"].append(f"python-docx required: {e}")
            _save_text_fallback(cv_content, company, job_id, "CV", result)
        except Exception as e:
            result["errors"].append(f"CV generation error: {e}")

    # Motivation Letter Pipeline
    if letter_content:
        try:
            letter_result = generate_motivation_pdf(letter_content, company, job_id)
            result["motivation_pdf"] = letter_result.get("motivation_pdf")
            result["motivation_docx"] = letter_result.get("motivation_docx")
            result["motivation_validation"] = letter_result.get("validation")
            letter_ok = letter_result.get("success", False)

            if not letter_ok:
                result["errors"].extend(letter_result.get("errors", []))
        except ImportError as e:
            result["errors"].append(f"python-docx required: {e}")
            _save_text_fallback(letter_content, company, job_id, "Motivation_Letter", result)
        except Exception as e:
            result["errors"].append(f"Motivation Letter generation error: {e}")

    # Application Answers
    if answers:
        result["answers_json"] = save_application_answers(answers, company, job_id)

    result["all_valid"] = cv_ok and letter_ok

    return result


def _save_text_fallback(content: str, company: str, job_id: str,
                        doc_type: str, result: dict) -> None:
    """Fallback: save as plain text when DOCX generation is unavailable."""
    txt_name = generate_filename(company, job_id, doc_type, "txt")
    key = "cv" if "CV" in doc_type else "motivation"
    output_dir = CV_DIR if key == "cv" else MOTIVATION_DIR
    txt_path = output_dir / txt_name
    with open(txt_path, "w") as f:
        f.write(content)
    result[f"{key}_txt"] = str(txt_path)


if __name__ == "__main__":
    print("Document Generator (ATS-Optimized)")
    print(f"  CV output:         {CV_DIR}")
    print(f"  Motivation output: {MOTIVATION_DIR}")
    print(f"  Answers output:    {APPLICATIONS_DIR}")
