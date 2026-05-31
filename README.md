# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous system designed to automatically contribute to open-source GitHub repositories. It discovers repositories matching specific criteria, scans their code for issues (security vulnerabilities, code quality bugs, performance problems, etc.), generates patches via LLMs, strictly validates patches in isolated Docker sandboxes, and opens Pull Requests to contribute back.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute, compile, and validate generated patches before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees.
- **RAG Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and respond to discussions.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays to mimic a real developer's circadian rhythm.
- **Multi-Model LLM Support:** Easily configure different LLM providers (Minimax, Gemini, OpenAI, Anthropic, or local Ollama models).

## System Architecture (High-Level)

The system orchestrates its operations via a CLI (`farm_agent`). The core execution loop follows these steps:
**Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**

- **Discovery & Gate:** Finds relevant repositories using GitHub's API and applies a Security Gate to filter out protected or unauthorized projects.
- **Analysis & Engine:** Uses multi-strategy analysis (security, code quality, docs) and an LLM-driven generation engine to propose patches based on issues or static findings.
- **Sandbox:** Generated code is validated in an ephemeral Docker sandbox to ensure tests pass and code compiles.
- **PR & Memory:** Finally, issues Pull Requests. State is persistently managed in an SQLite database (`aiosqlite`) to avoid duplicating work.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** >= 7.1
- **Git**

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with development dependencies:
   ```bash
   pip install -e '.[dev]'
   ```

### Configuration & Environment Variables

1. Copy the example configuration and `.env` files:
   ```bash
   cp config.example.yaml config.yaml
   cp .env.example .env
   ```

2. Configure your environment variables in `.env`:
   - `GITHUB_TOKEN`: (Required) Your GitHub personal access token with repo scopes.
   - `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated list of GitHub tokens for GET request rotation.
   - `MINIMAX_API_KEY`: (Required if using Minimax) API key for the default Minimax LLM.
   - `OPENROUTER_API_KEY`: (Optional) API key for OpenRouter (used by Bloodhound Red Team pipeline).
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`: (Optional) Webhooks and tokens for notifications.

3. Update `config.yaml` to configure the system (e.g., target LLM provider, GitHub preferences, Sandbox settings).

## Usage

Farm-Agent is operated entirely via its robust CLI. Example commands:

```bash
# Run the pipeline on a single specific repository
farm_agent target https://github.com/owner/repo

# Start an autonomous hunt to discover and patch repos
farm_agent hunt --rounds 5

# Run a circular target loop processing repositories from target_repo.json
farm_agent hunt-circular

# Run the 24/7 Super Human autonomous loop
farm_agent superhuman

# Monitor PRs and reply to maintainer feedback
farm_agent patrol

# View system memory, rate limits, and PR statistics
farm_agent system-status

# Display the leaderboard of contributions
farm_agent leaderboard

# Sweep and auto-close garbage PRs via LLM evaluation
farm_agent janitor

# View overall performance statistics
farm_agent stats
```

## Contributing & License

Contributions to Farm-Agent are welcome! Please ensure you test your changes locally using `pytest` or `make test` before submitting a PR.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
