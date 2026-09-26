FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY backend/requirements.txt backend/requirements-ml.txt /srv/backend/
RUN pip install -r backend/requirements.txt && pip install -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY backend /srv/backend
COPY ml /srv/ml
COPY config /srv/config
COPY scripts /srv/scripts
WORKDIR /srv/backend
ENV FLASK_APP=wsgi.py
EXPOSE 5000
CMD ["sh", "-c", "flask db upgrade && gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 wsgi:app"]
