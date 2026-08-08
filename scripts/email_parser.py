"""
Mohamed Job Agent — LinkedIn Email Parser
==========================================
Parses LinkedIn job alert emails and extracts individual job listings.
Works with both HTML and plain text email content.
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional


# Patterns to SKIP (application confirmations, not job alerts)
SKIP_SUBJECT_PATTERNS = [
    r"your application",
    r"application was sent",
    r"apply now",
    r"problem with your",
    r"your job alert preferences",
    r"you applied",
    r"application received",
    r"application submitted",
    r"thank you for applying",
]


def should_skip_email(subject: str) -> bool:
    """Check if email subject indicates it's NOT a job alert."""
    if not subject:
        return True
    subject_lower = subject.lower()
    return any(re.search(pat, subject_lower) for pat in SKIP_SUBJECT_PATTERNS)


def is_linkedin_job_alert(from_addr: str, subject: str = "") -> bool:
    """Check if email is from LinkedIn job alerts."""
    if not from_addr:
        return False
    from_lower = from_addr.lower()
    if "jobs-noreply@linkedin.com" not in from_lower:
        return False
    if should_skip_email(subject):
        return False
    return True


class LinkedInJobHTMLParser(HTMLParser):
    """
    Parse LinkedIn job alert HTML emails to extract individual job listings.

    LinkedIn alert emails typically contain multiple job cards, each with:
    - Job title (linked to the job posting)
    - Company name
    - Location
    - Sometimes workplace type (Remote, Hybrid, etc.)
    """

    def __init__(self):
        super().__init__()
        self.jobs = []
        self._current_job = {}
        self._in_link = False
        self._current_href = ""
        self._capture_text = False
        self._text_buffer = ""
        self._links = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a":
            href = attrs_dict.get("href", "")
            if "linkedin.com/comm/jobs/view/" in href or "linkedin.com/jobs/view/" in href:
                self._in_link = True
                self._current_href = href
                self._text_buffer = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._text_buffer.strip():
                self._links.append({
                    "title": self._text_buffer.strip(),
                    "url": self._current_href,
                })
            self._text_buffer = ""

    def handle_data(self, data):
        if self._in_link:
            self._text_buffer += data


def extract_linkedin_job_id(url: str) -> Optional[str]:
    """Extract the LinkedIn job ID from a URL."""
    if not url:
        return None
    # Pattern: /jobs/view/1234567890/ or currentJobId=1234567890
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"currentJobId=(\d+)", url)
    if match:
        return match.group(1)
    return None


def clean_linkedin_url(url: str) -> str:
    """Clean tracking parameters from LinkedIn URL, keep the job view URL."""
    if not url:
        return ""
    # Extract the core job URL
    job_id = extract_linkedin_job_id(url)
    if job_id:
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    return url


def extract_jobs_from_html(html_content: str, email_id: str = "",
                           email_subject: str = "") -> list[dict]:
    """
    Extract individual job listings from LinkedIn alert HTML email.

    Returns a list of job dicts, each containing:
        linkedin_job_id, job_title, company, location,
        workplace_type, linkedin_url, source_email_id, discovered_at
    """
    if not html_content:
        return []

    parser = LinkedInJobHTMLParser()
    try:
        parser.feed(html_content)
    except Exception:
        pass

    jobs = []
    seen_ids = set()

    # Process links found by the HTML parser
    for link in parser._links:
        url = link["url"]
        title = link["title"]
        job_id = extract_linkedin_job_id(url)

        # Skip duplicates within same email
        if job_id and job_id in seen_ids:
            continue
        if job_id:
            seen_ids.add(job_id)

        clean_url = clean_linkedin_url(url)

        job = {
            "linkedin_job_id": job_id,
            "job_title": title,
            "company": "",  # Will be enriched in next parsing stage
            "location": "",
            "workplace_type": "",
            "linkedin_url": clean_url,
            "source_email_id": email_id,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }
        jobs.append(job)

    # Try regex fallback for additional job patterns
    regex_jobs = _extract_jobs_regex(html_content, email_id, seen_ids)
    jobs.extend(regex_jobs)

    # Try to enrich with company/location from surrounding context
    _enrich_jobs_from_html(html_content, jobs)

    return jobs


def _extract_jobs_regex(html_content: str, email_id: str,
                        seen_ids: set) -> list[dict]:
    """Regex-based fallback extraction for LinkedIn job URLs."""
    jobs = []
    # Find all LinkedIn job URLs
    url_pattern = re.compile(
        r'href=["\']([^"\']*linkedin\.com/(?:comm/)?jobs/view/\d+[^"\']*)["\']',
        re.IGNORECASE,
    )
    for match in url_pattern.finditer(html_content):
        url = match.group(1)
        job_id = extract_linkedin_job_id(url)
        if job_id and job_id not in seen_ids:
            seen_ids.add(job_id)
            clean_url = clean_linkedin_url(url)
            # Try to find the link text (title) near this URL
            title = _find_link_text(html_content, match.start(), match.end())
            jobs.append({
                "linkedin_job_id": job_id,
                "job_title": title or "Unknown Title",
                "company": "",
                "location": "",
                "workplace_type": "",
                "linkedin_url": clean_url,
                "source_email_id": email_id,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            })
    return jobs


def _find_link_text(html: str, link_start: int, link_end: int) -> str:
    """Try to extract the text between <a ...> and </a> near a URL match."""
    # Find the closing > of the <a> tag
    close_tag = html.find(">", link_end)
    if close_tag == -1:
        return ""
    # Find </a>
    end_a = html.find("</a>", close_tag)
    if end_a == -1:
        return ""
    text = html[close_tag + 1: end_a]
    # Strip HTML tags from the text
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _enrich_jobs_from_html(html_content: str, jobs: list[dict]) -> None:
    """
    Try to find company name and location near each job in the HTML.

    LinkedIn alert emails typically have the company and location in
    text/elements near the job title link. This function searches the
    surrounding context for likely patterns.
    """
    for job in jobs:
        if not job.get("linkedin_url"):
            continue

        job_id = job.get("linkedin_job_id", "")
        if not job_id:
            continue

        # Find the job URL occurrence in HTML and look at nearby text
        idx = html_content.find(job_id)
        if idx == -1:
            continue

        # Extract a window of text around the job mention
        start = max(0, idx - 500)
        end = min(len(html_content), idx + 1500)
        window = html_content[start:end]
        window_text = re.sub(r"<[^>]+>", "\n", window)
        window_text = re.sub(r"\s+", " ", window_text).strip()

        # Try to find company (often follows "at " or " · " or "– ")
        if not job.get("company"):
            company_match = re.search(
                r"(?:at|·|–|-)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*·|\s*–|\s*-|\s*\n|\s*<)",
                window_text,
            )
            if company_match:
                job["company"] = company_match.group(1).strip()

        # Try to find location
        if not job.get("location"):
            location_match = re.search(
                r"(?:·|–|-)\s*([A-Z][A-Za-z\s,]+(?:Area|Region|County|City|Metropolitan)?)",
                window_text,
            )
            if location_match:
                candidate = location_match.group(1).strip()
                # Basic validation: locations tend to have commas or country names
                if "," in candidate or len(candidate.split()) <= 5:
                    job["location"] = candidate

        # Detect workplace type
        if not job.get("workplace_type"):
            wt_lower = window_text.lower()
            if "remote" in wt_lower:
                job["workplace_type"] = "Remote"
            elif "hybrid" in wt_lower:
                job["workplace_type"] = "Hybrid"
            elif "on-site" in wt_lower or "onsite" in wt_lower:
                job["workplace_type"] = "On-site"


def extract_jobs_from_text(text_content: str, email_id: str = "") -> list[dict]:
    """
    Fallback: extract jobs from plain text email content.

    Less reliable than HTML parsing, but handles edge cases.
    """
    if not text_content:
        return []

    jobs = []
    seen_ids = set()

    # Find all LinkedIn job URLs in plain text
    url_pattern = re.compile(
        r"(https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/\d+[^\s]*)",
        re.IGNORECASE,
    )

    for match in url_pattern.finditer(text_content):
        url = match.group(1)
        job_id = extract_linkedin_job_id(url)
        if job_id and job_id not in seen_ids:
            seen_ids.add(job_id)
            # Try to find title in the line before the URL
            line_start = text_content.rfind("\n", 0, match.start())
            preceding_text = text_content[line_start + 1: match.start()].strip()
            title = preceding_text if preceding_text else "Unknown Title"

            jobs.append({
                "linkedin_job_id": job_id,
                "job_title": title,
                "company": "",
                "location": "",
                "workplace_type": "",
                "linkedin_url": clean_linkedin_url(url),
                "source_email_id": email_id,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            })

    return jobs


def parse_email(email_data: dict) -> list[dict]:
    """
    Main entry point: parse a Gmail message and extract jobs.

    email_data should contain:
        - id: Gmail message ID
        - subject: email subject
        - from: sender address
        - html: HTML body (preferred)
        - text: plain text body (fallback)
    """
    email_id = email_data.get("id", "")
    subject = email_data.get("subject", "")
    from_addr = email_data.get("from", "")

    # Validate this is a LinkedIn job alert
    if not is_linkedin_job_alert(from_addr, subject):
        return []

    # Try HTML first, then plain text
    html = email_data.get("html", "")
    text = email_data.get("text", "")

    if html:
        jobs = extract_jobs_from_html(html, email_id, subject)
    elif text:
        jobs = extract_jobs_from_text(text, email_id)
    else:
        return []

    return jobs


if __name__ == "__main__":
    # Quick test with sample data
    sample = {
        "id": "test_001",
        "subject": "5 new jobs in Embedded Software",
        "from": "jobs-noreply@linkedin.com",
        "html": """
        <a href="https://www.linkedin.com/comm/jobs/view/3912345678/">
            Embedded Software Engineer
        </a>
        <a href="https://www.linkedin.com/comm/jobs/view/3912345679/">
            AUTOSAR Developer
        </a>
        """,
    }
    results = parse_email(sample)
    print(json.dumps(results, indent=2))
    print(f"\nExtracted {len(results)} jobs")
