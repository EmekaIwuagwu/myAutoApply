import asyncio
import logging
from datetime import datetime, date
from typing import Optional

from ..database.db import db, get_config_value
from ..database.models import JobListing, Application, AgentLog
from .search_agent import SearchAgent
from .analysis_agent import AnalysisAgent
from .resume_agent import ResumeAgent
from .apply_agent import ApplyAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Master agent — coordinates the full job application pipeline."""

    def __init__(self, app=None):
        self.app = app
        self.name = "Orchestrator"
        self._running = False
        self._stop_requested = False

        self.search_agent = SearchAgent(app)
        self.analysis_agent = AnalysisAgent(app)
        self.resume_agent = ResumeAgent(app)
        self.apply_agent = ApplyAgent(app)

    @property
    def is_running(self) -> bool:
        return self._running

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

    def _get_daily_application_count(self) -> int:
        """Get the number of applications submitted today."""
        if not self.app:
            return 0
        with self.app.app_context():
            today = date.today()
            count = Application.query.filter(
                Application.status == "submitted",
                db.func.date(Application.applied_at) == today,
            ).count()
            return count

    async def run_once(self, dry_run: bool = False) -> dict:
        """Run the full pipeline once. Returns summary stats."""
        if self._running:
            return {"status": "already_running"}

        self._running = True
        self._stop_requested = False
        stats = {
            "jobs_found": 0,
            "jobs_analyzed": 0,
            "jobs_applied": 0,
            "jobs_skipped": 0,
            "errors": 0,
        }

        self._log("pipeline_start", "info", "Starting AutoApply pipeline")

        try:
            # Step 1: Search for jobs
            if self._stop_requested:
                return stats
            self._log("search_start", "info", "Step 1: Searching for jobs")
            keywords_str = get_config_value("search_keywords", "Python Developer")
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            location = get_config_value("search_location", "Remote")

            jobs_found = await self.search_agent.run(keywords, location)
            stats["jobs_found"] = jobs_found
            self._log("search_done", "success", f"Found {jobs_found} new jobs")

            # Step 2: Analyze new jobs
            if self._stop_requested:
                return stats
            self._log("analyze_start", "info", "Step 2: Analyzing job fit scores")
            analyzed = self.analysis_agent.analyze_all_new()
            stats["jobs_analyzed"] = analyzed

            # Step 3: Apply to qualifying jobs
            if self._stop_requested:
                return stats

            max_apps = int(get_config_value("max_daily_applications", "20"))
            min_score = float(get_config_value("min_fit_score", "0.65"))
            blacklist = get_config_value("blacklisted_companies", "").lower().split(",")
            blacklist = [b.strip() for b in blacklist if b.strip()]

            daily_count = self._get_daily_application_count()
            remaining = max_apps - daily_count

            if remaining <= 0:
                self._log(
                    "daily_limit",
                    "warning",
                    f"Daily application limit reached ({max_apps})",
                )
            else:
                self._log(
                    "apply_start",
                    "info",
                    f"Step 3: Applying to jobs (budget: {remaining} remaining today)",
                )

                # Get qualifying jobs
                with self.app.app_context():
                    qualifying = (
                        JobListing.query.filter(
                            JobListing.status == "analyzed",
                            JobListing.fit_score >= min_score,
                        )
                        .order_by(JobListing.fit_score.desc())
                        .limit(remaining)
                        .all()
                    )
                    qualifying_data = [
                        {"id": j.id, "title": j.title, "company": j.company}
                        for j in qualifying
                        if j.company.lower() not in blacklist
                    ]

                for job_info in qualifying_data:
                    if self._stop_requested:
                        break

                    job_id = job_info["id"]

                    # Get tailored resume
                    resume_path = self.resume_agent.get_resume_for_job(job_id)

                    # Apply
                    try:
                        success = await self.apply_agent.apply_to_job(
                            job_id=job_id,
                            resume_path=resume_path,
                            dry_run=dry_run,
                        )
                        if success:
                            stats["jobs_applied"] += 1
                        else:
                            stats["errors"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        self._log("apply_error", "error", f"Error applying to job {job_id}: {e}")

                    # Respect rate limiting
                    await asyncio.sleep(5)

            self._log(
                "pipeline_complete",
                "success",
                f"Pipeline done. Found: {stats['jobs_found']}, Analyzed: {stats['jobs_analyzed']}, "
                f"Applied: {stats['jobs_applied']}, Errors: {stats['errors']}",
            )

        except Exception as e:
            self._log("pipeline_error", "error", f"Pipeline failed: {e}")
            stats["errors"] += 1
        finally:
            self._running = False

        return stats

    def stop(self):
        """Request the agent to stop after current operation."""
        self._stop_requested = True
        self._log("stop_requested", "warning", "Stop requested — will halt after current operation")

    async def run_loop(self, interval_minutes: int = 60, dry_run: bool = False):
        """Run the pipeline on a recurring interval."""
        self._log(
            "loop_start",
            "info",
            f"Starting agent loop (every {interval_minutes} minutes)",
        )
        while not self._stop_requested:
            await self.run_once(dry_run=dry_run)
            if not self._stop_requested:
                self._log(
                    "loop_wait",
                    "info",
                    f"Waiting {interval_minutes} minutes before next run",
                )
                await asyncio.sleep(interval_minutes * 60)

        self._log("loop_stopped", "info", "Agent loop stopped")
