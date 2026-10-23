# =============================================================================
# Transurban SEAL Golden Path — Hardened Multi-Stage Cloud Run v2 Container
# Reference: ENG-2075 / ENG-2081 (Streamlit + BigQuery Golden Path Template)
# =============================================================================

# Stage 1: Dependency Builder with uv
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definitions first for layer caching
COPY pyproject.toml ./

# Install production dependencies into /opt/venv
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -r pyproject.toml

# Stage 2: Hardened Non-Root Runtime Image
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    APP_NAME="ncx-portal-emissions" \
    APP_ENV="prod" \
    COST_CENTRE="cc-am-tunnel-ops" \
    GCP_PROJECT_ID="tu-data-edw-pr-1" \
    BQ_DATASET="a113_roadside"

# Create non-root user and group (ENG-2081 Security Requirement)
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /sbin/nologin --no-create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source, static assets, and A2A descriptor
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup .well-known/ ./.well-known/

# Switch to non-root user
USER 10001:10001

EXPOSE 8080

# Cloud Run v2 Startup & Liveness Probe against Streamlit internal health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/_stcore/health')" || exit 1

# Note: --server.enableCORS=false and --server.enableXsrfProtection=true are mandatory
# behind Cloud Run Direct IAP (ENG-2079 / ENG-2080)
ENTRYPOINT ["streamlit", "run", "src/app.py", \
            "--server.port=8080", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--server.enableCORS=false", \
            "--server.enableXsrfProtection=true", \
            "--browser.gatherUsageStats=false"]
