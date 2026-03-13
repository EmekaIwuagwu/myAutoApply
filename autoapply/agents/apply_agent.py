import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List

from ..browser.playwright_engine import PlaywrightEngine
from ..browser.human_simulator import random_delay, human_type, scroll_page
from ..database.db import db, get_config_value
from ..database.models import JobListing, Application, Resume, UserProfile, AgentLog
from ..llm.analyzer import JobAnalyzer
from ..vision.screenshot import take_screenshot

logger = logging.getLogger(__name__)


class ApplyAgent:
    """Agent that fills and submits job applications."""

    def __init__(self, app=None):
        self.app = app
        self.name = "ApplyAgent"
        self.analyzer = JobAnalyzer()

    def _log(self, action: str, status: str, message: str):
        if not self.app:
            logger.info(f"[{self.name}] {action}: {message}")
            return
        with self.app.app_context():
            log = AgentLog(
                agent_name=self.name,
                action=action,
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
            )
            db.session.add(log)
            db.session.commit()

    async def apply_to_job(
        self,
        job_id: int,
        resume_path: str = None,
        dry_run: bool = False,
    ) -> bool:
        """Apply to a job. Returns True on success."""
        if not self.app:
            logger.error("No Flask app context")
            return False

        with self.app.app_context():
            job = JobListing.query.get(job_id)
            if not job:
                self._log("apply", "error", f"Job {job_id} not found")
                return False

            profile = UserProfile.query.first()
            default_resume = Resume.query.filter_by(is_default=True).first()
            if not default_resume:
                default_resume = Resume.query.order_by(Resume.uploaded_at.desc()).first()

            resume_id = None
            if not resume_path and default_resume:
                resume_path = default_resume.file_path
                resume_id = default_resume.id

            job_title = job.title
            job_company = job.company
            job_url = job.url
            job_platform = job.platform
            job_description = job.description or ""

        self._log("apply_start", "info", f"Applying to: {job_title} @ {job_company}")

        # Generate cover letter (only if enabled in config and profile exists)
        cover_letter = ""
        with self.app.app_context():
            gen_cover = get_config_value("generate_cover_letter", "true").lower() == "true"
            profile_data = {
                "name": (profile.name or "") if profile else "",
                "skills": (profile.skills or "") if profile else "",
                "experience_years": (profile.experience_years or 0) if profile else 0,
            }

        if profile and gen_cover:
            try:
                cover_letter = self.analyzer.generate_cover_letter(
                    job_title=job_title,
                    company=job_company,
                    description=job_description,
                    candidate=profile_data,
                )
            except Exception as e:
                logger.warning(f"Cover letter generation failed: {e}")

        # Create application record
        with self.app.app_context():
            application = Application(
                job_id=job_id,
                resume_id=resume_id,
                cover_letter=cover_letter,
                status="pending",
                applied_at=datetime.utcnow(),
            )
            db.session.add(application)
            db.session.commit()
            app_id = application.id

        if dry_run:
            self._log("dry_run", "info", f"Dry run — skipping actual submission for job {job_id}")
            with self.app.app_context():
                app = Application.query.get(app_id)
                job = JobListing.query.get(job_id)
                app.status = "submitted"
                app.notes = "Dry run — not actually submitted"
                job.status = "applied"
                db.session.commit()
            return True

        # Launch browser and apply
        engine = PlaywrightEngine()
        screenshot_path = ""
        success = False

        try:
            await engine.launch()

            if "greenhouse.io" in job_url or "lever.co" in job_url:
                success, screenshot_path = await self._apply_greenhouse(
                    engine, job_url, profile, resume_path, cover_letter
                )
            elif "linkedin.com" in job_url:
                success, screenshot_path = await self._apply_linkedin_easy(
                    engine, job_url, profile, resume_path, cover_letter
                )
            elif "indeed.com" in job_url:
                success, screenshot_path = await self._apply_indeed(
                    engine, job_url, profile, resume_path, cover_letter
                )
            else:
                success, screenshot_path = await self._apply_generic(
                    engine, job_url, profile, resume_path, cover_letter
                )

        except Exception as e:
            self._log("apply_error", "error", f"Application failed for job {job_id}: {e}")
            success = False
        finally:
            await engine.close()

        # Update records
        with self.app.app_context():
            app = Application.query.get(app_id)
            job = JobListing.query.get(job_id)

            app.status = "submitted" if success else "failed"
            app.confirmation_screenshot = screenshot_path
            job.status = "applied" if success else "failed"
            db.session.commit()

        status = "success" if success else "error"
        self._log(
            "apply_complete",
            status,
            f"Application {'submitted' if success else 'failed'} for job {job_id}",
        )
        return success

    async def _apply_greenhouse(
        self,
        engine: PlaywrightEngine,
        url: str,
        profile: Optional[UserProfile],
        resume_path: Optional[str],
        cover_letter: str,
    ) -> tuple[bool, str]:
        """Apply to a Greenhouse/Lever job."""
        try:
            page = await engine.navigate(url)
            await random_delay(2.0, 3.5)

            # Find apply button
            apply_selectors = [
                "a[href*='apply']",
                "button:has-text('Apply')",
                "a:has-text('Apply')",
                "#apply-button",
                ".apply-button",
            ]
            for selector in apply_selectors:
                try:
                    await engine.safe_click(selector, page)
                    await random_delay(1.5, 2.5)
                    break
                except Exception:
                    continue

            if profile:
                await self._fill_common_fields(page, engine, profile, cover_letter)

            # Upload resume
            if resume_path and os.path.exists(resume_path):
                resume_input = await page.query_selector("input[type='file']")
                if resume_input:
                    await resume_input.set_input_files(resume_path)
                    await random_delay(1.0, 2.0)

            screenshot_path = await take_screenshot(page, prefix=f"greenhouse_confirm")

            # Submit form (don't actually submit in safety mode)
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "button:has-text('Submit')",
                "#submit-app",
            ]
            for selector in submit_selectors:
                try:
                    await engine.safe_click(selector, page)
                    await random_delay(2.0, 4.0)
                    screenshot_path = await take_screenshot(page, prefix="greenhouse_submitted")
                    return True, screenshot_path
                except Exception:
                    continue

            return False, screenshot_path

        except Exception as e:
            logger.error(f"Greenhouse apply error: {e}")
            return False, ""

    async def _apply_linkedin_easy(
        self,
        engine: PlaywrightEngine,
        url: str,
        profile: Optional[UserProfile],
        resume_path: Optional[str],
        cover_letter: str,
    ) -> tuple[bool, str]:
        """Apply via LinkedIn Easy Apply."""
        try:
            page = await engine.navigate(url)
            await random_delay(2.0, 3.5)

            # Click Easy Apply
            try:
                await engine.safe_click("button.jobs-apply-button", page)
            except Exception:
                try:
                    await engine.safe_click("button:has-text('Easy Apply')", page)
                except Exception:
                    return False, ""

            await random_delay(1.5, 2.5)

            # Fill multi-step form
            for step in range(10):
                if profile:
                    await self._fill_linkedin_step(page, engine, profile, resume_path, cover_letter)

                screenshot_path = await take_screenshot(page, prefix=f"linkedin_step_{step}")

                # Check for Next/Submit button
                try:
                    next_btn = await page.query_selector("button[aria-label='Continue to next step']")
                    submit_btn = await page.query_selector("button[aria-label='Submit application']")

                    if submit_btn:
                        await submit_btn.click()
                        await random_delay(2.0, 3.0)
                        final_screenshot = await take_screenshot(page, prefix="linkedin_submitted")
                        return True, final_screenshot
                    elif next_btn:
                        await next_btn.click()
                        await random_delay(1.0, 2.0)
                    else:
                        break
                except Exception:
                    break

            return False, screenshot_path if 'screenshot_path' in locals() else ""

        except Exception as e:
            logger.error(f"LinkedIn Easy Apply error: {e}")
            return False, ""

    async def _apply_indeed(
        self,
        engine: PlaywrightEngine,
        url: str,
        profile: Optional[UserProfile],
        resume_path: Optional[str],
        cover_letter: str,
    ) -> tuple[bool, str]:
        """Apply to an Indeed job."""
        try:
            page = await engine.navigate(url)
            await random_delay(2.0, 3.5)

            # Click apply
            try:
                await engine.safe_click("button#indeedApplyButton", page)
            except Exception:
                try:
                    await engine.safe_click("a[href*='apply']", page)
                except Exception:
                    pass

            await random_delay(1.5, 2.5)

            if profile:
                await self._fill_common_fields(page, engine, profile, cover_letter)

            screenshot_path = await take_screenshot(page, prefix="indeed_confirm")
            return False, screenshot_path  # Indeed often redirects externally

        except Exception as e:
            logger.error(f"Indeed apply error: {e}")
            return False, ""

    async def _apply_generic(
        self,
        engine: PlaywrightEngine,
        url: str,
        profile: Optional[UserProfile],
        resume_path: Optional[str],
        cover_letter: str,
    ) -> tuple[bool, str]:
        """Generic form-based application."""
        try:
            page = await engine.navigate(url)
            await random_delay(2.0, 3.5)

            if profile:
                await self._fill_common_fields(page, engine, profile, cover_letter)

            if resume_path and os.path.exists(resume_path):
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(resume_path)
                    await random_delay(1.0, 2.0)

            screenshot_path = await take_screenshot(page, prefix="generic_confirm")
            return False, screenshot_path

        except Exception as e:
            logger.error(f"Generic apply error: {e}")
            return False, ""

    async def _fill_common_fields(
        self,
        page,
        engine: PlaywrightEngine,
        profile,
        cover_letter: str,
    ):
        """Fill common application form fields."""
        # Build field map from profile
        field_map = {}
        if hasattr(profile, '__dict__'):
            field_map = {
                "first_name": (profile.name or "").split()[0] if profile.name else "",
                "last_name": " ".join((profile.name or "").split()[1:]) if profile.name else "",
                "name": profile.name or "",
                "full_name": profile.name or "",
                "email": profile.email or "",
                "phone": profile.phone or "",
                "linkedin": profile.linkedin_url or "",
                "github": profile.github_url or "",
                "location": profile.location or "",
                "cover_letter": cover_letter,
                "cover_letter_text": cover_letter,
            }

        # Common input selectors and their field mapping
        input_mappings = [
            (["[name*='first']", "[id*='first']", "[placeholder*='First']"], "first_name"),
            (["[name*='last']", "[id*='last']", "[placeholder*='Last']"], "last_name"),
            (["[name*='name']", "[id*='name']", "[placeholder*='Name']"], "name"),
            (["[name*='email']", "[id*='email']", "[type='email']"], "email"),
            (["[name*='phone']", "[id*='phone']", "[type='tel']"], "phone"),
            (["[name*='linkedin']", "[id*='linkedin']", "[placeholder*='LinkedIn']"], "linkedin"),
            (["[name*='github']", "[id*='github']", "[placeholder*='GitHub']"], "github"),
        ]

        for selectors, field_key in input_mappings:
            value = field_map.get(field_key, "")
            if not value:
                continue
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.fill(value)
                        await random_delay(0.2, 0.5)
                        break
                except Exception:
                    continue

        # Fill cover letter in textarea
        if cover_letter:
            textarea_selectors = [
                "textarea[name*='cover']",
                "textarea[id*='cover']",
                "textarea[placeholder*='cover']",
                "textarea[name*='message']",
                "textarea",
            ]
            for selector in textarea_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.fill(cover_letter)
                        await random_delay(0.3, 0.8)
                        break
                except Exception:
                    continue

    async def _fill_linkedin_step(self, page, engine, profile, resume_path, cover_letter):
        """Fill fields in a single LinkedIn Easy Apply step."""
        await self._fill_common_fields(page, engine, profile, cover_letter)

        # LinkedIn-specific: upload resume if file input present
        if resume_path and os.path.exists(resume_path):
            try:
                file_input = await page.query_selector("input[type='file'][name*='resume']")
                if not file_input:
                    file_input = await page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(resume_path)
                    await random_delay(0.5, 1.5)
            except Exception:
                pass
