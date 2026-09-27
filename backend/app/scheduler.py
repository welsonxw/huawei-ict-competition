"""Background weather + risk refresh every 3 hours (APScheduler). A Redis lock stops duplicate runs
when several gunicorn workers each start a scheduler."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .extensions import cache
from .services.control import run_due_schedules
from .services.device_sim import run_simulated_devices
from .services.risk_engine import refresh_all

log = logging.getLogger(__name__)
LOCK_KEY = "lock:risk-refresh"
SIM_LOCK_KEY = "lock:device-sim"
CONTROL_LOCK_KEY = "lock:control-schedules"


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


def run_device_sim(app):
    with app.app_context():
        try:
            if not cache.client.set(SIM_LOCK_KEY, "1", nx=True, ex=300):
                return
        except Exception:
            log.warning("redis unavailable; skipping device simulator tick", exc_info=True)
            return
        try:
            run_simulated_devices()
        except Exception:
            log.exception("device simulator tick failed")
        finally:
            cache.client.delete(SIM_LOCK_KEY)


def run_control(app):
    with app.app_context():
        try:
            if not cache.client.set(CONTROL_LOCK_KEY, "1", nx=True, ex=55):
                return
        except Exception:
            log.warning("redis unavailable; skipping control schedule tick", exc_info=True)
            return
        try:
            run_due_schedules()
        except Exception:
            log.exception("control schedule tick failed")
        finally:
            cache.client.delete(CONTROL_LOCK_KEY)


def start_scheduler(app):
    sched = BackgroundScheduler(daemon=True, timezone="Asia/Kuala_Lumpur")
    sched.add_job(run_refresh, "interval", hours=3, args=[app], id="risk-refresh", next_run_time=None)
    sched.add_job(run_refresh, "date", args=[app], id="risk-refresh-startup")
    sched.add_job(run_control, "interval", minutes=1, args=[app], id="control-schedules")
    if app.config["ENABLE_DEVICE_SIM"]:
        from .services.config_loader import iot

        with app.app_context():
            minutes = iot()["simulator"]["interval_minutes"]
        sched.add_job(run_device_sim, "interval", minutes=minutes, args=[app], id="device-sim")
    sched.start()
    return sched
