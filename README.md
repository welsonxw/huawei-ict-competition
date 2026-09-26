# TaniGuard – Crop-Health Early Warning (Huawei ICT Competition)

AI crop-health app for chilli and tomato growers that turns farmers' leaf scans into an early warning for Malaysia's food supply. Built for the Huawei ICT Competition – Innovation Track, powered by Huawei Cloud.

Work in progress – see the phase PRs.

## Quick start (local)

```bash
cp .env.example .env          # optional – defaults work for local use
docker compose up -d --build  # MySQL, Redis, backend (port 5000), frontend (http://localhost:8080)
```

The backend runs migrations, seeds disease profiles and three example plots, and downloads the tomato model on first start.

### Model weights

| Crop | File in `ml/weights/` | How to get it |
|---|---|---|
| Tomato | `plant-disease-model.pth` | `python scripts/download_model.py` (AgriTech ResNet9, MIT) |
| Chilli | `chilli_resnet9.pth` | Train: `python -m ml.train --data data/chilli --out ml/weights/chilli_resnet9.pth` |

If a file is missing, scans still work but return a **stub** prediction that is clearly labelled in the API (`is_stub: true`) and the UI.
Set `PREDICTOR=remote` and `MODELARTS_ENDPOINT` to call a Huawei Cloud ModelArts endpoint instead of local PyTorch.

### Tests

```bash
cd backend && pytest        # backend
cd frontend && npm run lint && npm run build
```
