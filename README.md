# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify vulnerabilities or quality issues, generate precise code fixes via LLM, and submit pull requests. It operates behind a sophisticated human behavior simulation layer to ensure all contributions provide genuine value to maintainers and respect standard open-source workflows.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches across multiple languages before any Pull Request is created, enforcing a strict quality gate.
- **PR Patrol:** Autonomously monitors open PRs created by the agent, reads maintainer review comments, generates code fixes, answers questions, and automatically signs CLAs.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and strictly blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays and randomized PR quotas to mimic a real developer's workflow.
- **Bloodhound Red Team:** Conducts vulnerability discovery and code audits using tools like Semgrep and ast-grep.
- **Circular Target Loop:** A crash-safe, deterministic round-robin execution loop for processing targets asynchronously and continuously.
- **DEV-QA Bounty Loop:** An internal multi-cycle evaluation mechanism that critiques generated patches and self-corrects based on repo style guides before finalization.
- **Security Disclosure Gate:** Scans repository meta files for private disclosure phrases and automatically aborts the public pipeline to respect maintainer preferences.
- **Token Pool Rotation:** Manages rate limits by rotating through secondary GitHub tokens dynamically.

## System Architecture (High-Level)

Farm-Agent follows the **DeerFlow** pattern—a custom registry-based agent architecture. The pipeline coordinates operations via a Click-based CLI (`farm_agent`).

The core execution loop (Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR) interacts with an LLM Provider (such as MiniMax, OpenRouter, Gemini, OpenAI, or Anthropic) and the GitHub REST/GraphQL APIs.

State and persistent memory are managed using an SQLite database with Write-Ahead Logging (WAL) via `aiosqlite`. A ChromaDB Retrieval-Augmented Generation (RAG) index is used for local contextual intelligence. Before submission, code patches undergo strict validation inside an ephemeral Docker Sandbox. If a patch fails validation, the agent initiates a DEV-QA self-correction loop to refine the fix.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **Hatchling:** Used as the build backend

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   make install
   # Or manually: pip install -e '.[dev]'
   ```

### Environment Variables

Configure the agent using `config.yaml` or set the following environment variables (copy `.env.example` to `.env`):

- `GITHUB_TOKEN`: Your GitHub Personal Access Token (or retrieved via `gh auth token`).
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary tokens for rate limit rotation.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `OPENROUTER_API_KEY`: API key for OpenRouter (e.g., for Red Team models).
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: For notifications (optional).

## Usage

Farm-Agent provides a comprehensive CLI for various operational modes:

**Run auto-discovery and contribute:**
```bash
farm_agent run
```

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Aggressive multi-round discovery and contribution (Hunt):**
```bash
farm_agent hunt --rounds 5
```

**Circular target processing (from target_repo.json):**
```bash
farm_agent hunt-circular
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Analyze a repository without contributing (Dry Run / Analysis Only):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**View overall performance statistics:**
```bash
farm_agent stats
```

**Check system status (memory, PRs, rate limits):**
```bash
farm_agent system-status
```

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
