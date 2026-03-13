"""Test: Create all tables, insert sample data, query back."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from autoapply.database.db import db, init_db, get_config_value, set_config_value
from autoapply.database.models import (
    UserProfile, Resume, JobListing, Application, AgentLog, AgentConfig
)


def create_test_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret"
    return app


def test_create_tables():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        # All tables should exist (no error means success)
        assert db.engine.dialect.has_table(db.engine.connect(), "user_profile")
        assert db.engine.dialect.has_table(db.engine.connect(), "job_listings")
        assert db.engine.dialect.has_table(db.engine.connect(), "applications")
        assert db.engine.dialect.has_table(db.engine.connect(), "agent_logs")
        print("✓ All tables created successfully")


def test_user_profile_crud():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        # Create
        profile = UserProfile(
            name="Jane Doe",
            email="jane@example.com",
            phone="+1-555-0100",
            skills="Python, FastAPI, PostgreSQL",
            experience_years=5,
            desired_role="Senior Python Developer",
            remote_only=True,
        )
        db.session.add(profile)
        db.session.commit()

        # Read
        fetched = UserProfile.query.filter_by(email="jane@example.com").first()
        assert fetched is not None
        assert fetched.name == "Jane Doe"
        assert fetched.experience_years == 5
        print(f"✓ UserProfile CRUD: {fetched.to_dict()}")


def test_job_listing_crud():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        job = JobListing(
            platform="indeed",
            title="Python Developer",
            company="Acme Corp",
            location="Remote",
            url="https://indeed.com/jobs/12345",
            description="We need a Python expert...",
            salary_range="$100k-$130k",
            status="new",
        )
        db.session.add(job)
        db.session.commit()

        fetched = JobListing.query.filter_by(url="https://indeed.com/jobs/12345").first()
        assert fetched is not None
        assert fetched.company == "Acme Corp"
        print(f"✓ JobListing CRUD: id={fetched.id}, title={fetched.title}")


def test_agent_log_crud():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        log = AgentLog(
            agent_name="TestAgent",
            action="test_action",
            status="info",
            message="Test log entry",
        )
        db.session.add(log)
        db.session.commit()

        fetched = AgentLog.query.filter_by(agent_name="TestAgent").first()
        assert fetched is not None
        assert fetched.message == "Test log entry"
        print(f"✓ AgentLog CRUD: {fetched.to_dict()}")


def test_config_crud():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        # Default configs seeded by init_db
        val = get_config_value("min_fit_score")
        assert val == "0.65", f"Expected '0.65', got '{val}'"

        set_config_value("min_fit_score", "0.75")
        val = get_config_value("min_fit_score")
        assert val == "0.75", f"Expected '0.75', got '{val}'"
        print(f"✓ Config CRUD: min_fit_score = {val}")


def test_application_relationship():
    app = create_test_app()
    init_db(app)
    with app.app_context():
        job = JobListing(
            platform="linkedin",
            title="ML Engineer",
            company="DataCo",
            url="https://linkedin.com/jobs/999",
            status="analyzed",
            fit_score=0.85,
        )
        db.session.add(job)
        db.session.commit()

        application = Application(
            job_id=job.id,
            status="submitted",
            cover_letter="Dear Hiring Manager...",
        )
        db.session.add(application)
        db.session.commit()

        fetched_app = Application.query.first()
        assert fetched_app.job.title == "ML Engineer"
        print(f"✓ Application relationship: job='{fetched_app.job.title}', status={fetched_app.status}")


if __name__ == "__main__":
    print("Running DB tests...")
    test_create_tables()
    test_user_profile_crud()
    test_job_listing_crud()
    test_agent_log_crud()
    test_config_crud()
    test_application_relationship()
    print("\n✅ All DB tests passed!")
