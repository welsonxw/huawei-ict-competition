# Huawei Cloud setup – step-by-step checklist

A beginner-friendly order of work for putting TaniGuard on Huawei Cloud. Each step says **what to click / create**,
**what value to copy** and **where it goes** in `/opt/taniguard/.env`. Full detail for every step is in
[DEPLOY_HUAWEI_CLOUD.md](DEPLOY_HUAWEI_CLOUD.md) (core services, ModelArts, Pangu) and [IOTDA.md](IOTDA.md) (sensors
and valves). Console menus change over time – search the service name in the console if a menu has moved.

Keep a private note (not in Git) with the values from the "Copy" column as you go.

## Stage A – account (≈ 30 min, once)

| # | Do | Copy |
|---|---|---|
| A1 | Sign up at https://www.huaweicloud.com/intl/en-us/ and complete **real-name verification**. Redeem any competition / student vouchers under **Billing Center → Coupons**. | – |
| A2 | **IAM → User Groups**: create `taniguard-admins` with the admin policies your team needs. **IAM → Users**: one login per team member in that group. Turn on MFA for the account owner. | account name, IAM user names |
| A3 | Pick **one region** for everything (examples use **AP-Singapore `ap-southeast-3`**). Check IoTDA and ModelArts are offered there before you buy anything. | region ID |
| A4 | **Billing**: use **pay-per-use** while building; set a **budget alert** (Billing Center → Budgets). Stop/delete ECS, RDS, DCS and ModelArts services after the demo – they bill by the hour. | – |

## Stage B – network (≈ 15 min)

| # | Do | Copy |
|---|---|---|
| B1 | **VPC → Create VPC** `vpc-taniguard`, subnet `192.168.0.0/24`. | VPC / subnet name |
| B2 | **Security groups** `sg-taniguard-ecs` (in: TCP 80, 443 from anywhere; TCP 22 from your IP) and `sg-taniguard-data` (in: 3306 and 6379 from `sg-taniguard-ecs`). | – |

## Stage C – core services (≈ 1–2 h; needed for the web app)

| # | Service | Do | Copy → `.env` |
|---|---|---|---|
| C1 | **ECS** | Ubuntu 22.04, 2 vCPU / 4 GiB, 40 GiB disk, `vpc-taniguard`, `sg-taniguard-ecs`, with an **EIP**. SSH in, install Docker, `git clone` the repo to `/opt/taniguard`, `cp .env.example .env`. | EIP → the demo URL |
| C2 | **RDS for MySQL 8.0** | Same VPC, `sg-taniguard-data`. Create database `taniguard` (utf8mb4) and user `taniguard`. | private IP + password → `DATABASE_URL=mysql+pymysql://taniguard:<pw>@<ip>:3306/taniguard?charset=utf8mb4` |
| C3 | **DCS for Redis 6+** | Single-node or master/standby (not Cluster), same VPC, `sg-taniguard-data`, with password. | address + password → `REDIS_URL=redis://:<pw>@<addr>:6379/0` |
| C4 | **OBS** | Private bucket `taniguard-<team>` in the same region. IAM user `taniguard-app` with **programmatic access**, custom policy limited to that bucket. | `STORAGE_BACKEND=obs`, `OBS_ENDPOINT=https://obs.<region>.myhuaweicloud.com`, `OBS_BUCKET`, `OBS_ACCESS_KEY`, `OBS_SECRET_KEY` |
| C5 | App settings | Generate `SECRET_KEY` (`python3 -c "import secrets; print(secrets.token_hex(32))"`), set `DEMO_FARMER_PASSWORD` / `DEMO_EXPERT_PASSWORD`. | `.env` |
| C6 | Start | `docker compose -f docker-compose.cloud.yml up -d --build` (runs migrations, seeds, downloads the tomato model). | – |
| C7 | Check | `curl http://<EIP>/api/health` → all `ok`; open `http://<EIP>/`, log in, scan `ml/samples/TomatoEarlyBlight1.JPG`, confirm the photo appears in the OBS bucket. **Behind the scenes** tab shows RDS / DCS / OBS green. | – |
| C8 | Demo data | `docker compose -f docker-compose.cloud.yml exec backend flask seed-demo` (labelled "Simulated scenario"). | – |

## Stage D – HTTPS (≈ 30 min; required before IoTDA can push data)

| # | Do | Copy → `.env` |
|---|---|---|
| D1 | Point a domain at the EIP (Huawei **DNS** or your registrar). | domain |
| D2 | Either **ELB** with an HTTPS listener + certificate from **SSL Certificate Manager** → ECS port 80, or a certificate on the ECS nginx. | `SESSION_COOKIE_SECURE=true`, restart |

## Stage E – IoTDA sensors and valves (≈ 1 h; the precision-farming part)

| # | Do | Copy → `.env` / TaniGuard |
|---|---|---|
| E1 | **IoTDA** in the same region; open the instance's **Access Details**. | MQTTS host (port 8883), application API endpoint |
| E2 | **Products → Create Product** (MQTT, JSON). Import `deploy/iotda/taniguard_sensor_model.json` under Model Definition (services `Sensor`, `Irrigation`, `Fertigation`). | `IOTDA_PRODUCT_ID` |
| E3 | For each device: `flask add-device <plot_id> [--simulated]` (and `--kind valve` / `--kind doser` for actuators) → TaniGuard id + key. In IoTDA **Devices → Register Device** use node ID = TaniGuard id, secret = TaniGuard key. | device IDs |
| E4 | Random token → `IOTDA_PUSH_TOKEN`. **Rules → Data Forwarding**: device property reported → HTTP push to `https://<domain>/api/iot/iotda/push/<token>` (upload your CA certificate to IoTDA). | `IOTDA_PUSH_TOKEN` |
| E5 | For valve/doser commands: project ID (**My Credentials → API Credentials**) and a project-scoped IAM token (command in DEPLOY_HUAWEI_CLOUD.md §10 step 5; valid 24 h). | `IOTDA_API_ENDPOINT`, `IOTDA_PROJECT_ID`, `IOTDA_IAM_TOKEN` |
| E6 | Restart, then run `scripts/device_simulator.py --mqtt mqtts://<host>:8883 --iotda-product <id> --device <id> --key <key> ...` (IOTDA.md). Readings appear in **Farm monitor**; **Water now** reaches the device through IoTDA. | – |

## Stage F – optional AI services

| # | Service | Do | Copy → `.env` |
|---|---|---|---|
| F1 | **SWR + ModelArts** | Build `ml/modelarts/Dockerfile`, push to SWR, upload weights to `obs://taniguard-<team>/model/`, create model (custom image, port 8080, `/health`), deploy a **Real-Time Service**. | `PREDICTOR=remote`, `MODELARTS_ENDPOINT`, `MODELARTS_TOKEN` (24 h) |
| F2 | **Pangu / other LLM** | An endpoint with the OpenAI-style chat-completions API. | `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL` |

## Before judging

- [ ] `/api/health` all `ok`; **Behind the scenes** shows every service you set up as green.
- [ ] Demo accounts work; `seed-demo` loaded; "Simulated scenario" / "Simulated device" labels visible.
- [ ] IAM tokens (ModelArts, IoTDA commands) refreshed within the last 24 h.
- [ ] Screenshots of each Huawei console page (ECS, RDS, DCS, OBS bucket, IoTDA devices/rules, ModelArts service) saved for the slides.
- [ ] After the event: stop or release pay-per-use resources.
