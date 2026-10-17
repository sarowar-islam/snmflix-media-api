# =============================================================================
# SNMflix Media Extraction API - Production Dockerfile
# =============================================================================
FROM python:3.12-slim AS runtime

# Prevent Python from writing .pyc files and buffer standard out/err
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# Install runtime utilities (curl for container health checks)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 snmflix \
    && useradd -u 10001 -g snmflix -s /bin/bash -m snmflix

# Set container working directory
WORKDIR /app

# Copy requirements first to take advantage of Docker layer caching
COPY requirements.txt .

# Install production Python dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application source code
COPY app/ ./app
COPY pytest.ini .

# Set proper ownership for non-root execution
RUN chown -R snmflix:snmflix /app

# Switch to unprivileged user
USER snmflix

# Expose port (Render injects $PORT at runtime)
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

# Start Uvicorn dynamically binding to Render's $PORT or 8000 default
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
