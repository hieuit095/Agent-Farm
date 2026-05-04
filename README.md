# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker 7.1+](https://img.shields.io/badge/docker-7.1%2B-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is an autonomous system that automatically discovers open-source GitHub repositories, analyzes them for vulnerabilities or improvements, generates precise code patches, and submits pull requests. Driven by a relentless Terminator Execution Loop, it maximizes contribution throughput up to daily API caps while rigorously validating code changes in an isolated polyglot sandbox to ensure stability.

## Key Features

- **Bloodhound Red Team Pipeline:** Employs advanced code analysis using `ast-grep` and `semgrep` alongside OpenRouter LLM routing for intelligent White-Hat auditing of target repositories.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches across multiple languages before creating a Pull Request, dropping any patches that fail tests or linters.
- **Terminator Execution Loop:** A relentless 24/7 autonomous engine orchestrated via `docker-compose` that pushes PR throughput up to maximum allowable daily API caps without human intervention or simulated delays.
- **PR Patrol:** Autonomously monitors open Farm-Agent PRs for maintainer feedback. It dynamically classifies incoming comments and autonomously generates and pushes code fixes in response to maintainer reviews.
- **Anti-Farming Filter:** A strict, zero-tolerance gateway that outright blocks trivial findings (e.g., formatting tweaks) and documentation-only PRs, ensuring high-impact contributions and preventing repository spam.
- **Token Pool Rotation:** Built-in rotation of multiple GitHub secondary tokens to distribute read-only GET API load, successfully avoiding secondary rate limit blocks from GitHub.
- **Circular Target Loop:** Maintains a safe, crash-resilient rotating queue of target repositories mapped into its persistent storage memory, ensuring a robust and uninterrupted flow of operations.

## System Architecture (High-Level)

Farm-Agent operates through a unified core CLI orchestration module mapped sequentially into a **Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR** execution flow. Starting with an evaluation phase through the Bloodhound Red Team module, it identifies and maps actionable codebase issues. The agent utilizes **Minimax (ABAB models)** as its primary LLM provider, with an intelligent fallback to **OpenRouter** when API ceilings are met. Before deploying changes, generated patches undergo uncompromising examination inside an isolated containerized Sandbox environment (`docker`). Contributions that successfully navigate this flow, and pass the strict Anti-Farming Filter, are committed and submitted as automated pull requests via the integrated PR Manager.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Sandbox environment)
- **Hatchling:** Required build backend

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

Configure the agent using `config.yaml` or set the following environment variables in a `.env` file based on `.env.example`:

- `GITHUB_TOKEN`: **(Required)** Your GitHub Personal Access Token (for write operations).
- `GITHUB_SECONDARY_TOKENS`: **(Optional)** Comma-separated secondary tokens for GET request rotation.
- `MINIMAX_API_KEY`: **(Required)** Your Minimax API Key for primary LLM code generation.
- `OPENROUTER_API_KEY`: **(Optional)** API key for OpenRouter, acting as Red Team LLM fallback.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`: Optional keys for event notification channels.

## Usage

Farm-Agent provides an array of CLI commands operated via the `farm_agent` command:

**Run a single hunt cycle (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Target a direct repository to assess and create PRs:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve complex open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Launch the persistent circular targeting loop:**
```bash
farm_agent hunt-circular data/target_repo.json
```

**Monitor open PRs and auto-respond to maintainer feedback:**
```bash
farm_agent patrol
```

**View overall pipeline metrics and performance statistics:**
```bash
farm_agent stats
```

*(Note: The legacy daemon, Janitor CLI, VIP tracking, and human-delayed modes have been disabled/removed in Farm-Agent v3.0+).*

## Contributing & License

We welcome contributions! Please follow standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
