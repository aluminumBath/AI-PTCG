# Backend image: rules engine + agents + RL inference + FastAPI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (psycopg2-binary ships wheels, but keep curl for healthchecks).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch from the official CPU index (keeps the image small),
# then the rest from PyPI.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Startup runs DB init + admin seed (see api/main.py:_startup).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
