# 🛠️ Farm-Agent

**Autonomous Open Source Contributor**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous AI agent designed to discover open-source GitHub repositories, identify vulnerabilities and code quality issues, generate precise patches, and submit them as pull requests. It leverages multiple LLM models and dynamic code analysis to continuously monitor and improve targeted projects.

## Key Features

- **Bloodhound Red Team & Semgrep Radar:** A dedicated pipeline utilizing Semgrep rulesets (e.g. CWE Top 25, Security Audit) and OpenRouter fallback models for intensive vulnerability discovery.
- **Polyglot Sandbox Validation:** Uses strictly isolated Docker containers without network access to execute and validate generated code patches across multiple languages before generating Pull Requests.
- **Anti-Farming Filter:** A stringent, zero-tolerance gateway that outright rejects trivial findings (e.g., typos, formatting tweaks) and blocks all documentation-only patches to preserve signal-to-noise ratio.
- **Circular Target Loop:** A continuous, round-robin processing system targeting prioritized repositories based on recent scan timestamps, enabling crash-safe rotation and persistent improvement loops.
- **Super Human Mode:** A relentless "Terminator execution loop" that maximizes PR throughput via an autonomous daemon operating up to API limits without simulated delays.
- **PR Patrol:** Autonomously monitors open PRs to engage with maintainer feedback, generating follow-up fixes and actively driving contributions to the finish line.

## System Architecture (High-Level)

The agent operates via a Click-based CLI (`farm_agent`), orchestrating processes through `ContribPipeline` and `SuperHumanLoop`. It interacts with the GitHub REST API and leverages Minimax ABAB models as the primary AI engine.

State, run history, and quotas are managed persistently via SQLite configured with WAL mode (`aiosqlite`). When resolving bugs, the engine employs a local ChromaDB instance for ephemeral RAG (Retrieval-Augmented Generation) context resolution. Validated code passes into an ephemeral, tightly-constrained Docker Sandbox. If the patch causes test or linter failures, the agent engages a cyclic self-correction process before requesting a final PR submission.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with repository scope
- **LLM API Key:** Minimax API key (default) or other configured providers

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configure the agent via `config.yaml` or provide the following required `.env` variables:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for primary LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID (if applicable).
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated list of secondary tokens for load-balanced GET requests.
- `OPENROUTER_API_KEY`: (Optional) OpenRouter API key for Red Team audits.

Alternatively, duplicate `config.example.yaml` as `config.yaml` and apply custom configurations.

## Usage

Farm-Agent provides an array of CLI tools mapped to different operational profiles:

**Run a single hunt pipeline (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Run continuous Circular Target Loop (from target JSON file):**
```bash
farm_agent hunt-circular
```

**Target a specific repository url directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve specific open issues in a repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and push fixes to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Scan a repository and output local findings (no PRs created):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**View overall system capabilities and run metrics:**
```bash
farm_agent system-status
```

## Contributing & License

We welcome contributions! Please follow standard open-source workflows to fork and submit PRs.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
