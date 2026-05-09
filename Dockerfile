# =============================================================================
# Quant.OS API - Multi-stage Dockerfile
# FastAPI backend with uvicorn ASGI server
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder - Compile dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Build arguments
ARG APP_VERSION=0.1.0
ARG BUILD_DATE
ARG VCS_REF

# Metadata labels
LABEL maintainer="Quant.OS Team <dev@alpha-search.dev>" \
      org.opencontainers.image.title="Quant.OS API" \
      org.opencontainers.image.description="Quantitative finance research platform API" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/alpha-search/alpha-search"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        cargo \
        pkg-config \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir uvicorn[standard] gunicorn

# ---------------------------------------------------------------------------
# Stage 2: Production - Runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Security: Create non-root user
RUN groupadd --gid 1000 quantos && \
    useradd --uid 1000 --gid quantos --shell /bin/false --create-home quantos

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=quantos:quantos alpha_search/ ./alpha_search/

# Create cache directory with correct permissions
RUN mkdir -p /app/cache && chown -R quantos:quantos /app/cache

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    APP_ENV=production \
    CACHE_DIR=/app/cache \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Switch to non-root user
USER quantos

# Run with gunicorn + uvicorn workers for production
# Workers = (2 x $num_cores) + 1, capped at 4 for small VPS
CMD exec gunicorn alpha_search.api:app \
    --bind ${API_HOST}:${API_PORT} \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${WORKERS:-2} \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL,,} \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50

# ---------------------------------------------------------------------------
# Stage 3: Development - Local dev with hot reload
# ---------------------------------------------------------------------------
FROM production AS development

# Switch to root for dev
USER root

# Install dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        vim \
    && rm -rf /var/lib/apt/lists/*

# Dev environment
ENV APP_ENV=development \
    LOG_LEVEL=DEBUG \
    LOG_FORMAT=text \
    WORKERS=1

# Mount source code as volume for hot reload
VOLUME ["/app"]

USER quantos

# Run with single uvicorn worker and auto-reload
CMD exec uvicorn alpha_search.api:app \
    --host ${API_HOST} \
    --port ${API_PORT} \
    --reload \
    --log-level ${LOG_LEVEL,,} \
    --access-log \
    --use-colors