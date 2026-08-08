"""
Mohamed Job Agent — Job Description Retriever
===============================================
Retrieves full job descriptions from multiple sources.
Priority: Official careers page > ATS > LinkedIn > Email content.
"""

import re
import json
import urllib.parse
from typing import Optional


# Known ATS platform URL patterns
ATS_PATTERNS = {
    "Workday": [
        r"myworkdayjobs\.com",
        r"wd\d+\.myworkday\.com",
        r"workday\.com/.*careers",
    ],
    "Greenhouse": [
        r"boards\.greenhouse\.io",
        r"job-boards\.greenhouse\.io",
        r"greenhouse\.io/.*jobs",
    ],
    "Lever": [
        r"jobs\.lever\.co",
        r"lever\.co/.*apply",
    ],
    "SmartRecruiters": [
        r"jobs\.smartrecruiters\.com",
        r"smartrecruiters\.com",
    ],
    "Teamtailor": [
        r"career\..*\.com",
        r"jobs\..*\.com",
        r"\.teamtailor\.com",
    ],
    "SuccessFactors": [
        r"jobs\.sap\.com",
        r"successfactors\.com",
        r"\.successfactors\.eu",
    ],
    "Ashby": [
        r"jobs\.ashbyhq\.com",
        r"ashbyhq\.com",
    ],
    "Personio": [
        r"jobs\.personio\.de",
        r"\.jobs\.personio\.com",
    ],
    "BambooHR": [
        r".*\.bamboohr\.com/careers",
        r".*\.bamboohr\.com/jobs",
    ],
    "iCIMS": [
        r"careers-.*\.icims\.com",
        r"jobs\..*\.icims\.com",
    ],
}


def detect_ats_platform(url: str) -> Optional[str]:
    """Detect which ATS platform a URL belongs to."""
    if not url:
        return None
    for platform, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return None


def build_careers_search_query(company: str, title: str, location: str = "") -> str:
    """
    Build a Google search query to find the official careers page.

    Example: "Continental careers Embedded Software Engineer Germany"
    """
    parts = [company, "careers", title]
    if location:
        # Extract country/city from location string
        parts.append(location.split(",")[0].strip())
    return " ".join(parts)


def build_ats_search_query(company: str, title: str) -> str:
    """Build a search query targeting known ATS platforms."""
    ats_sites = [
        "myworkdayjobs.com",
        "boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.smartrecruiters.com",
    ]
    site_query = " OR ".join(f"site:{site}" for site in ats_sites)
    return f"{company} {title} ({site_query})"


def parse_job_description_response(response_text: str) -> dict:
    """
    Parse a job description from retrieved page content.

    This is a structured extraction — the actual HTTP retrieval
    is done by n8n HTTP Request nodes or the browser agent.

    Returns a dict with standardized job description fields.
    """
    result = {
        "full_description": "",
        "requirements": "",
        "preferred_qualifications": "",
        "language_requirements": "",
        "experience_requirements": "",
        "visa_information": "",
        "relocation_information": "",
        "description_source": "",
        "official_url": "",
        "ats_platform": "",
    }

    if not response_text:
        return result

    text = response_text

    # Extract requirements section
    req_patterns = [
        r"(?:requirements|qualifications|what you.ll need|what we.re looking for|must have)[:\s]*(.*?)(?=\n\n|\n[A-Z]|preferred|nice to have|what we offer|benefits|$)",
        r"(?:minimum qualifications)[:\s]*(.*?)(?=\n\n|preferred|$)",
    ]
    for pattern in req_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            result["requirements"] = match.group(1).strip()
            break

    # Extract preferred qualifications
    pref_patterns = [
        r"(?:preferred|nice to have|bonus|desired|additional)[:\s]*(.*?)(?=\n\n|\n[A-Z]|what we offer|benefits|$)",
    ]
    for pattern in pref_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            result["preferred_qualifications"] = match.group(1).strip()
            break

    # Extract language requirements
    lang_patterns = [
        r"(?:language[s]?|spoken|fluent|proficiency)[:\s]*(.*?)(?=\n|$)",
        r"(?:german|french|dutch|swedish|english)\s+(?:required|mandatory|fluent|native)",
    ]
    for pattern in lang_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["language_requirements"] = match.group(0).strip()
            break

    # Extract experience requirements
    exp_match = re.search(
        r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|professional)",
        text, re.IGNORECASE,
    )
    if exp_match:
        result["experience_requirements"] = exp_match.group(0).strip()

    # Extract visa/sponsorship information
    visa_patterns = [
        r"(?:visa|sponsorship|work authorization|work permit|right to work)[^.]*\.",
        r"(?:must be authorized|must have the right|must be eligible)[^.]*\.",
    ]
    for pattern in visa_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["visa_information"] = match.group(0).strip()
            break

    # Extract relocation information
    reloc_patterns = [
        r"(?:relocation|relocate|moving|relocation assistance|relocation package)[^.]*\.",
    ]
    for pattern in reloc_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["relocation_information"] = match.group(0).strip()
            break

    result["full_description"] = text

    return result


def create_retrieval_plan(job: dict) -> list[dict]:
    """
    Create an ordered list of retrieval steps for a job.

    Returns steps to be executed by n8n or the browser agent.
    """
    company = job.get("company", "")
    title = job.get("title", job.get("job_title", ""))
    location = job.get("location", "")
    linkedin_url = job.get("linkedin_url", "")

    steps = []

    # Step 1: Search for official careers page
    if company and title:
        steps.append({
            "type": "web_search",
            "query": build_careers_search_query(company, title, location),
            "purpose": "Find official company careers page",
            "priority": 1,
        })

    # Step 2: Search ATS platforms
    if company and title:
        steps.append({
            "type": "web_search",
            "query": build_ats_search_query(company, title),
            "purpose": "Find job on ATS platform",
            "priority": 2,
        })

    # Step 3: LinkedIn job page
    if linkedin_url:
        steps.append({
            "type": "http_request",
            "url": linkedin_url,
            "purpose": "Retrieve LinkedIn job page",
            "priority": 3,
        })

    return steps


# n8n integration helper: format for n8n Code node
def format_for_n8n(job: dict) -> dict:
    """Format job data for n8n workflow consumption."""
    return {
        "json": {
            "job_id": job.get("id"),
            "linkedin_job_id": job.get("linkedin_job_id"),
            "company": job.get("company"),
            "title": job.get("title", job.get("job_title")),
            "location": job.get("location"),
            "linkedin_url": job.get("linkedin_url"),
            "search_query_careers": build_careers_search_query(
                job.get("company", ""),
                job.get("title", job.get("job_title", "")),
                job.get("location", ""),
            ),
            "search_query_ats": build_ats_search_query(
                job.get("company", ""),
                job.get("title", job.get("job_title", "")),
            ),
        }
    }


if __name__ == "__main__":
    # Test ATS detection
    test_urls = [
        "https://continental.wd3.myworkdayjobs.com/external/job/12345",
        "https://boards.greenhouse.io/company/jobs/6789",
        "https://jobs.lever.co/company/abcd-1234",
        "https://jobs.smartrecruiters.com/Company/12345-role",
        "https://www.example.com/careers/job123",
    ]
    for url in test_urls:
        platform = detect_ats_platform(url)
        print(f"{url} -> {platform or 'Unknown'}")
