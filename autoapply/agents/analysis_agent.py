import json
import logging
from datetime import datetime
from typing import Optional

from ..database.db import db
from ..database.models import JobListing, UserProfile, AgentLog
from ..llm.analyzer import JobAnalyzer

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Agent that uses LLM to score job listings for fit."""

    def __init__(self, app=None):
        self.app = app
        self.name = "AnalysisAgent"
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

    def analyze_job(self, job_id: int) -> Optional[dict]:
        """Analyze a single job listing and update fit score in DB."""
        if not self.app:
            return None

        with self.app.app_context():
            job = JobListing.query.get(job_id)
            if not job:
                self._log("analyze", "error", f"Job {job_id} not found")
                return None

            profile = UserProfile.query.first()
            if not profile:
                self._log("analyze", "warning", "No user profile found — using defaults")
                candidate = {
                    "name": "Candidate",
                    "skills": "",
                    "experience_years": 0,
                    "desired_role": "",
                }
            else:
                candidate = {
                    "name": profile.name or "Candidate",
                    "skills": profile.skills or "",
                    "experience_years": profile.experience_years or 0,
                    "desired_role": profile.desired_role or "",
                }

            self._log("analyze_start", "info", f"Analyzing job: {job.title} @ {job.company}")

            try:
                result = self.analyzer.analyze_fit(
                    job_title=job.title,
                    company=job.company,
                    job_description=job.description or "",
                    candidate=candidate,
                )

                job.fit_score = result.get("fit_score", 0.5)
                job.fit_reasoning = json.dumps(result)
                job.status = "analyzed"
                db.session.commit()

                self._log(
                    "analyze_complete",
                    "success",
                    f"Job {job_id} scored {job.fit_score:.2f}: {result.get('summary', '')}",
                )
                return result

            except Exception as e:
                job.status = "failed"
                db.session.commit()
                self._log("analyze_error", "error", f"Analysis failed for job {job_id}: {e}")
                return None

    def analyze_all_new(self) -> int:
        """Analyze all unanalyzed jobs. Returns count analyzed."""
        if not self.app:
            return 0

        with self.app.app_context():
            new_jobs = JobListing.query.filter_by(status="new").all()
            job_ids = [j.id for j in new_jobs]

        self._log("batch_analyze", "info", f"Analyzing {len(job_ids)} new jobs")
        analyzed = 0
        for job_id in job_ids:
            result = self.analyze_job(job_id)
            if result:
                analyzed += 1

        self._log("batch_complete", "success", f"Analyzed {analyzed}/{len(job_ids)} jobs")
        return analyzed
