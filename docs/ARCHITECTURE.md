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

## My farm game mode (Phase 12)

`GET /api/plots/<id>/farm` (owner or expert) returns one plot shaped for the game: latest sensor values and status,
soil state (dry / moist / wet from the soil-moisture target band), rain forecast for the next 3 h, MYT clock,
sick plants from the last 14 days of scans (confirmed label wins), and the Phase 11 control state. The game draws up to
50 plants from this; each sick scan marks one plant. Growth stage is not tracked, so plants share one stage.
Water/Fertilise in the game call `POST /api/plots/<id>/commands` with `source: "game"` and follow the same
safety checks, confirmation and command log as the Farm monitor. Simulated sensors, actuators and scans keep their
"Simulated device" / "Simulated scenario" banners.

## Watering and fertiliser control (Phase 11)

```
Farm monitor "Water / Fertilise" ─┐                      ┌─ simulated valve/doser → updates the Simulated device sensor → done
schedule (every minute, MYT)  ─────┼─> safety checks ──> confirm ──> dispatch ─┼─ HTTP: device polls GET /api/iot/commands, replies POST .../response
(Phase 12 game, Phase 13 optimiser)┘   (blocked = logged)            │          ├─ MQTT: $oc/devices/{uid}/sys/commands/request_id={id} → response topic → mqtt-bridge
                                                                      │          └─ IoTDA: synchronous command API, device reply returned in the HTTP response
                                                                      └─ no ack within 120 s → expired
```

- Commands (`device_commands`) and schedules (`control_schedules`) are always logged, including blocked, failed, expired and cancelled ones.
- Safety checks (`backend/app/services/control.py`, limits in `config/control.yaml`): amount per command and per day (per m² × plot area),
  device online and not busy, skip watering when soil moisture is at the top of the crop band or ≥ 5 mm rain is forecast in 6 h,
  warn on evening watering; for fertiliser a minimum interval, EC ceiling and heavy-rain warning.
- Manual commands must be confirmed within 5 minutes and are re-checked at confirm time. Schedules are the confirmation for their own runs.
- Only the farmer who owns the plot can actuate; experts see the log read-only.
- Payloads use the IoTDA command format (`service_id`, `command_name`, `paras`), so the same firmware works on HTTP, MQTT and IoTDA.
- In-app simulated valves/dosers are labelled **"Simulated device"** and never claim real water or fertiliser was applied.

## Routine optimiser v1 (Phase 13)

`GET /api/plots/<id>/optimise` (owner or expert) ranks watering routines for the next 24 h:

- Candidates: each time in `config/optimizer.yaml` `water.times` × each amount in `water.l_per_m2` (capped by the Phase 11 per-command limit), plus "skip".
- Each candidate runs the Phase 9 soil-water bucket model (`device_sim.step`) hourly on the Open-Meteo forecast, starting from the latest soil-moisture reading (a typical-day pattern is used and flagged if the forecast is unavailable).
- `score = w.moisture × mean %-points outside the crop target band + w.leaf_wet × extra leaf-wet hours caused by watering + w.water × L/m²`. Extra leaf wetness lasts until the next drying hour (07:00–18:00, RH below the leaf-wetness threshold) – the reason evening watering loses to morning watering.
- Candidates the Phase 11 rules would block (rain ≥ `rain_skip_mm` in the window, over per-command/daily limit, projected soil already wet) are excluded; the farmer's enabled water schedules are scored alongside for comparison.
- Fertiliser: earliest morning slot in 72 h that respects `min_hours_between`, has < `rain_warn_mm` rain in the following window and EC below the block level. No amount is recommended (DOA rates are placeholders).
- The response carries reason codes (rendered BM/EN), `simulated_input` and `placeholder`. The Farm monitor panel can request the best watering now (command source `optimizer`, still confirm-first) or save it as a daily schedule; the My farm game shows a one-line advisor.
- It is an estimate from engineering defaults, not a yield prediction. Learning from logged outcomes is Phase 14.

## Learning optimiser v2 (Phase 14)

`GET /api/plots/<id>/learning` (owner or expert) and `GET|POST /api/plots/<id>/harvests` (POST: owning farmer only).

- Routine days: completed watering commands bucketed by local hour into morning / midday / evening / night (`config/optimizer.yaml` `learning.timings`); days with sensor readings but no watering count as "none".
- Outcomes: each scan in the last 90 days is attributed once, to the most common timing on that plot in the 7 days before it; the effective (expert-confirmed) label decides sick vs healthy. Pooled across all plots of the same crop.
- A timing qualifies with ≥ 14 logged days and ≥ 10 attributed scans; only when ≥ 2 timings qualify does the optimiser add `weight × (timing sick rate − pooled rate)` to each candidate's score (reason code `learned`). Otherwise it stays on the Phase 13 rules.
- Harvest records give kg/m² per plot over 120 days, grouped by the plot's dominant timing; shown for comparison only (needs ≥ 3 plots per timing), not fed into the score.
- Simulated commands, scans and harvests set `simulated` so the UI shows the Simulated device / Simulated scenario banner. The panel states it is association in logged data, not proof of cause.

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
