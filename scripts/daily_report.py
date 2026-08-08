"""
Mohamed Job Agent — Daily Report Generator
============================================
Generates human-readable daily summary reports.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_manager import get_connection, get_jobs_for_report


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def generate_daily_report(report_date: str = None, db_path: str = None) -> str:
    """
    Generate a human-readable daily report.

    Returns the report as a formatted string and saves to logs/.
    """
    if report_date is None:
        report_date = date.today().isoformat()

    conn = get_connection(db_path)
    try:
        stats = get_jobs_for_report(conn, report_date)
    finally:
        conn.close()

    lines = []
    lines.append("=" * 70)
    lines.append(f"  MOHAMED JOB AGENT — DAILY REPORT")
    lines.append(f"  Date: {report_date}")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    # Summary statistics
    lines.append("📊 SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Total jobs found:      {stats.get('total_jobs', 0)}")
    lines.append(f"  Jobs analyzed:         {stats.get('jobs_analyzed', 0)}")
    lines.append(f"  Jobs skipped:          {stats.get('jobs_skipped', 0)}")
    lines.append(f"  Jobs for review:       {stats.get('jobs_review', 0) if 'jobs_review' not in stats else len(stats.get('review_jobs', []))}")
    lines.append(f"  Strong matches:        {len(stats.get('strong_matches', []))}")
    lines.append(f"  Documents ready:       {stats.get('jobs_documents_ready', 0)}")
    lines.append(f"  Ready to apply:        {stats.get('jobs_ready_to_apply', 0)}")
    lines.append("")

    # Strong matches detail
    strong = stats.get("strong_matches", [])
    if strong:
        lines.append("🎯 STRONG MATCHES (APPLY)")
        lines.append("-" * 40)
        for i, job in enumerate(strong, 1):
            lines.append(f"\n  [{i}] {job.get('title', 'N/A')}")
            lines.append(f"      Company:    {job.get('company', 'N/A')}")
            lines.append(f"      Location:   {job.get('location', 'N/A')}")
            lines.append(f"      Fit Score:  {job.get('fit_score', 'N/A')}")
            lines.append(f"      Visa:       {job.get('visa_sponsorship', 'N/A')}")
            lines.append(f"      Status:     {job.get('status', 'N/A')}")

            # Parse analysis JSON for details
            analysis_json = job.get("analysis_json")
            if analysis_json:
                try:
                    analysis = json.loads(analysis_json)
                    matched = analysis.get("matched_skills", [])
                    if matched:
                        lines.append(f"      Matched:    {', '.join(matched[:8])}")
                    gaps = analysis.get("missing_required_skills", [])
                    if gaps:
                        lines.append(f"      Gaps:       {', '.join(gaps[:5])}")
                except json.JSONDecodeError:
                    pass

            if job.get("linkedin_url"):
                lines.append(f"      LinkedIn:   {job['linkedin_url']}")
            if job.get("official_url"):
                lines.append(f"      Official:   {job['official_url']}")
            if job.get("cv_file"):
                lines.append(f"      CV:         {job['cv_file']}")
            if job.get("motivation_file"):
                lines.append(f"      Letter:     {job['motivation_file']}")
        lines.append("")

    # Review jobs
    review = stats.get("review_jobs", [])
    if review:
        lines.append("🔍 JOBS FOR REVIEW")
        lines.append("-" * 40)
        for i, job in enumerate(review, 1):
            lines.append(f"  [{i}] {job.get('title', 'N/A')} @ {job.get('company', 'N/A')}")
            lines.append(f"      Location: {job.get('location', 'N/A')} | Fit: {job.get('fit_score', 'N/A')} | Visa: {job.get('visa_sponsorship', 'N/A')}")
        lines.append("")

    lines.append("=" * 70)
    lines.append("End of report")
    lines.append("")

    report_text = "\n".join(lines)

    # Save to file
    report_filename = f"daily_report_{report_date}.txt"
    report_path = LOGS_DIR / report_filename
    with open(report_path, "w") as f:
        f.write(report_text)

    # Also save as JSON for programmatic access
    json_filename = f"daily_report_{report_date}.json"
    json_path = LOGS_DIR / json_filename
    json_stats = {k: v for k, v in stats.items()
                  if k not in ("strong_matches", "review_jobs")}
    json_stats["strong_matches_count"] = len(strong)
    json_stats["review_count"] = len(review)
    with open(json_path, "w") as f:
        json.dump(json_stats, f, indent=2)

    print(report_text)
    return report_text


if __name__ == "__main__":
    generate_daily_report()
