# ─────────────────────────────────────────────────────────
# Orion API — Multi-stage Dockerfile
# ─────────────────────────────────────────────────────────

# Build stage
FROM ghcr.io/astral-sh/uv:python3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen lockfile)
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Copy venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Non-root user
RUN useradd --create-home orion
USER orion

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "orion.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
