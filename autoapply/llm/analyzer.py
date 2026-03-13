import json
import logging
from .ollama_client import OllamaClient
from .prompts import JOB_FIT_PROMPT, COVER_LETTER_PROMPT, RESUME_TAILOR_PROMPT

logger = logging.getLogger(__name__)


class JobAnalyzer:
    """LLM-powered job description analysis."""

    def __init__(self, client: OllamaClient = None):
        from .ollama_client import ollama_client
        self.client = client or ollama_client

    def analyze_fit(
        self,
        job_title: str,
        company: str,
        job_description: str,
        candidate: dict,
    ) -> dict:
        """Analyze job fit using LLM. Returns fit data dict."""
        prompt = JOB_FIT_PROMPT.format(
            job_title=job_title,
            company=company,
            job_description=job_description[:3000],  # Truncate long descriptions
            name=candidate.get("name", "Candidate"),
            skills=candidate.get("skills", ""),
            experience_years=candidate.get("experience_years", 0),
            desired_role=candidate.get("desired_role", ""),
        )

        try:
            result = self.client.generate_json(prompt)
            if not result:
                logger.warning("Empty JSON response from Ollama for fit analysis")
                return self._default_fit_result()

            # Validate and clamp fit_score
            fit_score = float(result.get("fit_score", 0.5))
            fit_score = max(0.0, min(1.0, fit_score))
            result["fit_score"] = fit_score
            return result
        except Exception as e:
            logger.error(f"Job fit analysis failed: {e}")
            return self._default_fit_result()

    def generate_cover_letter(
        self,
        job_title: str,
        company: str,
        description: str,
        candidate: dict,
    ) -> str:
        """Generate a cover letter for the job."""
        prompt = COVER_LETTER_PROMPT.format(
            job_title=job_title,
            company=company,
            description_excerpt=description[:1500],
            name=candidate.get("name", "Candidate"),
            experience_years=candidate.get("experience_years", 0),
            skills=candidate.get("skills", ""),
        )

        try:
            return self.client.generate(prompt).strip()
        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return ""

    def tailor_resume(
        self,
        job_title: str,
        job_description: str,
        resume_summary: str,
    ) -> dict:
        """Generate resume tailoring suggestions."""
        prompt = RESUME_TAILOR_PROMPT.format(
            job_title=job_title,
            job_description=job_description[:2000],
            resume_summary=resume_summary[:1000],
        )

        try:
            result = self.client.generate_json(prompt)
            return result if result else {}
        except Exception as e:
            logger.error(f"Resume tailoring failed: {e}")
            return {}

    def _default_fit_result(self) -> dict:
        return {
            "fit_score": 0.5,
            "reasons_for": ["Unable to analyze — LLM unavailable"],
            "concerns": ["Analysis could not be completed"],
            "recommendation": "NO",
            "summary": "LLM analysis unavailable",
        }


analyzer = JobAnalyzer()
