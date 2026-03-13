import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..database.db import get_config_value

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_orchestrator = None
_agent_thread: Optional[threading.Thread] = None
_agent_loop: Optional[asyncio.AbstractEventLoop] = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def start_scheduler(app):
    """Start the APScheduler with configured interval."""
    global _scheduler
    scheduler = get_scheduler()

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

    # Schedule auto-run if enabled
    _reschedule_agent(app)


def _reschedule_agent(app):
    """Set up the agent job based on config."""
    global _scheduler
    scheduler = get_scheduler()

    with app.app_context():
        auto_enabled = get_config_value("auto_run_enabled", "false").lower() == "true"
        interval = int(get_config_value("run_interval_minutes", "60"))

    # Remove existing job if present
    if scheduler.get_job("autoapply_agent"):
        scheduler.remove_job("autoapply_agent")

    if auto_enabled:
        scheduler.add_job(
            func=lambda: _run_agent_job(app),
            trigger=IntervalTrigger(minutes=interval),
            id="autoapply_agent",
            name="AutoApply Agent",
            replace_existing=True,
            next_run_time=datetime.utcnow(),
        )
        logger.info(f"Agent scheduled every {interval} minutes")
    else:
        logger.info("Auto-run disabled — agent not scheduled")


def _run_agent_job(app):
    """Run the orchestrator in a thread with its own event loop."""
    global _agent_loop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _agent_loop = loop

    try:
        from ..agents.orchestrator import Orchestrator
        orch = Orchestrator(app)
        loop.run_until_complete(orch.run_once())
    except Exception as e:
        logger.error(f"Scheduled agent run failed: {e}")
    finally:
        loop.close()
        _agent_loop = None


def start_agent_now(app) -> bool:
    """Manually trigger the agent in a background thread."""
    global _agent_thread

    if _agent_thread and _agent_thread.is_alive():
        logger.warning("Agent is already running")
        return False

    _agent_thread = threading.Thread(
        target=_run_agent_job,
        args=(app,),
        daemon=True,
        name="autoapply-agent",
    )
    _agent_thread.start()
    logger.info("Agent started in background thread")
    return True


def stop_agent(app) -> bool:
    """Request the running agent to stop."""
    try:
        from ..agents.orchestrator import Orchestrator
        # Signal stop via a shared flag (best-effort)
        with app.app_context():
            from ..database.db import set_config_value
            set_config_value("agent_stop_requested", "true")
        logger.info("Stop signal sent to agent")
        return True
    except Exception as e:
        logger.error(f"Failed to stop agent: {e}")
        return False


def is_agent_running() -> bool:
    """Check if agent background thread is active."""
    global _agent_thread
    return _agent_thread is not None and _agent_thread.is_alive()


def stop_scheduler():
    """Shut down the APScheduler cleanly."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
