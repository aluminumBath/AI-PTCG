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
# then the rest from PyPI. The final import check fails the build loudly if any
# core dependency (e.g. uvicorn) is missing, so a broken image is never produced.
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt \
    && python -c "import uvicorn, fastapi, sqlalchemy, psycopg2, torch; print('deps OK')"

COPY . .

EXPOSE 8000

# Launch via the Python module rather than the bare `uvicorn` console script:
# this only requires the package to be importable, so it can't fail with
# "uvicorn: executable file not found in $PATH".
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
