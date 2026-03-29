# ── Build ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY farm_agent/ farm_agent/
COPY README.md .
COPY LICENSE .

RUN pip install --no-cache-dir build && \
    python -m build --wheel

# ── Runtime ───────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="DevTools Team"
LABEL description="Automation daemon for repository maintenance"

# Create non-root user
RUN useradd --create-home --shell /bin/bash farm_agent
WORKDIR /home/farm_agent

# Install the built wheel
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Create config and data directories
RUN mkdir -p /home/farm_agent/.farm_agent && \
    chown -R farm_agent:farm_agent /home/farm_agent

# Expose dashboard port
EXPOSE 8787

USER farm_agent

# Health check for dashboard mode
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8787/api/health')" || exit 1

# Default: show help
ENTRYPOINT ["farm_agent"]
CMD ["--help"]
