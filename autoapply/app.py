import asyncio
import json
import logging
import os
import threading
from datetime import datetime, date
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    Response,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from .config import config
from .database.db import db, init_db, get_config_value, set_config_value
from .database.models import (
    UserProfile,
    Resume,
    JobListing,
    Application,
    AgentLog,
    AgentConfig,
)
from .llm.ollama_client import OllamaClient
from .scheduler.job_scheduler import (
    start_scheduler,
    start_agent_now,
    stop_agent,
    is_agent_running,
    stop_scheduler,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

    # Ensure upload folders exist
    Path(config.RESUME_UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(config.SCREENSHOT_FOLDER).mkdir(parents=True, exist_ok=True)

    init_db(app)

    # Check Ollama on startup
    with app.app_context():
        ollama = OllamaClient()
        if ollama.is_available():
            logger.info("Ollama is available")
        else:
            logger.warning("Ollama not reachable at %s", config.OLLAMA_URL)

    # Start scheduler
    start_scheduler(app)

    # ─── Dashboard ────────────────────────────────────────────────────────────

    @app.route("/")
    def dashboard():
        total_jobs = JobListing.query.count()
        today = date.today()
        jobs_today = JobListing.query.filter(
            db.func.date(JobListing.scraped_at) == today
        ).count()
        total_apps = Application.query.count()
        apps_today = Application.query.filter(
            db.func.date(Application.applied_at) == today
        ).count()
        submitted = Application.query.filter_by(status="submitted").count()
        success_rate = round((submitted / total_apps * 100) if total_apps > 0 else 0, 1)

        # Platform breakdown
        platforms = db.session.query(
            JobListing.platform, db.func.count(JobListing.id)
        ).group_by(JobListing.platform).all()

        recent_logs = (
            AgentLog.query.order_by(AgentLog.timestamp.desc()).limit(10).all()
        )

        ollama = OllamaClient()
        ollama_ok = ollama.is_available()

        return render_template(
            "dashboard.html",
            total_jobs=total_jobs,
            jobs_today=jobs_today,
            total_apps=total_apps,
            apps_today=apps_today,
            success_rate=success_rate,
            platforms=platforms,
            recent_logs=recent_logs,
            agent_running=is_agent_running(),
            ollama_ok=ollama_ok,
        )

    # ─── Jobs ─────────────────────────────────────────────────────────────────

    @app.route("/jobs")
    def jobs():
        platform = request.args.get("platform", "")
        status = request.args.get("status", "")
        min_score = request.args.get("min_score", "")
        page = request.args.get("page", 1, type=int)

        query = JobListing.query
        if platform:
            query = query.filter_by(platform=platform)
        if status:
            query = query.filter_by(status=status)
        if min_score:
            try:
                query = query.filter(JobListing.fit_score >= float(min_score))
            except ValueError:
                pass

        pagination = query.order_by(JobListing.scraped_at.desc()).paginate(
            page=page, per_page=25, error_out=False
        )

        return render_template(
            "jobs.html",
            jobs=pagination.items,
            pagination=pagination,
            platform=platform,
            status=status,
            min_score=min_score,
        )

    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        job = JobListing.query.get_or_404(job_id)
        fit_data = {}
        if job.fit_reasoning:
            try:
                fit_data = json.loads(job.fit_reasoning)
            except Exception:
                pass
        applications = Application.query.filter_by(job_id=job_id).all()
        return render_template(
            "job_detail.html", job=job, fit_data=fit_data, applications=applications
        )

    # ─── Applications ─────────────────────────────────────────────────────────

    @app.route("/applications")
    def applications():
        page = request.args.get("page", 1, type=int)
        status = request.args.get("status", "")

        query = Application.query
        if status:
            query = query.filter_by(status=status)

        pagination = query.order_by(Application.applied_at.desc()).paginate(
            page=page, per_page=25, error_out=False
        )
        return render_template(
            "applications.html", applications=pagination.items, pagination=pagination, status=status
        )

    @app.route("/applications/<int:app_id>")
    def application_detail(app_id):
        application = Application.query.get_or_404(app_id)
        return render_template("application_detail.html", application=application)

    # ─── Resume ───────────────────────────────────────────────────────────────

    @app.route("/resume", methods=["GET", "POST"])
    def resume_page():
        if request.method == "POST":
            if "resume_file" not in request.files:
                flash("No file selected", "error")
                return redirect(url_for("resume_page"))

            file = request.files["resume_file"]
            if file.filename == "":
                flash("No file selected", "error")
                return redirect(url_for("resume_page"))

            if not _allowed_file(file.filename):
                flash("Only PDF and DOCX files are allowed", "error")
                return redirect(url_for("resume_page"))

            filename = secure_filename(file.filename)
            filepath = os.path.join(config.RESUME_UPLOAD_FOLDER, filename)
            file.save(filepath)

            ext = os.path.splitext(filename)[1].lstrip(".")
            is_first = Resume.query.count() == 0

            # Set all others as non-default if this will be default
            if is_first or request.form.get("set_default"):
                Resume.query.update({"is_default": False})

            resume = Resume(
                filename=filename,
                file_path=filepath,
                file_type=ext,
                is_default=is_first or bool(request.form.get("set_default")),
                uploaded_at=datetime.utcnow(),
            )
            db.session.add(resume)
            db.session.commit()
            flash("Resume uploaded successfully", "success")
            return redirect(url_for("resume_page"))

        resumes = Resume.query.order_by(Resume.uploaded_at.desc()).all()
        return render_template("resume.html", resumes=resumes)

    @app.route("/resume/<int:resume_id>/set-default", methods=["POST"])
    def set_default_resume(resume_id):
        Resume.query.update({"is_default": False})
        resume = Resume.query.get_or_404(resume_id)
        resume.is_default = True
        db.session.commit()
        flash("Default resume updated", "success")
        return redirect(url_for("resume_page"))

    @app.route("/resume/<int:resume_id>/delete", methods=["POST"])
    def delete_resume(resume_id):
        resume = Resume.query.get_or_404(resume_id)
        try:
            if os.path.exists(resume.file_path):
                os.remove(resume.file_path)
        except Exception:
            pass
        db.session.delete(resume)
        db.session.commit()
        flash("Resume deleted", "success")
        return redirect(url_for("resume_page"))

    # ─── Settings ─────────────────────────────────────────────────────────────

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            form_type = request.form.get("form_type")

            if form_type == "profile":
                profile = UserProfile.query.first() or UserProfile()
                profile.name = request.form.get("name", "")
                profile.email = request.form.get("email", "")
                profile.phone = request.form.get("phone", "")
                profile.location = request.form.get("location", "")
                profile.linkedin_url = request.form.get("linkedin_url", "")
                profile.github_url = request.form.get("github_url", "")
                profile.skills = request.form.get("skills", "")
                profile.experience_years = int(request.form.get("experience_years", 0) or 0)
                profile.desired_role = request.form.get("desired_role", "")
                profile.desired_salary = request.form.get("desired_salary", "")
                profile.remote_only = request.form.get("remote_only") == "on"
                if not profile.id:
                    db.session.add(profile)
                db.session.commit()
                flash("Profile saved", "success")

            elif form_type == "agent_config":
                config_keys = [
                    "max_daily_applications",
                    "min_fit_score",
                    "search_keywords",
                    "search_location",
                    "blacklisted_companies",
                    "tailor_resume",
                    "generate_cover_letter",
                    "auto_run_enabled",
                    "run_interval_minutes",
                ]
                for key in config_keys:
                    value = request.form.get(key, "")
                    if key in ("tailor_resume", "generate_cover_letter", "auto_run_enabled"):
                        value = "true" if request.form.get(key) else "false"
                    set_config_value(key, value)
                flash("Agent config saved", "success")

            elif form_type == "credentials":
                cred_keys = [
                    "linkedin_email", "linkedin_password",
                    "indeed_email", "indeed_password",
                ]
                for key in cred_keys:
                    value = request.form.get(key, "")
                    if value:  # Only update if provided
                        set_config_value(key, value)
                flash("Credentials saved", "success")

            elif form_type == "ollama":
                set_config_value("ollama_url", request.form.get("ollama_url", config.OLLAMA_URL))
                set_config_value("ollama_model", request.form.get("ollama_model", config.OLLAMA_MODEL))
                flash("Ollama config saved", "success")

            return redirect(url_for("settings"))

        profile = UserProfile.query.first()
        cfg = {r.key: r.value for r in AgentConfig.query.all()}

        return render_template("settings.html", profile=profile, cfg=cfg)

    # ─── Logs ─────────────────────────────────────────────────────────────────

    @app.route("/logs")
    def logs():
        agent_name = request.args.get("agent", "")
        status = request.args.get("status", "")
        page = request.args.get("page", 1, type=int)

        query = AgentLog.query
        if agent_name:
            query = query.filter_by(agent_name=agent_name)
        if status:
            query = query.filter_by(status=status)

        pagination = query.order_by(AgentLog.timestamp.desc()).paginate(
            page=page, per_page=50, error_out=False
        )

        agents = db.session.query(AgentLog.agent_name).distinct().all()
        agents = [a[0] for a in agents]

        return render_template(
            "logs.html",
            logs=pagination.items,
            pagination=pagination,
            agent_name=agent_name,
            status=status,
            agents=agents,
        )

    @app.route("/logs/stream")
    def logs_stream():
        """SSE endpoint for real-time log streaming."""
        def generate():
            last_id = AgentLog.query.count()
            while True:
                import time
                time.sleep(3)
                new_logs = (
                    AgentLog.query.filter(AgentLog.id > last_id)
                    .order_by(AgentLog.timestamp.asc())
                    .all()
                )
                if new_logs:
                    for log in new_logs:
                        data = json.dumps(log.to_dict())
                        yield f"data: {data}\n\n"
                    last_id = new_logs[-1].id
                else:
                    yield "data: {\"heartbeat\": true}\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ─── API ──────────────────────────────────────────────────────────────────

    @app.route("/api/agent/start", methods=["POST"])
    def api_agent_start():
        if is_agent_running():
            return jsonify({"status": "error", "message": "Agent already running"}), 409

        set_config_value("agent_stop_requested", "false")
        success = start_agent_now(app)
        if success:
            return jsonify({"status": "success", "message": "Agent started"})
        return jsonify({"status": "error", "message": "Failed to start agent"}), 500

    @app.route("/api/agent/stop", methods=["POST"])
    def api_agent_stop():
        stop_agent(app)
        return jsonify({"status": "success", "message": "Stop signal sent"})

    @app.route("/api/agent/status", methods=["GET"])
    def api_agent_status():
        today = date.today()
        apps_today = Application.query.filter(
            db.func.date(Application.applied_at) == today
        ).count()
        max_apps = int(get_config_value("max_daily_applications", "20"))
        total_jobs = JobListing.query.count()
        total_apps = Application.query.count()

        return jsonify(
            {
                "running": is_agent_running(),
                "apps_today": apps_today,
                "max_daily_apps": max_apps,
                "total_jobs": total_jobs,
                "total_applications": total_apps,
                "ollama_ok": OllamaClient().is_available(),
            }
        )

    @app.route("/api/jobs/scrape", methods=["POST"])
    def api_jobs_scrape():
        """Trigger a manual scrape (search only, no analysis or apply)."""
        def _run_scrape():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from .agents.search_agent import SearchAgent
                agent = SearchAgent(app)
                loop.run_until_complete(agent.run())
            finally:
                loop.close()

        t = threading.Thread(target=_run_scrape, daemon=True)
        t.start()
        return jsonify({"status": "success", "message": "Scrape started in background"})

    @app.route("/api/jobs/<int:job_id>/analyze", methods=["POST"])
    def api_analyze_job(job_id):
        job = JobListing.query.get_or_404(job_id)
        from .agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent(app)
        result = agent.analyze_job(job_id)
        if result:
            return jsonify({"status": "success", "fit_score": result.get("fit_score"), "result": result})
        return jsonify({"status": "error", "message": "Analysis failed"}), 500

    @app.route("/api/jobs/<int:job_id>/apply", methods=["POST"])
    def api_apply_job(job_id):
        JobListing.query.get_or_404(job_id)
        dry_run = request.json.get("dry_run", False) if request.is_json else False

        def _run_apply():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from .agents.apply_agent import ApplyAgent
                from .agents.resume_agent import ResumeAgent
                resume_agent = ResumeAgent(app)
                resume_path = resume_agent.get_resume_for_job(job_id)
                agent = ApplyAgent(app)
                loop.run_until_complete(
                    agent.apply_to_job(job_id, resume_path=resume_path, dry_run=dry_run)
                )
            finally:
                loop.close()

        t = threading.Thread(target=_run_apply, daemon=True)
        t.start()
        return jsonify({"status": "success", "message": "Application started in background"})

    @app.route("/api/jobs/<int:job_id>/skip", methods=["POST"])
    def api_skip_job(job_id):
        job = JobListing.query.get_or_404(job_id)
        job.status = "skipped"
        db.session.commit()
        return jsonify({"status": "success"})

    @app.route("/api/jobs/export")
    def api_export_jobs():
        """Export all applications as CSV."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Job Title", "Company", "Platform", "Status", "Fit Score", "Applied At"])

        apps = (
            db.session.query(Application, JobListing)
            .join(JobListing, Application.job_id == JobListing.id)
            .order_by(Application.applied_at.desc())
            .all()
        )
        for app_obj, job_obj in apps:
            writer.writerow([
                app_obj.id,
                job_obj.title,
                job_obj.company,
                job_obj.platform,
                app_obj.status,
                job_obj.fit_score,
                app_obj.applied_at.isoformat() if app_obj.applied_at else "",
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=applications.csv"},
        )

    @app.route("/uploads/screenshots/<path:filename>")
    def serve_screenshot(filename):
        return send_from_directory(config.SCREENSHOT_FOLDER, filename)

    return app


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
