"""
Mohamed Job Agent — PDF Converter
===================================
Converts DOCX files to PDF using LibreOffice headless.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional


def find_libreoffice() -> Optional[str]:
    """Find the LibreOffice binary."""
    for name in ["libreoffice", "soffice", "lowriter"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def convert_docx_to_pdf(docx_path: str, output_dir: str = None) -> Optional[str]:
    """
    Convert a DOCX file to PDF using LibreOffice headless.

    Args:
        docx_path: Path to the input DOCX file.
        output_dir: Directory for the output PDF. Defaults to same directory as DOCX.

    Returns:
        Path to the generated PDF, or None on failure.
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    if output_dir is None:
        output_dir = str(docx_path.parent)

    lo_bin = find_libreoffice()
    if not lo_bin:
        raise RuntimeError(
            "LibreOffice not found. Install it: sudo apt install libreoffice"
        )

    # Use a unique user profile to avoid lock conflicts with running instances
    user_profile = Path(output_dir) / ".lo_profile"
    user_profile.mkdir(parents=True, exist_ok=True)

    cmd = [
        lo_bin,
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation=file://{user_profile}",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(docx_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"LibreOffice conversion failed: {error_msg}")

        # Determine expected PDF path
        pdf_name = docx_path.stem + ".pdf"
        pdf_path = Path(output_dir) / pdf_name

        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return str(pdf_path)
        else:
            raise RuntimeError(
                f"PDF file not created or empty: {pdf_path}. "
                f"LibreOffice stdout: {result.stdout.strip()}"
            )

    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice conversion timed out (60s)")
    finally:
        # Clean up temp profile
        try:
            shutil.rmtree(user_profile, ignore_errors=True)
        except Exception:
            pass


def cleanup_docx(docx_path: str, keep_docx: bool = False) -> None:
    """
    Remove intermediate DOCX file after successful PDF conversion.

    Respects DEBUG_KEEP_DOCX environment variable.
    """
    if keep_docx or os.environ.get("DEBUG_KEEP_DOCX", "").lower() == "true":
        return

    docx_file = Path(docx_path)
    if docx_file.exists() and docx_file.suffix.lower() == ".docx":
        docx_file.unlink()


if __name__ == "__main__":
    lo = find_libreoffice()
    print(f"LibreOffice found: {lo or 'NOT FOUND'}")
    if lo:
        result = subprocess.run([lo, "--version"], capture_output=True, text=True)
        print(f"Version: {result.stdout.strip()}")
