# syntax=docker/dockerfile:1

# ---- Stage 1: build the Angular frontend ----
FROM node:22-alpine AS frontend-build
WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npx ng build

# ---- Stage 2: Python runtime serving API, WebSocket and the built frontend ----
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DICE_DB_PATH=/data/dice.db

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# main.py looks for the frontend at ../../frontend/dist/frontend/browser relative to app/
COPY --from=frontend-build /src/frontend/dist/frontend/browser /app/frontend/dist/frontend/browser

RUN useradd --uid 1000 --no-create-home --home /app fiasco \
    && mkdir -p /data \
    && chown fiasco:fiasco /data
USER fiasco

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/rooms')" || exit 1

# Single worker on purpose: live rooms are tracked in memory (RoomManager).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
