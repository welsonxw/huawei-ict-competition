"""'My farm' game view: one plot's live sensors, recent scans and actuator state shaped for the farm game."""

from datetime import timedelta

from ..models import Scan
from ..models.core import utcnow
from .control import control_state, local_now, rain_forecast_mm
from .iot import monitor

SCAN_DAYS = 14
FIELD_TILES = 50
RAIN_HOURS = 3
SOIL_STATE = {"low": "dry", "ok": "moist", "high": "wet"}


def scan_label(scan):
    return scan.confirmed_label or scan.diagnosis


def farm_view(plot, now=None):
    now = now or utcnow()
    sensors = monitor(plot, hours=24, now=now)
    sensors.pop("history")
    control = control_state(plot, now=now, limit=10)
    scans = (Scan.query.filter(Scan.plot_id == plot.id, Scan.created_at >= now - timedelta(days=SCAN_DAYS))
             .order_by(Scan.created_at.desc()).all())
    sick = [s for s in scans if scan_label(s) != "healthy"]
    plants = min(plot.num_plants or FIELD_TILES, FIELD_TILES)
    return {
        "plot": plot.to_dict(),
        "local_time": local_now(now).strftime("%H:%M"),
        "plants": plants,
        "plants_total": plot.num_plants,
        "soil": SOIL_STATE.get(sensors["status"].get("soil_moisture_pct")),
        "rain_mm_next": rain_forecast_mm(plot, RAIN_HOURS, now),
        "rain_hours": RAIN_HOURS,
        "sick": [{"scan_id": s.id, "disease": scan_label(s), "severity": s.severity, "confidence": s.confidence,
                  "created_at": s.created_at.isoformat() + "Z", "is_simulated": s.is_simulated,
                  "expert_checked": s.review_status in ("confirmed", "corrected")} for s in sick[:plants]],
        "scans_recent": len(scans),
        "scan_days": SCAN_DAYS,
        "scans_simulated": any(s.is_simulated for s in scans),
        "sensors": sensors,
        "control": control,
    }
