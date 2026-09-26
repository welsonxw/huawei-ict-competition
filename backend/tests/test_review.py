import io
import json
import zipfile

import pytest

from app.extensions import db
from app.models import ConfirmedLabel, Scan
from app.services.scans import locate
from conftest import login


@pytest.fixture
def storage(app, tmp_path):
    app.config["LOCAL_STORAGE_DIR"] = tmp_path
    app.extensions.pop("storage", None)
    from app.services.storage import get_storage

    return get_storage()


def make_scan(storage, diagnosis="anthracnose", status="pending", simulated=False, crop="chilli"):
    cell, region = locate(1.85, 103.33)
    path = storage.save(f"scans/{diagnosis}-{simulated}.jpg", b"jpegbytes", "image/jpeg")
    s = Scan(crop=crop, diagnosis=diagnosis, confidence=0.4, top3=[], severity=0.2, lat=1.85, lon=103.33,
             grid_cell=cell, region=region, image_path=path, review_status=status, is_simulated=simulated)
    db.session.add(s)
    db.session.commit()
    return s


def test_auth_roles(client, storage):
    scan = make_scan(storage)
    assert client.get("/api/review/queue").status_code == 401
    assert client.get("/api/scans").status_code == 401
    assert client.get(f"/api/scans/{scan.id}/image").status_code == 401
    assert client.post("/api/auth/login", json={"username": "x", "password": "nope"}).status_code == 401
    login(client, "farmer")
    assert client.get("/api/auth/me").get_json()["role"] == "farmer"
    assert client.get("/api/scans").status_code == 200
    assert client.get("/api/review/queue").status_code == 403
    assert client.get("/api/export/training-set").status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").get_json() is None


def test_confirm_and_correct(client, storage, expert):
    a, b = make_scan(storage), make_scan(storage, "leaf_curl")
    assert [s["id"] for s in client.get("/api/review/queue").get_json()] == [b.id, a.id]
    assert client.post(f"/api/review/{a.id}", json={"label": "anthracnose"}).get_json()["review_status"] == "confirmed"
    res = client.post(f"/api/review/{b.id}", json={"label": "healthy"}).get_json()
    assert res["review_status"] == "corrected" and res["confirmed_label"] == "healthy"
    assert client.post(f"/api/review/{b.id}", json={"label": "early_blight"}).status_code == 400
    assert client.get("/api/review/queue").get_json() == []
    row = ConfirmedLabel.query.filter_by(scan_id=b.id).one()
    assert (row.label, row.model_label, row.reviewer) == ("healthy", "leaf_curl", "expert")


def test_export_is_folder_per_class_and_skips_simulated(client, storage, expert):
    real, sim = make_scan(storage), make_scan(storage, simulated=True)
    for s in (real, sim):
        client.post(f"/api/review/{s.id}", json={"label": "anthracnose"})
    res = client.get("/api/export/training-set?crop=chilli")
    assert res.status_code == 200 and res.mimetype == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(res.data)).namelist()
    assert f"chilli/anthracnose/scan_{real.id}.jpg" in names and "manifest.csv" in names
    assert not any(f"scan_{sim.id}." in n for n in names)


def test_labels_and_metrics(app, client, tmp_path):
    labels = client.get("/api/review/labels?crop=tomato").get_json()
    assert {"label": "healthy", "name": {"en": "Healthy", "ms": "Sihat"}} in labels
    app.config["MODEL_DIR"] = tmp_path
    assert client.get("/api/model/metrics").get_json() == {"runs": []}
    (tmp_path / "metrics.json").write_text(json.dumps({"runs": [{"crop": "chilli", "version": "v1", "val_accuracy": 0.8}]}))
    assert client.get("/api/model/metrics").get_json()["runs"][0]["version"] == "v1"
