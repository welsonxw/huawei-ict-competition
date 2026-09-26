# Deploying TaniGuard on Huawei Cloud

This guide deploys the app on **ECS** with **RDS for MySQL**, **DCS for Redis** and **OBS**, and (optionally) the disease model on **ModelArts** and the assistant on **Pangu** or another LLM.
The same code runs locally with Docker Compose; in the cloud only environment variables change.

```
Browser ──HTTP(S)──> ECS (EIP / ELB)
                      ├─ nginx (frontend container) ──/api──> Flask + Gunicorn (backend container)
                      │                                          ├─> RDS for MySQL   (scans, plots, labels, users)
                      │                                          ├─> DCS for Redis   (weather, risk maps, dashboard cache, job lock)
                      │                                          ├─> OBS             (leaf photos, heatmaps)
                      │                                          ├─> ModelArts       (optional, PREDICTOR=remote)
                      │                                          ├─> Pangu / LLM     (optional, LLM_*)
                      │                                          └─> Open-Meteo      (weather, public internet)
```

Console screens change over time; the steps below name the settings to look for rather than exact button positions.

## 0. Before you start

- A Huawei Cloud account with real-name verification, and an IAM user for the team (do not use the account root user day to day).
- Pick **one region** and create everything in it. `ap-southeast-3` (AP-Singapore) is used in the examples; `my-kualalumpur-1` (AP-Kuala Lumpur-OP6) also exists but check which services it offers before choosing it.
- Create one **VPC** with one subnet (for example `192.168.0.0/24`). ECS, RDS and DCS must be in the same VPC – DCS instances cannot be reached over a public IP.

## 1. Security groups

| Group | Inbound rule | Why |
|---|---|---|
| `sg-taniguard-ecs` | TCP 80 (and 443 if you add HTTPS) from `0.0.0.0/0` | Web app |
| | TCP 22 from **your own IP only** | SSH |
| `sg-taniguard-data` | TCP 3306 from `sg-taniguard-ecs` | RDS for MySQL |
| | TCP 6379 from `sg-taniguard-ecs` | DCS for Redis |

Leave outbound open (the backend calls Open-Meteo, GitHub for the model download, and OBS/ModelArts endpoints).

## 2. ECS (web app, API, scheduled jobs)

1. **Elastic Cloud Server → Buy ECS**: same region/VPC/subnet, `sg-taniguard-ecs`.
   - Flavor: 2 vCPUs / 4 GiB is enough for the demo (PyTorch CPU inference runs in the backend). Use 4 GiB+ if you keep `PREDICTOR=local`.
   - Image: Ubuntu 22.04 server, 40 GiB system disk.
   - Assign an **EIP** (or put an ELB in front) so judges can reach it; the EIP also gives the ECS internet access.
2. SSH in and install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && newgrp docker
   ```
3. Get the code:
   ```bash
   sudo mkdir -p /opt/taniguard && sudo chown $USER /opt/taniguard
   git clone https://github.com/welsonxw/huawei-ict-competition.git /opt/taniguard
   cd /opt/taniguard && cp .env.example .env
   ```

## 3. RDS for MySQL (main database)

1. **Relational Database Service → Buy DB Instance**: engine **MySQL 8.0**, same VPC/subnet, security group `sg-taniguard-data`. Single instance is fine for the demo; primary/standby for production.
2. Set the administrator password, then under **Databases** create `taniguard` with character set **utf8mb4**, and under **Accounts** create a user `taniguard` with read/write on that database only.
3. Copy the instance's **private (floating) IP**. In `/opt/taniguard/.env`:
   ```bash
   DATABASE_URL=mysql+pymysql://taniguard:<PASSWORD>@<RDS_PRIVATE_IP>:3306/taniguard?charset=utf8mb4
   ```
   URL-encode special characters in the password (for example `@` → `%40`).
4. Optional check from the ECS: `docker run --rm -it mysql:8.0 mysql -h <RDS_PRIVATE_IP> -u taniguard -p taniguard -e "SELECT 1"`.

## 4. DCS for Redis (cache)

1. **Distributed Cache Service → Buy DCS Instance**: Redis 6.0 or later, **single-node** or **master/standby** (the app uses a plain Redis client, not Redis Cluster mode), same VPC, `sg-taniguard-data`, set a password.
2. Copy the instance's connection address. In `.env`:
   ```bash
   REDIS_URL=redis://:<PASSWORD>@<DCS_ADDRESS>:6379/0
   ```
   For a password-free instance: `redis://<DCS_ADDRESS>:6379/0`.
3. Optional check: `docker run --rm -it redis:7-alpine redis-cli -h <DCS_ADDRESS> -p 6379 -a <PASSWORD> ping` → `PONG`.

Redis also holds the lock that stops the 3-hourly weather/risk refresh running twice when Gunicorn has several workers.

## 5. OBS (photos, heatmaps, model files)

1. **Object Storage Service → Create Bucket** in the same region: storage class Standard, **Private** policy, name e.g. `taniguard-<team>`.
2. **IAM → Users → Create user** `taniguard-app` with **programmatic access** and download its **access key (AK/SK)**. Give it an OBS policy limited to this bucket (custom policy allowing `obs:object:GetObject`, `obs:object:PutObject`, `obs:object:DeleteObject`, `obs:bucket:ListBucket` on `obs:*:*:bucket:taniguard-<team>` and `obs:*:*:object:taniguard-<team>/*`).
3. In `.env`:
   ```bash
   STORAGE_BACKEND=obs
   OBS_ENDPOINT=https://obs.ap-southeast-3.myhuaweicloud.com
   OBS_BUCKET=taniguard-<team>
   OBS_ACCESS_KEY=<AK>
   OBS_SECRET_KEY=<SK>
   ```
   The backend talks to OBS through its S3-compatible API with boto3, using virtual-hosted-style URLs (`<bucket>.obs.<region>.myhuaweicloud.com`) as OBS requires. The region is taken from the endpoint; set `OBS_REGION` only if you use a custom domain.

Photos are served to logged-in users through the API (`/api/scans/<id>/image`), so the bucket never needs public read access.

## 6. Remaining settings

In `.env`:

```bash
SECRET_KEY=<output of: python3 -c "import secrets; print(secrets.token_hex(32))">
ENABLE_SCHEDULER=true
CORS_ORIGINS=                 # empty: the frontend and API share one origin through nginx
SESSION_COOKIE_SECURE=false   # true once the site is served over HTTPS
DEMO_FARMER_PASSWORD=<8+ chars>   # optional demo logins "farmer" / "expert"
DEMO_EXPERT_PASSWORD=<8+ chars>
```

Never commit `.env`. It is in `.gitignore`.

## 7. Start the app

### Option A – Docker Compose (recommended)

```bash
cd /opt/taniguard
docker compose -f docker-compose.cloud.yml up -d --build
docker compose -f docker-compose.cloud.yml logs -f backend   # wait for "Listening at: http://0.0.0.0:5000"
```

On every start the backend container runs, in order:

1. `flask db upgrade` – Alembic migrations create/upgrade all tables in RDS;
2. `flask seed-base` – disease profiles, fertiliser tables, example plots, and demo users if `DEMO_*_PASSWORD` is set;
3. `scripts/download_model.py` – fetches the tomato ResNet9 weights into `ml/weights/` (skipped if present);
4. Gunicorn with 2 workers.

`docker-compose.cloud.yml` has no MySQL or Redis containers and refuses to start if `DATABASE_URL` or `REDIS_URL` is missing.

Start at boot with systemd:

```bash
sudo cp deploy/systemd/taniguard.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now taniguard
```

### Option B – systemd without Docker

```bash
sudo apt-get install -y python3.11 python3.11-venv nginx nodejs npm   # Node 20+ needed for the build
cd /opt/taniguard
python3.11 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/pip install -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv/bin/python scripts/download_model.py
(cd frontend && npm ci && npm run build)
sudo useradd --system taniguard && sudo mkdir -p data && sudo chown -R taniguard data ml/weights
sudo cp deploy/systemd/taniguard-api.service /etc/systemd/system/
sudo cp deploy/nginx/taniguard.conf /etc/nginx/sites-available/taniguard
sudo ln -sf /etc/nginx/sites-available/taniguard /etc/nginx/sites-enabled/taniguard
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload && sudo systemctl enable --now taniguard-api && sudo nginx -s reload
```

The unit runs `flask db upgrade` and `flask seed-base` before Gunicorn starts.

## 8. Check it works

```bash
curl http://<EIP>/api/health    # {"database":"ok","redis":"ok","status":"ok"}
curl http://<EIP>/api/system    # {"database":"mysql","cache":"redis","storage":"obs",...}
```

Open `http://<EIP>/`, log in, scan a tomato leaf from `ml/samples/`, and check the photo appears in the OBS bucket under `scans/`. The **Behind the scenes** tab turns each box green when the matching Huawei Cloud service is in use.

Accounts (if you did not set the demo passwords):

```bash
docker compose -f docker-compose.cloud.yml exec backend flask create-user expert1 --role expert
docker compose -f docker-compose.cloud.yml exec backend flask create-user farmer1
```

Demo data for judging (always labelled **"Simulated scenario"** in the UI, never mixed into live data):

```bash
docker compose -f docker-compose.cloud.yml exec backend flask seed-demo
docker compose -f docker-compose.cloud.yml exec backend flask seed-demo --clear   # remove it
```

## 9. HTTPS (recommended before sharing the link)

Either put a **Dedicated Load Balancer (ELB)** in front of the ECS with an HTTPS listener and a certificate from **SSL Certificate Manager** forwarding to port 80, or install a certificate on the ECS nginx. Then set `SESSION_COOKIE_SECURE=true` and restart.

## 10. Optional – disease model on ModelArts

The backend's `RemoteEndpointPredictor` sends `POST {"crop", "image": <base64 JPEG>}` with an `X-Auth-Token` header and expects `{"label", "confidence", "top3", "heatmap", "severity", "model_version"}`. `ml/serve.py` implements exactly that contract around the same PyTorch model, packaged as a ModelArts **custom image**.

1. **Model package in OBS**: upload the weights to a folder, e.g. `obs://taniguard-<team>/model/` containing `plant-disease-model.pth` and, once trained, `chilli_resnet9.pth`. ModelArts copies this folder to `/home/mind/model` in the container.
2. **Build and push the image to SWR** (SoftWare Repository for Container):
   ```bash
   docker build -f ml/modelarts/Dockerfile -t taniguard-infer:v1 .
   # test locally with the weights mounted where ModelArts puts them
   docker run --rm --user 1000:100 -p 8080:8080 -v $PWD/ml/weights:/home/mind/model taniguard-infer:v1
   curl localhost:8080/health
   # SWR console → Organization → "Generate login command", then:
   docker tag taniguard-infer:v1 swr.ap-southeast-3.myhuaweicloud.com/<org>/taniguard-infer:v1
   docker push swr.ap-southeast-3.myhuaweicloud.com/<org>/taniguard-infer:v1
   ```
   The image listens on port **8080**, runs as UID 1000 / GID 100, and exposes `GET /health`, as ModelArts custom images require.
3. **ModelArts → Model Management → Create model**: meta model from OBS (`obs://taniguard-<team>/model/`), AI engine **Custom**, container image = the SWR image, protocol HTTP, port 8080, health check path `/health`. Inference API: `POST /`, `application/json`.
4. **Deploy → Real-Time Service**: CPU flavor (2 vCPUs / 8 GiB is enough). When the service is **Running**, copy its **API URL** from the service's Usage Guides tab.
5. Get a **project-scoped IAM token** (ModelArts real-time services reject domain-scoped tokens):
   ```bash
   curl -si -X POST https://iam.ap-southeast-3.myhuaweicloud.com/v3/auth/tokens \
     -H 'Content-Type: application/json' -d '{"auth":{"identity":{"methods":["password"],"password":{"user":{
       "name":"<IAM_USER>","password":"<IAM_PASSWORD>","domain":{"name":"<ACCOUNT_NAME>"}}}},
       "scope":{"project":{"name":"ap-southeast-3"}}}}' | grep -i '^x-subject-token'
   ```
6. In `.env`, then restart:
   ```bash
   PREDICTOR=remote
   MODELARTS_ENDPOINT=<API URL>
   MODELARTS_TOKEN=<X-Subject-Token value>
   ```

IAM tokens are valid for 24 hours, so `MODELARTS_TOKEN` must be refreshed daily (re-run step 5 and restart the backend). Automatic refresh or AK/SK request signing is not implemented yet. If the endpoint has no model file loaded it returns HTTP 503 instead of a fake prediction.

## 11. Optional – assistant on Pangu or another LLM

The assistant calls any **OpenAI-compatible chat-completions** endpoint:

```bash
LLM_ENDPOINT=https://<host>/v1/chat/completions
LLM_API_KEY=<key>
LLM_MODEL=<model name>
```

Use a Pangu (or other ModelArts-hosted) model that offers this API format. If the endpoint uses a different format, add a provider class next to `OpenAICompatibleProvider` in `backend/app/services/assistant.py`. With no key, or if the call fails, the assistant answers from built-in BM/EN templates.

## 12. Updating and backups

```bash
cd /opt/taniguard && git pull && docker compose -f docker-compose.cloud.yml up -d --build   # migrations run on start
```

RDS takes automated backups (check the retention period under the instance's **Backups & Restorations**). Leaf photos live in OBS; turn on bucket versioning if you need to recover deleted files.

## Environment variable reference

| Variable | Local default | Huawei Cloud value |
|---|---|---|
| `DATABASE_URL` | built from `MYSQL_*` (compose) or SQLite | RDS for MySQL private IP |
| `REDIS_URL` | `redis://redis:6379/0` | DCS for Redis address + password |
| `STORAGE_BACKEND` | `local` | `obs` |
| `OBS_ENDPOINT` / `OBS_BUCKET` / `OBS_ACCESS_KEY` / `OBS_SECRET_KEY` / `OBS_REGION` | – | bucket + IAM AK/SK |
| `PREDICTOR` | `local` | `local` or `remote` |
| `MODELARTS_ENDPOINT` / `MODELARTS_TOKEN` | – | real-time service URL + IAM token |
| `LLM_ENDPOINT` / `LLM_API_KEY` / `LLM_MODEL` | – | Pangu or other LLM |
| `SECRET_KEY` | random, saved in `data/.secret_key` | long random string |
| `SESSION_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `ENABLE_SCHEDULER` | `true` in compose | `true` |
| `CORS_ORIGINS` | empty | empty (same origin) |
| `DEMO_FARMER_PASSWORD` / `DEMO_EXPERT_PASSWORD` | – | optional |

## Official references

- OBS endpoints and S3 compatibility: https://support.huaweicloud.com/intl/en-us/api-obs/obs_04_0001.html
- OBS custom policy actions and resource format: https://support.huaweicloud.com/intl/en-us/api-obs/obs_04_0112.html , https://support.huaweicloud.com/intl/en-us/usermanual-iam/iam_01_0019.html
- DCS access from ECS in the same VPC: https://support.huaweicloud.com/intl/en-us/dcs/index.html
- ModelArts custom images (port 8080, `/health`, UID 1000): https://support.huaweicloud.com/intl/en-us/inference-modelarts/index.html
- ModelArts token authentication (project-scoped, 24 h): https://support.huaweicloud.com/intl/en-us/usermanual-standard-modelarts/inference-modelarts-0023.html , https://support.huaweicloud.com/intl/en-us/api-modelarts/modelarts_03_0004.html
