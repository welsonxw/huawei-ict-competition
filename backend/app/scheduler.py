"""Background weather + risk refresh every 3 hours (APScheduler). A Redis lock stops duplicate runs
when several gunicorn workers each start a scheduler."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .extensions import cache
from .services.risk_engine import refresh_all

log = logging.getLogger(__name__)
LOCK_KEY = "lock:risk-refresh"


def run_refresh(app):
    with app.app_context():
        try:
            if not cache.client.set(LOCK_KEY, "1", nx=True, ex=600):
                return
        except Exception:  # noqa: BLE001
            log.warning("redis unavailable; skipping scheduled refresh", exc_info=True)
            return
        try:
            refresh_all()
        except Exception:  # noqa: BLE001
            log.exception("scheduled risk refresh failed")
        finally:
            cache.client.delete(LOCK_KEY)


def start_scheduler(app):
    sched = BackgroundScheduler(daemon=True, timezone="Asia/Kuala_Lumpur")
    sched.add_job(run_refresh, "interval", hours=3, args=[app], id="risk-refresh", next_run_time=None)
    sched.add_job(run_refresh, "date", args=[app], id="risk-refresh-startup")
    sched.start()
    return sched
