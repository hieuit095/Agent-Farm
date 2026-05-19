# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, scan their code for issues, generate precise patches via LLMs, validate those patches in an isolated Docker sandbox, and submit high-quality Pull Requests.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving open GitHub issues before falling back to static code analysis.
- **Bloodhound Red Team:** Utilizes `ast-grep` and Semgrep pre-scans to detect and patch security vulnerabilities.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate patches.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure contextual accuracy.
- **PR Patrol:** Autonomously monitors open PRs to auto-fix issues or reply to maintainers.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings and blocks documentation-only PRs to prevent spamming.
- **Super Human Mode:** A 24/7 autonomous daemon that mimics a developer's circadian rhythm with simulated coding delays and quotas.

## System Architecture (High-Level)

The agent operates via a Click-based CLI (`farm_agent`) wrapping the core `ContribPipeline` orchestrator. It uses an LLM Provider (Minimax or OpenRouter) paired with an ephemeral ChromaDB vector store for context. Code generation patches are subsequently verified inside an ephemeral Docker Sandbox before creating a GitHub PR. State is persistently tracked in a WAL-enabled SQLite database (`data/memory.db`).

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher
- **GitHub PAT:** A Personal Access Token with repository scopes
- **LLM API Key:** Minimax or OpenRouter API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Core variables expected in `.env`:
- `GITHUB_TOKEN`: GitHub Personal Access Token
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for API load balancing
- `MINIMAX_API_KEY`: API Key for the default Minimax model
- `MINIMAX_GROUP_ID`: Minimax Group ID (if applicable)
- `OPENROUTER_API_KEY`: Key for Bloodhound Red Team audits via OpenRouter
- `TELEGRAM_BOT_TOKEN`: Token for push notifications
- `EXCLUDED_LANGUAGES`: Languages to skip during discovery

## Usage

**Run a single hunt round:**
```bash
farm_agent hunt --rounds 1
```

**Target a specific repository directly:**
```bash
farm_agent target <url>
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve <url>
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**View overall performance statistics:**
```bash
farm_agent stats
```

**Other available commands:**
`run`, `hunt-circular`, `models`, `leaderboard`, `notify-test`, `system-status`

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
