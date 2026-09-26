# Custom inference image for a Huawei Cloud ModelArts real-time service.
# Build from the repo root:  docker build -f ml/modelarts/Dockerfile -t taniguard-infer:v1 .
# ModelArts runs the container as UID 1000 / GID 100, downloads the OBS model package
# (plant-disease-model.pth and/or chilli_resnet9.pth) to /home/mind/model and calls port 8080.
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv:/srv/backend MODEL_DIR=/home/mind/model
WORKDIR /srv
COPY backend/requirements.txt backend/requirements-ml.txt /srv/backend/
RUN pip install -r backend/requirements.txt && pip install -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY backend/app /srv/backend/app
COPY ml /srv/ml
RUN mkdir -p /home/mind/model && chown -R 1000:100 /home/mind
USER 1000:100
EXPOSE 8080
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "--timeout", "120", "--graceful-timeout", "60", "ml.serve:app"]
