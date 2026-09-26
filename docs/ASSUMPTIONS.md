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

## Phase 3 – Smart fertiliser

- **All crop requirements are placeholders.** `config/crop_requirements.yaml` holds round numbers (kg/ha, oxide form) marked `placeholder: true` so the optimiser runs. The API returns `placeholder_requirements: true` and the UI shows a "do not use these amounts in the field yet" banner until the DOA Pakej Teknologi Cili / Tomato values are entered.
- **Prices are TODO (`null`).** While any chosen product has no price, the optimiser treats all products as equal cost (so it minimises total kg), cost is shown as "not configured", and `placeholder_prices: true`.
- **Soil level factors** (low ×1.25, medium ×1.0, high ×0.75) are placeholders pending DOA soil-test interpretation. Advanced mode accepts Low/Medium/High only; numeric soil tests need DOA thresholds (TODO).
- **Tomato pH range is TODO.** If a pH is entered for tomato, the app says the range is not configured. Chilli uses 5.5–6.5 from the brief. pH never changes the product choice.
- **Bag sizes** 1/5/25/50 kg are a configurable guess (`thresholds.yaml`, TODO verify).
- **"Why" text** comes from the data: soil levels the farmer marked Low, plus the nutrient this stage needs noticeably more of (>15% above the crop's average across stages) in the requirement table.
- **Nutrients with a zero requirement are unconstrained.** MgO is shown on labels but not optimised, because the brief's requirement table has only N, P₂O₅ and K₂O.
- **Editing products and requirements** is done in the DB tables, which are seeded from YAML and never overwritten. An edit UI protected by the expert role comes with login in Phase 6.
- **Previous fertiliser** is free text that is repeated back as a caution. It does not change the amounts (no DOA carry-over coefficients yet).
