# 🛠️ Farm-Agent

**Autonomous System for Open Source Contributions on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise patches via LLM, validate them in sandboxed environments, and submit Pull Requests. It ensures contributions provide genuine value to maintainers by avoiding trivial formatting fixes and verifying code before submission.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs code quality, security, and architecture analyzers against repository file trees.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to address code review comments.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays and randomized PR quotas to mimic human-like pacing.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator interacts with LLM Providers (MiniMax, OpenAI, Anthropic, Gemini, Ollama) and the GitHub API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with repository scope
- **LLM API Key:** API Key for your preferred provider (e.g., MiniMax, OpenRouter)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   make install
   ```
   Or using pip:
   ```bash
   pip install -e '.[dev]'
   ```

### Environment Variables

Configure the agent using `config.yaml` or set the following key environment variables in a `.env` file (copy `.env.example` to `.env`):

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation.
- `MINIMAX_API_KEY`: Your Minimax API Key (or other provider keys like `OPENROUTER_API_KEY`).
- `TELEGRAM_BOT_TOKEN`: Token for Telegram notifications.

Alternatively, copy `config.example.yaml` to `config.yaml` and fill in your details.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target <url>
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve <url>
```

**Run aggressive multi-round discovery:**
```bash
farm_agent hunt
```

**Run the circular target loop (DEV-QA cycle):**
```bash
farm_agent hunt-circular
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Analyze a repository without creating PRs:**
```bash
farm_agent analyze <url>
```

**Other useful commands:**
- `farm_agent stats`: View project statistics.
- `farm_agent status`: View PR statuses.
- `farm_agent leaderboard`: View PR stats and repo rankings.
- `farm_agent gc`: Purge old database entries.
- `farm_agent cleanup`: Clean up forks.
- `farm_agent config`: Show configuration.
- `farm_agent models`: Show available LLM models.
- `farm_agent templates`: List contribution templates.

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
