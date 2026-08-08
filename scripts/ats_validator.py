"""
Mohamed Job Agent — ATS Validator
===================================
Validates generated PDFs for ATS compatibility.
Extracts text, checks sections, verifies keyword coverage.
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional


# Required sections that must be parseable from the PDF
REQUIRED_CV_SECTIONS = [
    "Mohamed Almalky",
    "Professional Summary",
    "Technical Skills",
    "Professional Experience",
    "Education",
]

# Motivation Letter expected elements
REQUIRED_LETTER_ELEMENTS = [
    "Mohamed Almalky",
    "Dear",
]


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extract text from a PDF file.

    Uses pdftotext (poppler-utils) as primary method.
    Falls back to reading raw PDF bytes for basic text extraction.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return None

    if pdf_path.stat().st_size == 0:
        return None

    # Method 1: pdftotext (poppler-utils)
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            result = subprocess.run(
                [pdftotext, "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except (subprocess.TimeoutExpired, Exception):
            pass

    # Method 2: PyPDF2 (if installed)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        pass

    # Method 3: Basic binary scan for text content
    try:
        with open(pdf_path, "rb") as f:
            raw = f.read()
        # Check if file has the PDF header
        if raw[:5] != b"%PDF-":
            return None
        # Look for text streams — very basic
        text_blocks = re.findall(rb"\((.*?)\)", raw)
        if text_blocks:
            decoded = []
            for block in text_blocks[:100]:
                try:
                    decoded.append(block.decode("utf-8", errors="ignore"))
                except Exception:
                    pass
            if decoded:
                return " ".join(decoded)
    except Exception:
        pass

    return None


def validate_cv_pdf(pdf_path: str, ats_keywords: dict = None) -> dict:
    """
    Validate a CV PDF for ATS compatibility.

    Args:
        pdf_path: Path to the CV PDF file.
        ats_keywords: Dict with 'required' and 'preferred' keyword lists.

    Returns:
        Validation result dict with scores and details.
    """
    result = {
        "pdf_path": pdf_path,
        "pdf_exists": False,
        "pdf_not_empty": False,
        "pdf_text_extract_success": False,
        "extracted_text_length": 0,
        "section_parse_success": {},
        "all_sections_found": False,
        "required_keywords_found": [],
        "required_keywords_missing": [],
        "preferred_keywords_found": [],
        "preferred_keywords_missing": [],
        "contact_info_readable": False,
        "ats_readability_score": 0,
        "validation_passed": False,
        "errors": [],
    }

    pdf_file = Path(pdf_path)

    # Check file exists
    result["pdf_exists"] = pdf_file.exists()
    if not result["pdf_exists"]:
        result["errors"].append(f"PDF file not found: {pdf_path}")
        return result

    # Check file not empty
    result["pdf_not_empty"] = pdf_file.stat().st_size > 0
    if not result["pdf_not_empty"]:
        result["errors"].append("PDF file is empty (0 bytes)")
        return result

    # Extract text
    text = extract_text_from_pdf(pdf_path)
    result["pdf_text_extract_success"] = text is not None and len(text.strip()) > 50
    if not result["pdf_text_extract_success"]:
        result["errors"].append("Could not extract meaningful text from PDF")
        return result

    result["extracted_text_length"] = len(text)
    text_lower = text.lower()

    # Check required sections
    all_sections_ok = True
    for section in REQUIRED_CV_SECTIONS:
        found = section.lower() in text_lower
        result["section_parse_success"][section] = found
        if not found:
            all_sections_ok = False
            result["errors"].append(f"Section not found: '{section}'")

    result["all_sections_found"] = all_sections_ok

    # Check contact info
    result["contact_info_readable"] = "mohamed" in text_lower and "almalky" in text_lower

    # Check ATS keywords
    if ats_keywords:
        required = ats_keywords.get("required", [])
        preferred = ats_keywords.get("preferred", [])

        for kw in required:
            if kw.lower() in text_lower:
                result["required_keywords_found"].append(kw)
            else:
                result["required_keywords_missing"].append(kw)

        for kw in preferred:
            if kw.lower() in text_lower:
                result["preferred_keywords_found"].append(kw)
            else:
                result["preferred_keywords_missing"].append(kw)

    # Calculate ATS readability score
    score = _calculate_ats_score(result)
    result["ats_readability_score"] = score

    # Final validation
    result["validation_passed"] = (
        result["pdf_text_extract_success"]
        and result["all_sections_found"]
        and result["contact_info_readable"]
        and score >= 50
    )

    return result


def validate_motivation_pdf(pdf_path: str) -> dict:
    """Validate a Motivation Letter PDF."""
    result = {
        "pdf_path": pdf_path,
        "pdf_exists": False,
        "pdf_not_empty": False,
        "pdf_text_extract_success": False,
        "extracted_text_length": 0,
        "elements_found": {},
        "validation_passed": False,
        "errors": [],
    }

    pdf_file = Path(pdf_path)
    result["pdf_exists"] = pdf_file.exists()
    if not result["pdf_exists"]:
        result["errors"].append(f"PDF not found: {pdf_path}")
        return result

    result["pdf_not_empty"] = pdf_file.stat().st_size > 0
    if not result["pdf_not_empty"]:
        result["errors"].append("PDF is empty")
        return result

    text = extract_text_from_pdf(pdf_path)
    result["pdf_text_extract_success"] = text is not None and len(text.strip()) > 30
    if not result["pdf_text_extract_success"]:
        result["errors"].append("Could not extract text from motivation PDF")
        return result

    result["extracted_text_length"] = len(text)
    text_lower = text.lower()

    for element in REQUIRED_LETTER_ELEMENTS:
        result["elements_found"][element] = element.lower() in text_lower

    result["validation_passed"] = (
        result["pdf_text_extract_success"]
        and all(result["elements_found"].values())
    )

    return result


def _calculate_ats_score(validation: dict) -> int:
    """
    Calculate an ATS compatibility score from 0-100.

    Scoring:
    - PDF extractable:           20 points
    - All sections found:        25 points
    - Contact info readable:     10 points
    - Required keywords (proportional): 30 points
    - Preferred keywords (proportional): 15 points
    """
    score = 0

    # Text extraction (20 pts)
    if validation["pdf_text_extract_success"]:
        score += 20

    # Section structure (25 pts)
    sections = validation.get("section_parse_success", {})
    if sections:
        found_count = sum(1 for v in sections.values() if v)
        score += int(25 * found_count / len(sections))

    # Contact info (10 pts)
    if validation.get("contact_info_readable"):
        score += 10

    # Required keywords (30 pts)
    req_found = len(validation.get("required_keywords_found", []))
    req_missing = len(validation.get("required_keywords_missing", []))
    req_total = req_found + req_missing
    if req_total > 0:
        score += int(30 * req_found / req_total)
    else:
        score += 30  # No required keywords specified = full marks

    # Preferred keywords (15 pts)
    pref_found = len(validation.get("preferred_keywords_found", []))
    pref_missing = len(validation.get("preferred_keywords_missing", []))
    pref_total = pref_found + pref_missing
    if pref_total > 0:
        score += int(15 * pref_found / pref_total)
    else:
        score += 15

    return min(100, max(0, score))


def generate_ats_report(cv_validation: dict, letter_validation: dict = None) -> str:
    """Generate a human-readable ATS coverage report."""
    lines = []
    lines.append("=" * 50)
    lines.append("ATS VALIDATION REPORT")
    lines.append("=" * 50)

    # CV Report
    lines.append("\n📄 CV PDF")
    lines.append(f"   File: {cv_validation.get('pdf_path', 'N/A')}")
    lines.append(f"   Text extractable: {'✅' if cv_validation.get('pdf_text_extract_success') else '❌'}")
    lines.append(f"   Text length: {cv_validation.get('extracted_text_length', 0)} chars")
    lines.append(f"   Contact readable: {'✅' if cv_validation.get('contact_info_readable') else '❌'}")

    sections = cv_validation.get("section_parse_success", {})
    lines.append(f"\n   Sections:")
    for section, found in sections.items():
        lines.append(f"     {'✅' if found else '❌'} {section}")

    req_found = cv_validation.get("required_keywords_found", [])
    req_missing = cv_validation.get("required_keywords_missing", [])
    if req_found or req_missing:
        lines.append(f"\n   Required keywords: {len(req_found)}/{len(req_found)+len(req_missing)}")
        if req_missing:
            lines.append(f"   ⚠️  Missing: {', '.join(req_missing[:10])}")

    pref_found = cv_validation.get("preferred_keywords_found", [])
    pref_missing = cv_validation.get("preferred_keywords_missing", [])
    if pref_found or pref_missing:
        lines.append(f"   Preferred keywords: {len(pref_found)}/{len(pref_found)+len(pref_missing)}")

    lines.append(f"\n   ATS Score: {cv_validation.get('ats_readability_score', 0)}/100")
    lines.append(f"   Validation: {'✅ PASSED' if cv_validation.get('validation_passed') else '❌ FAILED'}")

    if cv_validation.get("errors"):
        lines.append(f"\n   Errors:")
        for err in cv_validation["errors"]:
            lines.append(f"     ❌ {err}")

    # Motivation Letter Report
    if letter_validation:
        lines.append(f"\n📄 Motivation Letter PDF")
        lines.append(f"   File: {letter_validation.get('pdf_path', 'N/A')}")
        lines.append(f"   Text extractable: {'✅' if letter_validation.get('pdf_text_extract_success') else '❌'}")
        lines.append(f"   Validation: {'✅ PASSED' if letter_validation.get('validation_passed') else '❌ FAILED'}")

    lines.append("\n" + "=" * 50)
    return "\n".join(lines)


if __name__ == "__main__":
    print("ATS Validator ready.")
    print(f"pdftotext available: {shutil.which('pdftotext') is not None}")
    print(f"Required CV sections: {REQUIRED_CV_SECTIONS}")
