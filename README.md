# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It operates behind a sophisticated human behavior simulation layer to ensure all contributions provide genuine value to maintainers while respecting project guidelines.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across 12 supported languages) before any Pull Request is created.
- **Bloodhound Red Team Pipeline:** Incorporates `ast-grep` and Semgrep pre-scans for robust vulnerability discovery and security auditing.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback and autonomously generates and pushes code fixes in response.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and strictly blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a relentless Terminator execution loop to maximize PR throughput up to daily API caps, utilizing multi-process coordination.
- **Token Pool Rotation:** Manages GitHub GET request rotation using secondary tokens to effectively handle and distribute API rate limits.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with LLM Providers (primarily Minimax ABAB models, with OpenRouter routing for White-Hat audits) and the GitHub REST API. State is persistently managed in an SQLite database (`memory.db`) using WAL mode.

The core execution loop follows these sequential steps: **Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**.

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is strictly validated inside an ephemeral Docker Sandbox operating on a restricted internal network. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Polyglot Sandbox Validation and `agent-farm` service isolation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** Minimax API key (default) or supported alternatives (OpenRouter, Gemini, OpenAI, Anthropic, Ollama)

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

3. (Optional) Run via Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Environment Variables

Configure the agent by copying `config.example.yaml` to `config.yaml` and `.env.example` to `.env`. The system relies on the following key environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token (Required).
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (Optional, comma-separated).
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID (Optional based on plan).
- `OPENROUTER_API_KEY`: API key for White-Hat auditing fallback via OpenRouter (Optional).

*Notifications (Optional):*
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
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

**Run a circular target hunt from target_repo.json:**
```bash
farm_agent hunt-circular
```

**Analyze a repository without creating PRs:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**View overall system status (memory, PRs, rate limits):**
```bash
farm_agent system-status
```

*Note: The `janitor` command is currently disabled.*

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
