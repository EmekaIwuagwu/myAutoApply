import logging
from datetime import datetime
from typing import Optional

from ..database.db import db, get_config_value
from ..database.models import Resume, JobListing, AgentLog
from ..resume.tailorer import ResumeTailorer
from ..config import config

logger = logging.getLogger(__name__)


class ResumeAgent:
    """Agent that tailors resumes for specific job applications."""

    def __init__(self, app=None):
        self.app = app
        self.name = "ResumeAgent"
        self.tailorer = ResumeTailorer()

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

    def get_resume_for_job(self, job_id: int) -> Optional[str]:
        """Get the best resume path for a job (tailored or default)."""
        if not self.app:
            return None

        tailor_enabled = get_config_value("tailor_resume", "true").lower() == "true"

        with self.app.app_context():
            job = JobListing.query.get(job_id)
            if not job:
                return None

            default_resume = Resume.query.filter_by(is_default=True).first()
            if not default_resume:
                default_resume = Resume.query.order_by(Resume.uploaded_at.desc()).first()

            if not default_resume:
                self._log("get_resume", "warning", "No resume uploaded")
                return None

            if not tailor_enabled:
                return default_resume.file_path

            # Try to tailor the resume
            self._log("tailor_start", "info", f"Tailoring resume for: {job.title} @ {job.company}")
            try:
                tailored_path = self.tailorer.tailor_for_job(
                    resume_path=default_resume.file_path,
                    job_title=job.title,
                    job_description=job.description or "",
                    output_dir=config.RESUME_UPLOAD_FOLDER,
                )

                if tailored_path and tailored_path != default_resume.file_path:
                    # Save tailored resume to DB
                    import os
                    tailored_resume = Resume(
                        filename=os.path.basename(tailored_path),
                        file_path=tailored_path,
                        file_type=os.path.splitext(tailored_path)[1].lstrip("."),
                        is_default=False,
                        uploaded_at=datetime.utcnow(),
                    )
                    db.session.add(tailored_resume)
                    db.session.commit()
                    self._log("tailor_complete", "success", f"Tailored resume created: {tailored_path}")
                    return tailored_path
                else:
                    return default_resume.file_path

            except Exception as e:
                self._log("tailor_error", "error", f"Resume tailoring failed: {e}")
                return default_resume.file_path
