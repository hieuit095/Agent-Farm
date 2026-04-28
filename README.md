# 🛠️ Farm-Agent

**Autonomous System that Automatically Contributes to Open Source Projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced system designed to autonomously analyze open-source GitHub repositories, identify vulnerabilities or bugs, generate precise fixes, and submit pull requests. Leveraging large language models, static analysis tools, and isolated code execution environments, Farm-Agent aims to provide genuine value to maintainers at scale.

## Key Features

- **Bloodhound Red Team:** An auditing engine leveraging ast-grep and Semgrep to discover vulnerabilities, integrated with a multi-model routing system (including OpenRouter for white-hat audits).
- **Terminator Execution Loop:** A relentless 24/7 daemon operating via Docker Compose to maximize PR throughput up to daily API limits.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated code across multiple languages before any Pull Request is created.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and strictly blocks documentation-only PRs to prevent spamming maintainers.
- **DEV-QA Bounty Loop:** An iterative quality assurance validation process prior to PR submission.
- **PR Patrol:** Autonomously monitors open Farm-Agent PRs for maintainer feedback, classifies comments using an LLM, and pushes necessary code fixes.
- **Circular Target Loop:** A continuous processing cycle rotating through targeted repositories to maximize efficiency.
- **Token Pool Rotation:** Built-in secondary token support (`GITHUB_SECONDARY_TOKENS`) for GitHub GET requests to manage and bypass strict API rate limits.
- **Ephemeral RAG Context:** Utilizes ChromaDB for RAM-only, local Retrieval-Augmented Generation to ensure contextual awareness across codebases.

## System Architecture (High-Level)

Farm-Agent orchestrates its operations via the `farm_agent` CLI tool. The system operates on a core execution loop: **Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**. It interacts with configured LLM Providers (e.g., Minimax, Gemini, OpenAI, Anthropic, OpenRouter) for code analysis and generation, and the GitHub REST API for reading repositories and creating pull requests.

Code patches are generated via an LLM engine augmented by an ephemeral ChromaDB RAG index. Before submission, every patch must pass validation in a Polyglot Sandbox environment orchestrated via the Docker SDK, which includes isolated internal network setups (`sandbox_isolated`). Persistent operational data is stored in an SQLite database using WAL mode.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1
- **GitHub Token:** A Personal Access Token with necessary repository scopes.
- **LLM API Key:** Access to an LLM provider (e.g., `MINIMAX_API_KEY`, `GEMINI_API_KEY`, etc.).

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

Configure the agent by copying `.env.example` to `.env` and `config.example.yaml` to `config.yaml`.

Required environment variables include:
- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token for API writes.
- `MINIMAX_API_KEY` (or equivalent provider key like `GEMINI_API_KEY`): Your LLM API Key.

Optional environment variables:
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary tokens for GET request rotation.
- `OPENROUTER_API_KEY`: API key for Bloodhound Red Team White-Hat audits.
- Notification configurations: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`.

## Usage

Farm-Agent features a Click-based CLI for various operational modes:

**Auto-discover repositories and contribute:**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target <url>
```

**Run the Relentless Terminator Daemon:**
```bash
farm_agent superhuman
```

**Circular Target Loop (process from target_repo.json):**
```bash
farm_agent hunt-circular
```

**Monitor open PRs and auto-respond (PR Patrol):**
```bash
farm_agent patrol
```

**Analyze a repository without contributing:**
```bash
farm_agent analyze <url>
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve <url>
```

**Check overall system status and memory state:**
```bash
farm_agent system-status
```

## Contributing & License

Refer to the project's issue tracker for ongoing tasks.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.