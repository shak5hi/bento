# One image recipe for every Python service. Build context: backend/
#   docker build -f docker/python.Dockerfile --build-arg SERVICE=prober .
FROM python:3.12-slim

ARG SERVICE
ARG APT_PACKAGES=""
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/shared:/app/service \
    SERVICE_NAME=${SERVICE}

RUN if [ -n "$APT_PACKAGES" ]; then \
      apt-get update && apt-get install -y --no-install-recommends $APT_PACKAGES && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY shared/requirements.txt /tmp/shared.txt
COPY services/${SERVICE}/requirements.txt /tmp/service.txt
RUN pip install -r /tmp/shared.txt -r /tmp/service.txt

COPY shared /app/shared
COPY services/${SERVICE} /app/service

RUN useradd --create-home --uid 10001 bento
USER bento
WORKDIR /app/service
CMD ["python", "main.py"]
