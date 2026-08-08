"""
Mohamed Job Agent — AI Job Analyzer
=====================================
Integrates with OpenAI to analyze jobs against Mohamed's career profile.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CAREER_PROFILE_PATH = PROJECT_ROOT / "career-profile" / "mohamed_almalky.json"

FIT_THRESHOLD_SHORTLIST = int(os.environ.get("FIT_THRESHOLD_SHORTLIST", "80"))
FIT_THRESHOLD_REVIEW = int(os.environ.get("FIT_THRESHOLD_REVIEW", "65"))


def load_career_profile() -> dict:
    with open(CAREER_PROFILE_PATH, "r") as f:
        return json.load(f)


def load_prompt_template(prompt_name: str) -> str:
    path = PROMPTS_DIR / f"{prompt_name}.md"
    with open(path, "r") as f:
        return f.read()


def render_prompt(template: str, variables: dict) -> str:
    rendered = template
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        rendered = rendered.replace(placeholder, str(value) if value else "N/A")
    return rendered


def build_analysis_prompt(job: dict) -> str:
    profile = load_career_profile()
    template = load_prompt_template("job_analysis")
    variables = {
        "career_profile": profile,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "workplace_type": job.get("workplace_type", ""),
        "full_description": job.get("full_description", "No description available"),
        "requirements": job.get("requirements", "Not specified"),
        "preferred_qualifications": job.get("preferred_qualifications", "Not specified"),
        "language_requirements": job.get("language_requirements", "Not specified"),
        "experience_requirements": job.get("experience_requirements", "Not specified"),
        "visa_information": job.get("visa_information", "Not mentioned"),
        "relocation_information": job.get("relocation_information", "Not mentioned"),
    }
    return render_prompt(template, variables)


def build_ats_analysis_prompt(job: dict) -> str:
    profile = load_career_profile()
    template = load_prompt_template("ats_analysis")
    variables = {
        "career_profile": profile,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "full_description": job.get("full_description", "No description available"),
        "requirements": job.get("requirements", "Not specified"),
        "preferred_qualifications": job.get("preferred_qualifications", "Not specified"),
    }
    return render_prompt(template, variables)


def build_cv_prompt(job: dict, analysis: dict, ats_analysis: dict = None) -> str:
    profile = load_career_profile()
    template = load_prompt_template("cv_generation")

    keywords_req = []
    keywords_pref = []
    summary_focus = analysis.get("recommended_cv_focus", [])

    if ats_analysis:
        keywords_req = ats_analysis.get("ats_keywords_required", [])
        keywords_pref = ats_analysis.get("ats_keywords_preferred", [])
        if ats_analysis.get("recommended_summary_focus"):
            summary_focus = ats_analysis.get("recommended_summary_focus")

    variables = {
        "career_profile": profile,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "full_description": job.get("full_description", ""),
        "recommended_cv_focus": summary_focus,
        "recommended_keywords": keywords_req + keywords_pref or analysis.get("recommended_keywords", []),
        "matched_skills": analysis.get("matched_skills", []),
        "ats_keywords_required": keywords_req,
        "ats_keywords_preferred": keywords_pref,
    }
    return render_prompt(template, variables)


def build_motivation_prompt(job: dict, analysis: dict) -> str:
    profile = load_career_profile()
    template = load_prompt_template("motivation_letter")
    variables = {
        "career_profile": profile,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "full_description": job.get("full_description", ""),
        "matched_skills": analysis.get("matched_skills", []),
        "recommended_cv_focus": analysis.get("recommended_cv_focus", []),
    }
    return render_prompt(template, variables)


def build_answers_prompt(job: dict, questions: list[str]) -> str:
    profile = load_career_profile()
    template = load_prompt_template("application_answers")
    variables = {
        "career_profile": profile,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "questions": "\n".join(f"- {q}" for q in questions),
    }
    return render_prompt(template, variables)


def parse_ai_response(response_text: str) -> Optional[dict]:
    if not response_text:
        return None
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def validate_analysis(analysis: dict) -> tuple[bool, list[str]]:
    required = ["fit_score", "technical_score", "career_score",
                 "relocation_score", "visa_score", "decision",
                 "matched_skills", "missing_required_skills",
                 "experience_match", "visa_sponsorship", "relocation", "explanation"]
    errors = []
    for f in required:
        if f not in analysis:
            errors.append(f"Missing: {f}")
    for sf in ["fit_score", "technical_score", "career_score", "relocation_score", "visa_score"]:
        if sf in analysis:
            v = analysis[sf]
            if not isinstance(v, (int, float)) or v < 0 or v > 100:
                errors.append(f"{sf} must be 0-100, got: {v}")
    if "decision" in analysis and analysis["decision"] not in ("APPLY", "REVIEW", "SKIP"):
        errors.append(f"Invalid decision: {analysis['decision']}")
    return len(errors) == 0, errors


def apply_decision_thresholds(analysis: dict) -> dict:
    fit = analysis.get("fit_score", 0)
    if fit >= FIT_THRESHOLD_SHORTLIST:
        analysis["decision"] = "APPLY"
    elif fit >= FIT_THRESHOLD_REVIEW:
        analysis["decision"] = "REVIEW"
    else:
        analysis["decision"] = "SKIP"
    return analysis


def extract_cv_content(response_text: str) -> str:
    match = re.search(r"---CV_START---(.*?)---CV_END---", response_text, re.DOTALL)
    return match.group(1).strip() if match else response_text.strip()


def extract_letter_content(response_text: str) -> str:
    match = re.search(r"---LETTER_START---(.*?)---LETTER_END---", response_text, re.DOTALL)
    return match.group(1).strip() if match else response_text.strip()


def build_openai_messages(prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": "You are an expert technical recruiter specializing in embedded software and automotive engineering. Respond with valid JSON when asked."},
        {"role": "user", "content": prompt},
    ]


if __name__ == "__main__":
    test_job = {
        "company": "Continental AG", "title": "Embedded Software Engineer",
        "location": "Frankfurt, Germany", "full_description": "AUTOSAR Classic experience needed...",
    }
    prompt = build_analysis_prompt(test_job)
    print(f"Analysis prompt length: {len(prompt)} chars")
