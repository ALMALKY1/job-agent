"""
Mohamed Job Agent — Browser Automation Foundation
===================================================
Playwright-based browser agent for ATS form filling.
Does NOT auto-submit — stops before final submission.
"""

import json
import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "browser-agent" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Selectors and patterns for stop conditions
STOP_TRIGGERS = {
    "captcha": [
        "iframe[src*='captcha']",
        "iframe[src*='recaptcha']",
        "#captcha",
        ".g-recaptcha",
        "[data-sitekey]",
        "iframe[title*='reCAPTCHA']",
    ],
    "otp": [
        "input[name*='otp']",
        "input[name*='verification']",
        "input[name*='code']",
        "[aria-label*='verification code']",
    ],
    "login": [
        "input[type='password']",
        "#password",
        "input[name='password']",
        "[aria-label='Password']",
    ],
    "legal_declaration": [
        "input[type='checkbox'][name*='agree']",
        "input[type='checkbox'][name*='terms']",
        "input[type='checkbox'][name*='consent']",
        "input[type='checkbox'][name*='declaration']",
    ],
    "submit_button": [
        "button[type='submit']:has-text('Submit Application')",
        "button:has-text('Submit')",
        "button:has-text('Apply')",
        "input[type='submit'][value*='Submit']",
    ],
}

# ATS platform configurations
ATS_CONFIGS = {
    "Workday": {
        "url_pattern": r"myworkdayjobs\.com|wd\d+\.myworkday",
        "apply_button": "a:has-text('Apply'), button:has-text('Apply')",
        "file_upload": "input[type='file']",
    },
    "Greenhouse": {
        "url_pattern": r"boards\.greenhouse\.io",
        "apply_button": "a:has-text('Apply'), #apply-button",
        "file_upload": "input[type='file']",
    },
    "Lever": {
        "url_pattern": r"jobs\.lever\.co",
        "apply_button": "a.postings-btn:has-text('Apply')",
        "file_upload": "input[type='file']",
    },
    "SmartRecruiters": {
        "url_pattern": r"jobs\.smartrecruiters\.com",
        "apply_button": "button:has-text('Apply'), a:has-text('Apply')",
        "file_upload": "input[type='file']",
    },
    "Teamtailor": {
        "url_pattern": r"\.teamtailor\.com|career\.",
        "apply_button": "a:has-text('Apply'), button:has-text('Apply')",
        "file_upload": "input[type='file']",
    },
}


def detect_ats_from_url(url: str) -> Optional[str]:
    """Detect ATS platform from URL."""
    for name, config in ATS_CONFIGS.items():
        if re.search(config["url_pattern"], url, re.IGNORECASE):
            return name
    return None


class ApplicationBot:
    """
    Browser automation agent for job applications.

    Workflow:
    1. Navigate to job URL
    2. Click Apply
    3. Fill known fields (name, email, phone)
    4. Upload CV and Motivation Letter
    5. Answer known questions
    6. STOP before final submit
    7. Take screenshot
    8. Return status READY_TO_APPLY
    """

    def __init__(self, headless: bool = True, slow_mo: int = 100):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.page = None
        self.status = "INITIALIZED"
        self.stop_reason = None
        self.screenshots = []

    async def launch(self):
        """Launch the browser."""
        try:
            from playwright.async_api import async_playwright
            self.pw = await async_playwright().start()
            self.browser = await self.pw.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
            self.page = await self.browser.new_page()
            self.status = "LAUNCHED"
        except ImportError:
            self.status = "ERROR"
            self.stop_reason = "Playwright not installed. Run: pip install playwright && playwright install"
            return False
        return True

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, "pw") and self.pw:
            await self.pw.stop()
        self.status = "CLOSED"

    async def check_stop_conditions(self) -> Optional[str]:
        """Check if any stop condition is met."""
        for trigger_type, selectors in STOP_TRIGGERS.items():
            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        return trigger_type
                except Exception:
                    continue
        return None

    async def take_screenshot(self, label: str = "step") -> str:
        """Take a screenshot and save it."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{label}_{timestamp}.png"
        filepath = SCREENSHOTS_DIR / filename
        await self.page.screenshot(path=str(filepath), full_page=True)
        self.screenshots.append(str(filepath))
        return str(filepath)

    async def navigate_to_job(self, url: str) -> dict:
        """Navigate to a job posting URL."""
        if not self.page:
            return {"success": False, "error": "Browser not launched"}

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.take_screenshot("job_page")

            # Detect ATS
            ats = detect_ats_from_url(url)

            # Check for stop conditions immediately
            stop = await self.check_stop_conditions()
            if stop in ("captcha", "login"):
                self.status = "BLOCKED"
                self.stop_reason = stop
                await self.take_screenshot(f"blocked_{stop}")
                return {
                    "success": False, "blocked": True,
                    "reason": stop, "ats": ats,
                }

            self.status = "ON_JOB_PAGE"
            return {"success": True, "ats": ats, "title": await self.page.title()}

        except Exception as e:
            self.status = "ERROR"
            self.stop_reason = str(e)
            return {"success": False, "error": str(e)}

    async def fill_field(self, selector: str, value: str) -> bool:
        """Safely fill a form field."""
        try:
            element = await self.page.query_selector(selector)
            if element and await element.is_visible():
                await element.fill(value)
                return True
        except Exception:
            pass
        return False

    async def upload_file(self, selector: str, file_path: str) -> bool:
        """Upload a file to a file input."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                await element.set_input_files(file_path)
                return True
        except Exception:
            pass
        return False

    async def apply_to_job(self, job: dict, cv_path: str = None,
                           motivation_path: str = None,
                           cv_pdf_path: str = None,
                           motivation_pdf_path: str = None) -> dict:
        """
        Attempt to fill an application form.
        STOPS before final submission.
        """
        result = {
            "status": "STARTED",
            "fields_filled": [],
            "files_uploaded": [],
            "stop_reason": None,
            "screenshots": [],
        }

        url = job.get("official_url") or job.get("linkedin_url", "")
        if not url:
            result["status"] = "ERROR"
            result["stop_reason"] = "No URL available"
            return result

        # Navigate
        nav = await self.navigate_to_job(url)
        if not nav.get("success"):
            result["status"] = "BLOCKED" if nav.get("blocked") else "ERROR"
            result["stop_reason"] = nav.get("reason") or nav.get("error")
            result["screenshots"] = self.screenshots
            return result

        # Check for stop conditions at each step
        stop = await self.check_stop_conditions()
        if stop:
            self.status = "STOPPED"
            self.stop_reason = stop
            await self.take_screenshot(f"stopped_{stop}")
            result["status"] = "READY_TO_APPLY"
            result["stop_reason"] = f"Stopped: {stop} detected"
            result["screenshots"] = self.screenshots
            return result

        # Try to upload CV (prefer PDF)
        cv_upload_file = cv_pdf_path if (cv_pdf_path and os.path.exists(cv_pdf_path)) else cv_path
        if cv_upload_file and os.path.exists(cv_upload_file):
            file_inputs = await self.page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                try:
                    await fi.set_input_files(cv_upload_file)
                    result["files_uploaded"].append("cv")
                    break
                except Exception:
                    continue

        await self.take_screenshot("after_fill")

        # Final stop — do NOT submit
        result["status"] = "READY_TO_APPLY"
        result["stop_reason"] = "Stopped before final submission — human review required"
        result["screenshots"] = self.screenshots
        self.status = "READY_TO_APPLY"

        return result


async def run_application(job: dict, cv_path: str = None,
                          motivation_path: str = None,
                          headless: bool = True) -> dict:
    """Main entry point for browser automation."""
    bot = ApplicationBot(headless=headless)
    launched = await bot.launch()
    if not launched:
        return {"status": "ERROR", "reason": bot.stop_reason}
    try:
        result = await bot.apply_to_job(job, cv_path, motivation_path)
        return result
    finally:
        await bot.close()


if __name__ == "__main__":
    # Test with a sample (will fail without Playwright installed)
    test_job = {
        "official_url": "https://boards.greenhouse.io/example/jobs/123",
        "company": "Example Corp",
        "title": "Embedded Engineer",
    }
    print("Browser agent initialized.")
    print(f"ATS detection test: {detect_ats_from_url(test_job['official_url'])}")
    print("Stop triggers configured:", list(STOP_TRIGGERS.keys()))
    print("ATS platforms configured:", list(ATS_CONFIGS.keys()))
