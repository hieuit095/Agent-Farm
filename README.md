# 🛠️ Farm-Agent

**Autonomous AI Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous AI agent that discovers open-source GitHub repositories, scans their codebase for actionable issues (e.g., security vulnerabilities, bugs, performance flaws), generates precision patches via Large Language Models, and validates them inside secure Docker sandboxes. Once verified, it autonomously submits Pull Requests or opens Issues, acting as a tireless open-source contributor.

## Key Features

- **Polyglot Sandbox Validation:** Patches are strictly validated in fully isolated Docker containers (`network_mode="none"`, `cap_drop=["ALL"]`) before any Pull Request is created, preventing broken builds.
- **Issue-First Pipeline:** Prioritizes solving open, high-impact GitHub issues before falling back to static codebase analysis.
- **Multi-Strategy Analysis & Red Team Bloodhound:** Combines deterministic rules (Semgrep) and probabilistic LLM audits (OpenRouter models) to detect security vulnerabilities, code quality issues, and UI/UX flaws.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops low-impact findings (e.g., trivial typos, formatting, docstrings) and completely blocks documentation-only PRs to prevent maintainer spam.
- **X-Ray Context Vision:** Builds an ephemeral RAG index (ChromaDB) to retrieve exact cross-file dependencies and context when generating fixes.
- **Super Human Mode:** A 24/7 autonomous daemon that mimics a human developer's rhythm, complete with simulated coding delays, and rate-limit aware execution loops.
- **PR Patrol & Janitor:** Autonomously monitors open PRs to auto-respond to maintainer feedback, attempt self-correction, or sweep and close garbage PRs.

## System Architecture (High-Level)

Farm-Agent is orchestrated via a `click`-based CLI. Its core pipeline (`ContribPipeline`) drives a multi-stage process:
1. **Discovery:** Scrapes GitHub for repos matching specific criteria (language, stars, activity).
2. **Analysis:** Runs code scanners, enforcing strict policy checks (AI blocks, interaction limits, private disclosure gates).
3. **Generation:** Dispatches validated findings to an LLM provider (Minimax, Gemini, OpenRouter, or local Ollama) using an internal task router.
4. **Validation:** Executes the patch inside a sterile Docker container.
5. **Submission:** If successful, pushes changes via `gitpython` and the GitHub API, logging the entire outcome persistently into an SQLite database (via `aiosqlite` in WAL mode).

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo`, `read:org`, and `workflow` scopes.
- **LLM API Key:** Minimax API Key (default) or other supported providers.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package along with its development dependencies:
   ```bash
   make install
   # or manually: pip install -e ".[dev]"
   ```

### Environment Variables

Configure Farm-Agent by copying `config.example.yaml` to `config.yaml` and `.env.example` to `.env`. The core required environment variables are:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token for API interactions.
- `MINIMAX_API_KEY`: API Key for the Minimax LLM (if using the default provider).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated list of secondary tokens for API rate-limit rotation.
- `OPENROUTER_API_KEY`: (Optional) For Red Team Bloodhound security audits.
- Notifications: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`.

## Usage

Farm-Agent is operated via the `farm_agent` CLI tool. Here are the core commands:

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

**Run aggressive multi-round discovery:**
```bash
farm_agent hunt
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Analyze a repo without submitting anything:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**View overall performance statistics and leaderboards:**
```bash
farm_agent stats
farm_agent leaderboard
farm_agent system-status
```

## Contributing & License

We welcome contributions! Please review open issues and submit standard PRs following the configured Ruff formatting.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
