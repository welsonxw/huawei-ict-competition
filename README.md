# TaniGuard – Crop-Health Early Warning (Huawei ICT Competition)

AI crop-health app for chilli and tomato growers that turns farmers' leaf scans into an early warning for Malaysia's food supply. Built for the Huawei ICT Competition – Innovation Track, powered by Huawei Cloud.

- **Farm layer** – scan a leaf → diagnosis, confidence, top 3, Grad-CAM heatmap, a 3–5 step BM/EN action plan that uses the 48-hour weather forecast, and a fertiliser planner (≤ 2 products, pH/liming advice).
- **Community layer** – outbreak risk map for today, +3 and +5 days from weather disease models plus nearby reports.
- **National layer** – tonnes of chilli and tomato at risk per state in the next 14 days, from DOA 2023 production data.
- **Learning loop** – experts confirm or correct low-confidence scans; confirmed scans export as a training set for the next model version.

## Huawei Cloud

| Service | Used for |
|---|---|
| ECS | Web app, Flask API, scheduled weather/risk refresh |
| RDS for MySQL | Scans, plots, confirmed labels, users |
| DCS for Redis | Weather, risk map and dashboard cache; job lock |
| OBS | Leaf photos and heatmaps (S3-compatible API) |
| ModelArts (optional) | Remote disease-model inference (`ml/serve.py` custom image) |
| Pangu / LLM (optional) | Farmer assistant |

Step-by-step deployment: [docs/DEPLOY_HUAWEI_CLOUD.md](docs/DEPLOY_HUAWEI_CLOUD.md). Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). How to use the app: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Screenshots

Add PNGs to `docs/screenshots/` with these names:

| Scan result + heatmap | Outbreak map (Simulated scenario) | National dashboard | Behind the scenes |
|---|---|---|---|
| ![Scan](docs/screenshots/scan.png) | ![Map](docs/screenshots/map.png) | ![National](docs/screenshots/national.png) | ![Architecture](docs/screenshots/architecture.png) |

## Run locally

Requires Docker with Compose v2.

```bash
cp .env.example .env          # set DEMO_FARMER_PASSWORD / DEMO_EXPERT_PASSWORD for demo logins
docker compose up -d --build
```

- App: http://localhost:8080 · API health: http://localhost:8080/api/health
- Accounts: `docker compose exec backend flask create-user NAME --role farmer|expert`, or the demo users `farmer` / `expert` from `.env`.
- Demo data (always labelled **"Simulated scenario"**): `docker compose exec backend flask seed-demo` (`--clear` to remove).

Without `DATABASE_URL` or Docker, the backend falls back to SQLite, so it also runs as a plain Flask app:

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
cd backend && PYTHONPATH=.. REDIS_URL=fakeredis:// ../.venv/bin/flask db upgrade && PYTHONPATH=.. REDIS_URL=fakeredis:// ../.venv/bin/flask run
```

### Models

- **Tomato** – pretrained ResNet9 from AgriTech, downloaded automatically on first start (or `python scripts/download_model.py`).
- **Chilli** – no public model; train one with `python -m ml.train --data <folder-per-class dataset> --version v1`. Until then chilli scans return a clearly flagged stub and go to expert review.
- **ModelArts** – set `PREDICTOR=remote`, `MODELARTS_ENDPOINT` and `MODELARTS_TOKEN` (see the deployment guide).

## Tests

```bash
cd backend && PYTHONPATH=.. python -m pytest -q && ruff check . ../ml ../scripts
cd frontend && npm ci && npm run lint && npm run build
```

## Data sources and open values

Production figures come from the DOA vegetable statistics 2023. Values without an official source yet (fertiliser prices, DOA nutrient rates, damage coefficients, some risk thresholds) are marked `TODO: verify source` in `config/` and listed in [docs/TODO_SOURCES.md](docs/TODO_SOURCES.md); the UI flags them as placeholders. Assumptions are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

## Licence and attribution

MIT – see [LICENSE](LICENSE). Reuses code and model weights from [AgriTech](https://github.com/omroy07/AgriTech) by Om Roy (MIT), PlantVillage sample images, and state boundaries from geoBoundaries / OpenStreetMap contributors (ODbL); see [NOTICE.md](NOTICE.md).
