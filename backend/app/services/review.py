"""Expert review: confirm or correct a scan label, and export confirmed scans as a folder-per-class dataset."""
import csv
import io
import json
import zipfile
from pathlib import Path

from flask import current_app

from ml.labels import CHILLI_LABELS, TOMATO_LABEL_MAP

from ..extensions import db
from ..models import ConfirmedLabel, Scan
from .profiles import display_name
from .risk_engine import invalidate
from .storage import get_storage

LABELS = {"chilli": list(CHILLI_LABELS), "tomato": sorted(TOMATO_LABEL_MAP.values())}


class ReviewError(ValueError):
    pass


def label_options(crop):
    return [{"label": x, "name": {lang: display_name(crop, x, lang) for lang in ("en", "ms")}} for x in LABELS[crop]]


def review(scan: Scan, label, reviewer):
    if label not in LABELS[scan.crop]:
        raise ReviewError(f"label must be one of {LABELS[scan.crop]}")
    row = ConfirmedLabel.query.filter_by(scan_id=scan.id).one_or_none() or ConfirmedLabel(scan_id=scan.id)
    row.crop, row.label, row.model_label, row.reviewer = scan.crop, label, scan.diagnosis, reviewer
    scan.confirmed_label = label
    scan.review_status = "confirmed" if label == scan.diagnosis else "corrected"
    db.session.add(row)
    db.session.commit()
    invalidate()
    return scan


def confirmed_rows(crop=None):
    q = (db.session.query(ConfirmedLabel, Scan).join(Scan, Scan.id == ConfirmedLabel.scan_id)
         .filter(Scan.is_simulated.is_(False), Scan.image_path.isnot(None)))
    if crop:
        q = q.filter(ConfirmedLabel.crop == crop)
    return q.order_by(ConfirmedLabel.id).all()


def training_set_zip(crop=None):
    """Zip laid out as <crop>/<label>/scan_<id>.jpg plus manifest.csv; each <crop>/ folder feeds ml/train.py --extra."""
    storage = get_storage()
    buf = io.BytesIO()
    manifest = io.StringIO()
    writer = csv.writer(manifest)
    writer.writerow(["scan_id", "crop", "label", "model_label", "reviewer", "confirmed_at"])
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cl, scan in confirmed_rows(crop):
            zf.writestr(f"{cl.crop}/{cl.label}/scan_{scan.id}.jpg", storage.read(scan.image_path))
            writer.writerow([scan.id, cl.crop, cl.label, cl.model_label, cl.reviewer or "", cl.created_at.isoformat()])
            n += 1
        zf.writestr("manifest.csv", manifest.getvalue())
    buf.seek(0)
    return buf, n


def model_metrics():
    path = Path(current_app.config["MODEL_DIR"]) / "metrics.json"
    if not path.exists():
        return {"runs": []}
    return json.loads(path.read_text())
