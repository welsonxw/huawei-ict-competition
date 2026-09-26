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
- **Prices are TODO (`null`).** While any active product has no price, the optimiser treats all products as equal cost (so it minimises total kg), cost is shown as "not configured", and `placeholder_prices: true`.
- **Soil level factors** (low ×1.25, medium ×1.0, high ×0.75) are placeholders pending DOA soil-test interpretation. Advanced mode accepts Low/Medium/High only; numeric soil tests need DOA thresholds (TODO).
- **Tomato pH range is TODO.** If a pH is entered for tomato, the app says the range is not configured. Chilli uses 5.5–6.5 from the brief. pH never changes the product choice.
- **Bag sizes** 1/5/25/50 kg are a configurable guess (`thresholds.yaml`, TODO verify).
- **"Why" text** comes from the data: soil levels the farmer marked Low, plus the nutrient this stage needs noticeably more of (>15% above the crop's average across stages) in the requirement table.
- **Nutrients with a zero requirement are unconstrained.** MgO is shown on labels but not optimised, because the brief's requirement table has only N, P₂O₅ and K₂O.
- **Editing products and requirements** is done in the DB tables, which are seeded from YAML and never overwritten. An edit UI protected by the expert role comes with login in Phase 6.
- **Previous fertiliser** is free text that is repeated back as a caution. It does not change the amounts (no DOA carry-over coefficients yet).

## Phase 4 – Risk engine and outbreak map

- **Risk formula:** `risk = S_weather × (1 + Σ w_dist × w_age)`, with both weights linear (1 at 0 km / 0 days, 0 at the disease's spread radius / decay period). Only confirmed reports, or unreviewed real-model reports with confidence ≥ `risk.report_min_confidence`, are counted. Pending, stub and low-confidence scans are ignored.
- **Bands are Medium > 1.0 and High ≥ 2.0.** Weather alone gives at most 1.0, so a cell only turns Medium or High once there are nearby reports. These cut-offs are engineering defaults and still need checking against field data.
- **Leaf wetness** is taken to mean RH ≥ 90%, because Open-Meteo has no leaf-wetness sensor data.
- **TOM-CAST** DSV table is in `config/tomcast_table.yaml`. It adds up DSV over 7 days and scales against a threshold of 15.
- **Hutton** needs a minimum temperature ≥ 10 °C and ≥ 6 h of RH ≥ 90% on 2 consecutive days. It scores 0.5 when only one of the two days qualifies. The rule comes from the UK and must be recalibrated for Malaysia.
- **Rule model:** the share of hours in the last 3 days that are inside the temperature range and meet the moisture trigger. The score reaches 1 when 75% of hours qualify.
- **Vector proxy (whitefly):** 50% share of dry days + 50% heat (mean daily max from 25 to 33 °C) over 7 days, halved if it rained on the target day. These thresholds are TODO and need DOA/MARDI entomology input.
- **Weather** is Open-Meteo hourly data for the past 7 days plus 7 forecast days per ~5 km cell. It is fetched in batches, cached in Redis for 3 h, and refreshed every 3 h by APScheduler (`ENABLE_SCHEDULER=true`) or on demand with `flask refresh-risk`. Risk layers are cached in Redis and invalidated whenever a new scan is saved.
- **Simulated scenario:** `scripts/seed_demo.py` (or `flask seed-demo [--clear]`) creates about 300 scans marked `is_simulated = true`, using fixed settings in `config/demo_scenario.yaml`. The demo layer uses fixed, made-up "rainy spell" weather, not Open-Meteo. Simulated scans never feed into the live layer, and the map shows "Simulated scenario – not real data" whenever the demo layer is on.

## Phase 5 – National dashboard

- **Production (`P_region`)** is DOA's 2023 annual production by state (`config/production.yaml`, taken from Jadual 2-1 of *Statistik Tanaman Sayur-sayuran dan Tanaman Kontan 2023*). "Cili" here means ordinary chilli; DOA reports cili padi separately. The expected harvest in the window is annual production × 14 / 365, which assumes harvest is spread evenly through the year.
- **Incidence** is the share of usable scans for that crop in the state over the last 14 days that show the disease. Pending-review and stub scans are left out. **Severity** is the mean Grad-CAM leaf-area share of the diseased scans.
- **Damage function `f(severity)`** is linear with slope 1 and marked as a placeholder (`config/damage_functions.yaml`) until DOA/MARDI yield-loss coefficients are available.
- **Supply level:** Watch at ≥ 2% and High at ≥ 5% of expected harvest at risk. These are placeholders. A state with fewer than 20 usable scans shows "Not enough scans" instead of a level.
- **State boundaries** come from geoBoundaries gbOpen MYS ADM1 (© OpenStreetMap contributors, ODbL 1.0), simplified. Scans are assigned to a state by point-in-polygon; if a point is outside every state, the nearest state centroid is used.
- **Demo healthy background:** the simulated scenario also adds healthy scans in each state, so incidence is a share rather than 100%. These are simulated too.
- The UI shows the note: "Scan data comes from app users, not a random survey, so early incidence may be over-estimated."

## Phase 6 – Review loop, assistant, login

- **Login** uses a signed session cookie (HttpOnly, SameSite=Lax), so photo URLs work in `<img>` tags. There are two roles. **Farmers** can use plots, scans, leaf photos, heatmaps, the fertiliser planner and the assistant. **Experts** can do all of that, and also use the review queue, confirm or correct labels, and export the training set. The outbreak map, national dashboard, disease list and model metrics stay public because they only show aggregated data. Report dots on the public map are rounded to 0.01° (about 1 km), so they don't reveal exact farm locations.
- Create accounts with `flask create-user NAME --role expert`. Alternatively, set `DEMO_FARMER_PASSWORD` / `DEMO_EXPERT_PASSWORD` and run `flask seed-base`. Passwords must be at least 8 characters and are hashed with Werkzeug.
- **Review:** if the expert picks the model's label, the scan is marked `confirmed`; if they pick a different label, it is marked `corrected`. Either way a row is written to `confirmed_labels`. The confirmed label then replaces the model label in the risk map and national dashboard.
- **Export:** `GET /api/export/training-set?crop=` (or `scripts/export_training_set.py`) produces `<crop>/<label>/scan_<id>.jpg` plus `manifest.csv`. Simulated scans are never exported.
- **Model v1 → v2 panel:** reads `ml/weights/metrics.json`, which `ml/train.py` writes. The bundled tomato model was not trained here, so the panel stays empty until a training run is recorded.
- **Assistant:** works with any OpenAI-compatible chat-completions endpoint (`LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`); Huawei Cloud Pangu is the intended provider. If no key is set, or the call fails, it answers from rule-based templates in BM or English. Those templates are built from the same diagnosis and action plan, so they never add doses.
