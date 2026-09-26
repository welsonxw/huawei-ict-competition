import io
import logging
import uuid

from PIL import Image, UnidentifiedImageError

from ..extensions import db
from ..models import Plot, Scan
from .action_plan import action_plan
from .config_loader import regions, state_boundaries, thresholds
from .grid import cell_id, nearest_region, region_at
from .predictor import get_predictor
from .profiles import display_name, get_profile
from .risk_engine import invalidate as invalidate_risk
from .storage import get_storage
from .weather import get_forecast

CROPS = ("chilli", "tomato")
MAX_PIXELS = 40_000_000

log = logging.getLogger(__name__)


class ScanError(ValueError):
    pass


def locate(lat, lon):
    cfg = thresholds()
    region = region_at(lat, lon, state_boundaries()) or nearest_region(lat, lon, regions())
    return cell_id(lat, lon, cfg["grid"]["cell_deg"]), region


def create_plot(name, crop, lat, lon, area_m2=None, num_plants=None, is_simulated=False):
    cell, region = locate(lat, lon)
    plot = Plot(name=name, crop=crop, lat=lat, lon=lon, grid_cell=cell, region=region,
                area_m2=area_m2, num_plants=num_plants, is_simulated=is_simulated)
    db.session.add(plot)
    db.session.commit()
    return plot


def run_scan(image_bytes, crop, plot: Plot | None, lat=None, lon=None):
    if crop not in CROPS:
        raise ScanError("crop must be chilli or tomato")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.width * image.height > MAX_PIXELS:
            raise ScanError("image is too large; please use a photo under 40 megapixels")
        image.load()
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ScanError("file is not a readable image") from exc

    if plot is not None:
        if plot.crop != crop:
            raise ScanError(f"{plot.name} is a {plot.crop} plot")
        lat, lon = plot.lat, plot.lon
    if lat is None or lon is None:
        raise ScanError("plot_id or lat/lon is required")

    cfg = thresholds()
    result = get_predictor().predict(image, crop)
    low_conf = result["is_stub"] or result["confidence"] < cfg["scan"]["low_confidence"]

    storage = get_storage()
    key = uuid.uuid4().hex
    jpeg = io.BytesIO()
    image.save(jpeg, format="JPEG", quality=90)
    image_path = storage.save(f"scans/{key}.jpg", jpeg.getvalue(), "image/jpeg")
    heatmap_path = storage.save(f"heatmaps/{key}.png", result["heatmap"], "image/png") if result.get("heatmap") else None

    cell, region = locate(lat, lon)
    scan = Scan(
        plot_id=plot.id if plot else None, crop=crop, diagnosis=result["label"], confidence=result["confidence"],
        top3=result["top3"], severity=result["severity"], lat=lat, lon=lon, grid_cell=cell, region=region,
        image_path=image_path, heatmap_path=heatmap_path, model_version=result["model_version"],
        is_stub=result["is_stub"], review_status="pending" if low_conf else "none",
    )
    db.session.add(scan)
    db.session.commit()
    invalidate_risk()

    return scan, scan_payload(scan, low_conf, result.get("stub_reason"))


def scan_payload(scan: Scan, low_conf, stub_reason=None):
    return {
        "scan": scan.to_dict(),
        "low_confidence": low_conf,
        "stub_reason": stub_reason,
        "display_name": {lang: display_name(scan.crop, scan.effective_label, lang) for lang in ("en", "ms")},
        "top3_names": [
            {**t, "name": {lang: display_name(scan.crop, t["label"], lang) for lang in ("en", "ms")}} for t in scan.top3
        ],
        "action_plan": plan_for(scan, low_conf),
    }


def plan_for(scan: Scan, low_conf):
    plot_name = scan.plot.name if scan.plot else {"en": "this plot", "ms": "plot ini"}
    try:
        forecast = get_forecast(scan.lat, scan.lon)
    except Exception:  # noqa: BLE001 – the scan is saved; a plan without weather is still useful
        log.exception("forecast unavailable for scan %s", scan.id)
        forecast = None
    label = scan.effective_label
    plan = {}
    for lang in ("en", "ms"):
        name = plot_name if isinstance(plot_name, str) else plot_name[lang]
        p = action_plan(label, scan.crop, get_profile(scan.crop, label), name, forecast, thresholds()["weather"],
                        low_confidence=low_conf)
        plan[lang] = p[lang]
        plan["weather"] = p["weather"]
    return plan
