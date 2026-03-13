import asyncio
import logging
import os
import tempfile
import threading
from datetime import datetime
from typing import Optional

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..database.db import get_config_value

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_agent_thread: Optional[threading.Thread] = None
_agent_loop: Optional[asyncio.AbstractEventLoop] = None

# Under gunicorn each worker process is a fork. We only want the scheduler
# running in ONE process. Use a file-lock so only the first worker wins.
_SCHEDULER_LOCK_FILE = os.path.join(tempfile.gettempdir(), "autoapply_scheduler.lock")
_scheduler_owner = False  # True only in the process that holds the lock


def _try_acquire_scheduler_lock() -> bool:
    """Return True if this process successfully claimed the scheduler lock.

    On Windows (dev server) fcntl is not available — always return True since
    there is only one process anyway.
    """
    if not _HAS_FCNTL:
        return True
    try:
        fd = open(_SCHEDULER_LOCK_FILE, "w")
        _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        # Keep fd open so the lock is held for the life of this process
        _try_acquire_scheduler_lock._fd = fd
        return True
    except (IOError, OSError):
        return False


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def start_scheduler(app):
    """Start the APScheduler — only in one gunicorn worker."""
    global _scheduler_owner
    if not _try_acquire_scheduler_lock():
        logger.info("Scheduler already running in another worker — skipping")
        return

    _scheduler_owner = True
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started (pid=%s)", os.getpid())

    _reschedule_agent(app)


def _reschedule_agent(app):
    """Configure the auto-run schedule from DB config."""
    scheduler = get_scheduler()

    with app.app_context():
        auto_enabled = get_config_value("auto_run_enabled", "false").lower() == "true"
        interval = int(get_config_value("run_interval_minutes", "60"))

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
        logger.info("Agent scheduled every %s minutes", interval)
    else:
        logger.info("Auto-run disabled — agent not scheduled")


def _run_agent_job(app):
    """Run the orchestrator in a dedicated thread with its own event loop."""
    global _agent_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _agent_loop = loop
    try:
        from ..agents.orchestrator import Orchestrator
        orch = Orchestrator(app)
        loop.run_until_complete(orch.run_once())
    except Exception as e:
        logger.error("Scheduled agent run failed: %s", e)
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
    """Send stop signal to the running agent via DB flag."""
    try:
        with app.app_context():
            from ..database.db import set_config_value
            set_config_value("agent_stop_requested", "true")
        logger.info("Stop signal sent to agent")
        return True
    except Exception as e:
        logger.error("Failed to stop agent: %s", e)
        return False


def is_agent_running() -> bool:
    global _agent_thread
    return _agent_thread is not None and _agent_thread.is_alive()


def stop_scheduler():
    """Shut down the APScheduler cleanly."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    # Release lock file
    try:
        if hasattr(_try_acquire_scheduler_lock, "_fd"):
            _try_acquire_scheduler_lock._fd.close()
        if os.path.exists(_SCHEDULER_LOCK_FILE):
            os.remove(_SCHEDULER_LOCK_FILE)
    except Exception:
        pass
