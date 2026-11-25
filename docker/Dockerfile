# Standalone SE image (API + CLI). Host compose prefers the thermal python image
# so diagram CV deps are available; this Dockerfile is for SE-local smoke / CI.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

ENV SE_API_HOST=0.0.0.0
ENV SE_API_PORT=8100
ENV PYTHONPATH=/app/src

EXPOSE 8100
CMD ["uvicorn", "source_extract.api.app:app", "--host", "0.0.0.0", "--port", "8100"]
