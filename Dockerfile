# ── Build ──────────────────────────────────────────────────────────────────
# Stage 1: Build the wheel in an isolated builder image.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build toolchain (required by chromadb, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY farm_agent/ farm_agent/
COPY README.md .
COPY LICENSE .

RUN pip install --no-cache-dir build && \
    python -m build --wheel

# ── Runtime ────────────────────────────────────────────────────────────────
# Stage 2: Lean production image with Semgrep and Docker SDK.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

LABEL maintainer="Farm-Agent Team"
LABEL description="Farm-Agent v4.0.0 — Autonomous Bounty-Hunting Security Researcher"
LABEL version="4.0.0"

# ── System dependencies ────────────────────────────────────────────────────
# git   — required by GitPython for shallow clones (Bloodhound pipeline)
# ca-certificates — TLS root certs for GitHub API & OpenRouter calls
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Foundry
RUN curl -L https://foundry.paradigm.xyz | bash && \
    /root/.foundry/bin/foundryup
ENV PATH="/root/.foundry/bin:${PATH}"

# ── Install Go compiler ────────────────────────────────────────────────────
# Required for sandbox test execution and Semgrep Go ruleset analysis.
ARG GO_VERSION=1.21.6
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz && \
    /usr/local/go/bin/go version
ENV PATH="/usr/local/go/bin:${PATH}"

# ── Install Semgrep (parallel radar for Bloodhound) ────────────────────────
# Heavy dep (~200MB) but provides access to community security rulesets.
# Isolate in venv to prevent dependency conflicts (e.g. opentelemetry).
RUN python3 -m venv /opt/semgrep && \
    /opt/semgrep/bin/pip install --no-cache-dir semgrep && \
    ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep

# ── Install Python wheel from builder ──────────────────────────────────────
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# ── Application directories ────────────────────────────────────────────────
# /app/data   — SQLite memory.db + ChromaDB vector store (volume-mounted)
# /app/logs   — Daily rolling log files (volume-mounted)
WORKDIR /app
RUN mkdir -p /app/data /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Use python -m to avoid any shell script CRLF issues on Windows-cloned repos
CMD ["python", "-m", "farm_agent.cli.main", "superhuman"]