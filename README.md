# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise code fixes via LLM, validate them in polyglot sandboxes, and submit high-quality Pull Requests.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues (`issues/solver.py`) before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Red Team Bloodhound Analyzer:** Runs Semgrep pre-scans and leverages OpenRouter for vulnerability discovery.
- **Contextual RAG Indexing:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays to mimic a real developer's workflow.
- **DEV-QA Bounty Loop:** A cycle loop where generated patches are evaluated and retried up to 3 times before submission.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with LLM Providers (MiniMax, OpenRouter via Gemini, OpenAI, Anthropic) and the GitHub REST & GraphQL APIs. State is persistently managed in an SQLite database using Write-Ahead Logging (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a DEV-QA loop with self-correction before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   pip install -e '.[dev]'
   ```

### Environment Variables

Configure the agent by copying `config.example.yaml` to `config.yaml` and `.env.example` to `.env`, then setting the following core environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `OPENROUTER_API_KEY`: Your OpenRouter API Key (required for Red Team engine).
- `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token (for notifications).

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Analyze a repository without contributing:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Hunt aggressively across multiple discovery rounds:**
```bash
farm_agent hunt --rounds 5
```

**Circular Target Loop (round-robin from JSON):**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Check status of submitted PRs:**
```bash
farm_agent status
```

**View overall performance statistics:**
```bash
farm_agent stats
```

**Show current configuration:**
```bash
farm_agent config
```

## Contributing & License

We welcome contributions! Please refer to standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.