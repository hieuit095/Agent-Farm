# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous AI system designed to discover open-source GitHub repositories matching specific criteria, identify bugs, code quality issues, or security vulnerabilities, and generate and validate precision patches via LLMs. It operates fully autonomously with human-like simulation layers to safely submit valuable Pull Requests.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving open GitHub issues and aligns with maintainers' immediate needs before falling back to static code analysis.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and strictly validate generated patches before creating any Pull Request.
- **X-Ray Context Vision & RAG:** Builds local ChromaDB Retrieval-Augmented Generation (RAG) indexes to fetch exact contexts for safe code patching across multiple files.
- **Anti-Farming Filter:** Zero-tolerance gatekeeper that drops trivial findings (e.g., formatting, typos) and strictly blocks documentation-only PRs to prevent spam.
- **Super Human Mode:** A 24/7 autonomous loop featuring simulated human coding delays, randomized PR quotas, and stochastic schedules mimicking real developer activity.
- **PR Patrol:** Autonomously monitors open PRs to fetch maintainer review feedback and push auto-fixes, answer questions, or handle CI failures.
- **Bloodhound Red Team:** Performs deep vulnerability discovery using Semgrep integrations before applying precision LLM patches.

## System Architecture (High-Level)

The agent operates across a "DeerFlow" execution pipeline initiated via a Click-based CLI (`farm_agent`).
1. **Orchestrator:** `ContribPipeline` orchestrates discovery, analysis, generation, and PR submission.
2. **Datastore:** State and history are persistently managed via SQLite in WAL mode (`aiosqlite`).
3. **Execution Sandbox:** Generated code changes are isolated and validated in an ephemeral Docker environment. If tests fail, the agent triggers a self-correction loop.
4. **LLM Engine:** Supports MiniMax, OpenRouter (Anthropic/OpenAI/Google), or local models like Ollama for advanced code analysis and generation.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A valid Personal Access Token with repo scope
- **LLM API Key:** E.g., `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install dependencies (including development dependencies):
   ```bash
   make install
   # or manually: pip install -e '.[dev]'
   ```

### Environment Variables

Copy `.env.example` to `.env` and `config.example.yaml` to `config.yaml`.
Required core `.env` variables include:
- `GITHUB_TOKEN`: Your GitHub PAT.
- `MINIMAX_API_KEY` or `OPENROUTER_API_KEY`: API keys for the LLM engine.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: (Optional) for notifications.

## Usage

Farm-Agent provides several core CLI commands (`farm_agent --help` for full details):

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Aggressive multi-round discovery + contribution:**
```bash
farm_agent hunt --rounds 3
```

**Round-robin target processing from a database loop:**
```bash
farm_agent hunt-circular
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

**View project statistics and leaderboards:**
```bash
farm_agent system-status
farm_agent leaderboard
```

## Contributing & License

Refer to the `CONTRIBUTING.md` for our internal guidelines. This project is licensed under the **MIT License**. See the `LICENSE` file for full details.
