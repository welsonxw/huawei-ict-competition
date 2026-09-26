# Assumptions

Decisions made where the build prompt left room for interpretation.

1. **Product name.** The prototype is called "TaniGuard" ("tani" = farming in Malay). Rename freely.
2. **Migrations.** Alembic is used through Flask-Migrate (`flask db upgrade`), which is a thin wrapper over Alembic.
3. **Local development without Docker.** If `DATABASE_URL` is unset the backend falls back to SQLite in `data/dev.db`; tests use in-memory SQLite and `fakeredis`. Production and Docker Compose use MySQL 8 and Redis 7.
4. **Frontend serving.** In Docker Compose the React build is served by nginx on port 8080, which proxies `/api` to the backend.
5. **Network exposure.** Compose binds MySQL, Redis and the backend to `127.0.0.1` only; the public entry point is the frontend (nginx, :8080). CORS is off unless `CORS_ORIGINS` is set.

## Phase 2 – Scan and action plan

- **Tomato model**: the AgriTech ResNet9 (38 PlantVillage classes) is used as-is; only the 10 tomato outputs are kept and renormalised. The weights (~26 MB) are not committed; `scripts/download_model.py` fetches them into `ml/weights/` (the backend container runs it on start). The architecture uses `MaxPool2d(4)`, as in the AgriTech notebook – `MaxPool2d(2)` does not match the weights.
- **Chilli model**: no chilli weights exist yet. Until `ml/weights/chilli_resnet9.pth` is trained with `python -m ml.train`, chilli scans return a deterministic **stub** prediction, flagged `is_stub=true` and shown in the UI with a "STUB PREDICTION" banner.
- **Stub confidence** is deterministic per image and is often below the 0.60 threshold, so stub scans usually land in the review queue. This is intentional.
- **Action-plan length**: disease plans have 3–5 steps. Healthy leaves (2 steps: keep monitoring, rescan) and low-confidence scans (2 steps: retake, wait for expert) are deliberately shorter, because giving treatment steps there would be misleading.
- **Weather window**: Open-Meteo hourly series start at local midnight; the action plan uses the 48 hours from the current Malaysia-time hour. "Tomorrow" means the next calendar day in Asia/Kuala_Lumpur.
- **Grad-CAM severity** = share of the leaf image whose normalised activation is ≥ `scan.severity_threshold` (0.5). It is a rough indicator, not a lab-measured affected area.
- **Example plots** (Plot A/B/C near Kluang, Johor) are created by `flask seed-base` so the Scan tab works out of the box. They are ordinary (non-simulated) demo plots with no scans.
- **Sample images** in `ml/samples/` come from the AgriTech repository test set (PlantVillage images) and are used for tests and demos.
