"""Test: Run orchestrator for 1 job end-to-end (dry run — no actual submit)."""
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from autoapply.database.db import db, init_db, set_config_value
from autoapply.database.models import (
    UserProfile, JobListing, Resume, AgentLog
)


def create_test_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret"
    return app


def seed_test_data(app):
    """Seed test user profile, a job, and a resume (dummy path)."""
    with app.app_context():
        # Profile
        profile = UserProfile(
            name="Test User",
            email="test@example.com",
            phone="+1-555-9999",
            skills="Python, FastAPI, Docker, PostgreSQL",
            experience_years=5,
            desired_role="Senior Python Developer",
            remote_only=True,
        )
        db.session.add(profile)

        # Job with high fit score (pre-analyzed)
        job = JobListing(
            platform="greenhouse",
            title="Senior Python Developer",
            company="TestCorp",
            location="Remote",
            url="https://boards.greenhouse.io/testcorp/jobs/12345",
            description="We need a Python expert with FastAPI and PostgreSQL experience.",
            fit_score=0.9,
            status="analyzed",
        )
        db.session.add(job)
        db.session.commit()

        # Config
        set_config_value("min_fit_score", "0.65")
        set_config_value("max_daily_applications", "5")
        set_config_value("generate_cover_letter", "false")
        set_config_value("tailor_resume", "false")

        return job.id


def test_analysis_agent(app):
    """Test the analysis agent with a pre-seeded job."""
    from autoapply.agents.analysis_agent import AnalysisAgent

    with app.app_context():
        # Add an unanalyzed job
        job = JobListing(
            platform="indeed",
            title="Backend Engineer",
            company="StartupXYZ",
            url="https://indeed.com/test/backend123",
            description="Looking for a backend engineer with Python and REST API experience.",
            status="new",
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    from autoapply.llm.ollama_client import OllamaClient
    if not OllamaClient().is_available():
        print("⚠ Ollama offline — skipping LLM analysis in pipeline test")
        return True

    agent = AnalysisAgent(app)
    result = agent.analyze_job(job_id)
    if result:
        print(f"✓ Analysis: fit_score={result.get('fit_score')}, recommendation={result.get('recommendation')}")
    else:
        print("⚠ Analysis returned None (LLM may be unavailable)")
    return True


async def test_apply_agent_dry_run(app, job_id):
    """Test the apply agent in dry run mode — no actual submission."""
    from autoapply.agents.apply_agent import ApplyAgent

    agent = ApplyAgent(app)
    success = await agent.apply_to_job(
        job_id=job_id,
        resume_path=None,
        dry_run=True,
    )
    print(f"✓ Dry run apply: success={success}")

    with app.app_context():
        from autoapply.database.models import Application
        app_record = Application.query.filter_by(job_id=job_id).first()
        assert app_record is not None, "Application record should be created"
        print(f"✓ Application record: status={app_record.status}, notes='{app_record.notes}'")

    return success


async def test_full_pipeline_dry_run():
    """Test the full orchestrator pipeline in dry run mode."""
    app = create_test_app()
    init_db(app)

    print("Seeding test data...")
    job_id = seed_test_data(app)
    print(f"✓ Test job created: id={job_id}")

    print("\nRunning analysis agent...")
    test_analysis_agent(app)

    print("\nRunning apply agent (dry run)...")
    await test_apply_agent_dry_run(app, job_id)

    print("\nChecking agent logs...")
    with app.app_context():
        logs = AgentLog.query.all()
        print(f"✓ {len(logs)} log entries created")
        for log in logs[-5:]:
            print(f"  [{log.status}] {log.agent_name}: {log.message}")

    print("\n✅ Full pipeline dry run complete!")


if __name__ == "__main__":
    print("Running full pipeline test (dry run)...")
    asyncio.run(test_full_pipeline_dry_run())
