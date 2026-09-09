# Lenny Growth Assistant — backend image (FastAPI)

FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg/build tools kept minimal; add here if a later
# step needs e.g. build-essential for a native RAG dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
# Installing dev deps (pytest) in the main image is a deliberate simplification
# for this take-home assignment — keeps evaluator setup to one Dockerfile/one
# image instead of a separate test stage, so `docker compose exec backend
# pytest` works immediately after a fresh clone with no extra install step.
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
