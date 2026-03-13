from datetime import datetime
from .db import db


class UserProfile(db.Model):
    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    email = db.Column(db.Text)
    phone = db.Column(db.Text)
    location = db.Column(db.Text)
    linkedin_url = db.Column(db.Text)
    github_url = db.Column(db.Text)
    skills = db.Column(db.Text)  # comma-separated
    experience_years = db.Column(db.Integer, default=0)
    desired_role = db.Column(db.Text)
    desired_salary = db.Column(db.Text)
    remote_only = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "skills": self.skills,
            "experience_years": self.experience_years,
            "desired_role": self.desired_role,
            "desired_salary": self.desired_salary,
            "remote_only": self.remote_only,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.Text)
    file_path = db.Column(db.Text)
    file_type = db.Column(db.Text)  # pdf/docx
    is_default = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "is_default": self.is_default,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class JobListing(db.Model):
    __tablename__ = "job_listings"

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.Text)  # linkedin/indeed/greenhouse/remoteco
    title = db.Column(db.Text)
    company = db.Column(db.Text)
    location = db.Column(db.Text)
    url = db.Column(db.Text, unique=True)
    description = db.Column(db.Text)
    salary_range = db.Column(db.Text)
    posted_date = db.Column(db.Text)
    fit_score = db.Column(db.Float, default=0.0)
    fit_reasoning = db.Column(db.Text)
    status = db.Column(db.Text, default="new")  # new/analyzed/applied/skipped/failed
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("Application", backref="job", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "salary_range": self.salary_range,
            "posted_date": self.posted_date,
            "fit_score": self.fit_score,
            "fit_reasoning": self.fit_reasoning,
            "status": self.status,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job_listings.id"), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=True)
    cover_letter = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Text, default="pending")  # pending/submitted/failed/rejected/interview
    notes = db.Column(db.Text)
    confirmation_screenshot = db.Column(db.Text)

    resume = db.relationship("Resume", backref="applications", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "resume_id": self.resume_id,
            "cover_letter": self.cover_letter,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "status": self.status,
            "notes": self.notes,
            "confirmation_screenshot": self.confirmation_screenshot,
        }


class PlatformSession(db.Model):
    __tablename__ = "platform_sessions"

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.Text)
    username = db.Column(db.Text)
    session_cookies = db.Column(db.Text)  # JSON blob
    is_active = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "username": self.username,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class AgentLog(db.Model):
    __tablename__ = "agent_logs"

    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.Text)
    action = db.Column(db.Text)
    status = db.Column(db.Text, default="info")  # info/success/warning/error
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class AgentConfig(db.Model):
    __tablename__ = "agent_config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.Text, unique=True)
    value = db.Column(db.Text)

    def to_dict(self):
        return {"id": self.id, "key": self.key, "value": self.value}
