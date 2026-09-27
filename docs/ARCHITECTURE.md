# Architecture

TaniGuard has three layers: the **farm layer** (scan, action plan, fertiliser), the **community layer** (outbreak risk map) and the **national layer** (tonnes at risk per state). One Flask API and one React app serve all three.

```
             React + Vite + Tailwind (BM / EN)          Scan · Farm monitor · Outbreak map · National · Farm game · Behind the scenes
                           │  /api (same origin, session cookie)
             Flask API (Gunicorn)  ──────────────  APScheduler: weather + risk refresh every 3 h (Redis lock)
  ┌──────────────┬───────────────┬────────────────┬──────────────────┬──────────────────┐
  predictor      action_plan      fertiliser        risk_engine         national           review / assistant
  local PyTorch  profile +        LP (scipy         weather models ×    DOA production ×   expert labels, zip export,
  or ModelArts   48 h forecast    linprog)          nearby reports      incidence × damage LLM or templates
  └──────────────┴───────────────┴────────────────┴──────────────────┴──────────────────┘
        │                 │                                  │
  Storage (disk | OBS)   Cache (Redis | DCS)           Database (MySQL/SQLite | RDS)
```

| Concern | Local (Docker Compose) | Huawei Cloud | Switch |
|---|---|---|---|
| Web + API + jobs | containers on your machine | ECS | – |
| Database | MySQL 8 container | RDS for MySQL | `DATABASE_URL` |
| Cache | Redis 7 container | DCS for Redis | `REDIS_URL` |
| Photos, heatmaps | disk volume | OBS (S3-compatible API) | `STORAGE_BACKEND=obs` |
| Disease model | PyTorch in the backend | ModelArts real-time service (`ml/serve.py` image) | `PREDICTOR=remote` |
| Assistant | rule-based templates | Pangu or any OpenAI-compatible LLM | `LLM_*` |
| Weather | Open-Meteo | Open-Meteo | – |
| Field sensors | "Simulated device" (in-app job or `scripts/device_simulator.py`) | Huawei IoTDA (MQTT) → HTTP forwarding to `/api/iot/iotda/push/<token>` (see IOTDA.md); local Mosquitto + `flask mqtt-bridge` | `ENABLE_DEVICE_SIM`, `IOTDA_PUSH_TOKEN`, `MQTT_BROKER_URL` |

## Main data flow

1. A farmer uploads a leaf photo with crop and plot. The photo goes to storage (disk or OBS).
2. `predict(image, crop)` returns label, confidence, top 3, a Grad-CAM heatmap and severity. Without weights it returns a flagged stub.
3. The scan is saved with its grid cell and state. Low-confidence or stub scans go to the expert review queue.
4. The action plan combines the disease profile's advice type with the 48-hour Open-Meteo forecast (cached in Redis).
5. The risk engine scores each grid cell: weather model score × (1 + distance- and age-weighted nearby reports). Results are cached.
6. The national layer turns state-level incidence and severity into tonnes at risk using DOA 2023 production.
7. Experts confirm or correct labels. Confirmed labels override the model in steps 5–6 and are exported as a folder-per-class zip to retrain the model; `ml/train.py` records accuracy for the Model v1 → v2 panel.

## Farm monitor (Phase 9)

```
Simulated device (scheduler job, 15 min)   ─┐
scripts/device_simulator.py / ESP32 (HTTP) ─┼─> POST /api/iot/readings (X-Device-Id / X-Device-Key)
                                            │      validate ranges + timestamp → sensor_readings (MySQL/RDS)
Huawei IoTDA / local MQTT bridge (Phase 10)  ─┘
GET /api/plots/<id>/monitor → latest values, status vs crop target band, alerts, history → Farm monitor tab
```

- Each `Device` belongs to a plot and authenticates with a random key stored only as a SHA-256 hash; the key is shown once.
- Readings: soil moisture, soil and air temperature, humidity, leaf wetness, EC (nutrient proxy), light, battery.
- Alerts: device offline, value outside the crop target band, leaves wet ≥ 6 h in a row, low battery.
- Simulated devices run a simple soil-water bucket model driven by the Open-Meteo forecast for the plot (synthetic day/night pattern when offline). Their readings are flagged `is_simulated` and the UI shows **"Simulated device"**.
- Target bands and alert limits live in `config/iot.yaml` and are engineering placeholders (`docs/TODO_SOURCES.md`).

## Code map

| Path | What |
|---|---|
| `backend/app/services/predictor.py` | `LocalTorchPredictor`, `RemoteEndpointPredictor` |
| `backend/app/services/storage.py` | `LocalStorage`, `OBSStorage` |
| `backend/app/services/weather.py`, `weather_models.py` | Open-Meteo client, disease weather models |
| `backend/app/services/risk_engine.py` | grid risk + outbreak map |
| `backend/app/services/national.py` | state-level tonnes at risk |
| `backend/app/services/fertiliser.py` | linear-programming fertiliser planner |
| `backend/app/services/review.py`, `assistant.py`, `auth.py` | expert loop, assistant, login |
| `backend/app/services/iot.py`, `device_sim.py` | devices, reading ingest, monitor status, device simulator |
| `ml/` | ResNet9, Grad-CAM, training, ModelArts server |
| `config/` | every tunable number, with `TODO: verify source` where a source is still missing |

## Data provenance

- Production: DOA vegetable statistics 2023 (see `config/production.yaml`).
- Anything without a source is marked `TODO: verify source` (see `docs/TODO_SOURCES.md`).
- All demo data is flagged `is_simulated` and labelled **"Simulated scenario"** in the UI; it is never mixed into live results or exported for training.
- Readings from simulated sensors are flagged `is_simulated` and labelled **"Simulated device"**.
