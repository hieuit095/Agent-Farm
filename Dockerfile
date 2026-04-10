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
# Stage 2: Lean production image with ast-grep and Docker SDK.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

LABEL maintainer="Farm-Agent Team"
LABEL description="Farm-Agent v3.0.0 — Autonomous Bounty-Hunting Security Researcher"
LABEL version="3.0.0"

# Build arg for ast-grep version — easy to bump without changing the Dockerfile
ARG SG_VERSION=0.34.0

# ── System dependencies ────────────────────────────────────────────────────
# git   — required by GitPython for shallow clones (Bloodhound pipeline)
# curl  — required to download ast-grep binary
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

# ── Install ast-grep (sg) binary ───────────────────────────────────────────
# Direct binary download — avoids pulling Node.js (~200MB savings).
# Detects the architecture and downloads the matching release binary.
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64)  SG_ARCH="x86_64-unknown-linux-musl" ;; \
        aarch64) SG_ARCH="aarch64-unknown-linux-musl" ;; \
        *)       echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    curl -fsSL \
        "https://github.com/ast-grep/ast-grep/releases/download/${SG_VERSION}/ast-grep-linux-${SG_ARCH}.zip" \
        -o /tmp/sg.zip && \
    unzip -o /tmp/sg.zip -d /tmp/sg-extract && \
    mv /tmp/sg-extract/sg /usr/local/bin/sg && \
    chmod +x /usr/local/bin/sg && \
    rm -rf /tmp/sg.zip /tmp/sg-extract && \
    sg --version

# ── Install Semgrep (parallel radar for Bloodhound) ────────────────────────
# Heavy dep (~200MB) but provides access to community security rulesets.
# Gracefully skipped at runtime if binary missing (use_semgrep=False in config).
RUN pip install --no-cache-dir semgrep

# ── Install Python wheel from builder ──────────────────────────────────────
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# ── Application directories ────────────────────────────────────────────────
# /app/data   — SQLite memory.db + ChromaDB vector store (volume-mounted)
# /app/logs   — Daily rolling log files (volume-mounted)
WORKDIR /app
RUN mkdir -p /app/data /app/logs

# ── Entrypoint ─────────────────────────────────────────────────────────────
# Minimal: v3.0 Memory.init() creates all schema at runtime.
# No pre-seeding or DB migration needed in the entrypoint.
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["farm_agent", "superhuman"]