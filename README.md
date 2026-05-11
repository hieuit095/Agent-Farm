# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous AI software engineer designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise code patches via LLMs, and submit pull requests. To ensure high-quality contributions and minimize maintainer friction, all patches are rigorously tested in an isolated polyglot Docker sandbox and gated by strict anti-farming policies before submission.

## Key Features

- **Polyglot Sandbox Validation:** Uses isolated Docker containers (`network_mode="none"`) to execute and validate generated code patches for multiple languages (Python, JavaScript, Rust, TypeScript, etc.) before any PR is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, UI/UX, and documentation analyzers against repository file trees. Integrates Bloodhound (Semgrep) for robust pre-scans.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that strictly blocks trivial findings (e.g., typos, pure formatting) and bans documentation-only PRs to prevent spamming maintainers.
- **PR Patrol:** Autonomously monitors open PRs for maintainer review feedback, uses an LLM to classify comments, and generates/pushes automated code fixes to address the feedback.
- **Super Human Mode:** A relentless 24/7 autonomous daemon that operates organic hunt and patrol execution loops to seamlessly maximize contribution throughput.
- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues via an intelligent estimation heuristic before falling back to static codebase analysis.
- **Security Disclosure Gate:** Scans repository meta files (`SECURITY.md`, etc.) for private disclosure instructions to prevent public leaks of sensitive vulnerabilities.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a `click`-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts seamlessly with Large Language Model Providers (primarily utilizing Minimax ABAB models, with OpenRouter backups for White-Hat auditing) and the GitHub REST/GraphQL APIs.

State and task scheduling are persistently managed in a highly concurrent local SQLite database running in WAL mode (`aiosqlite`). When generating patches, the engine employs a local ChromaDB vector store for accurate code retrieval. Most critically, every generated code patch is passed to an ephemeral Docker Sandbox Guillotine—if the patch causes build or test failures, the agent attempts a self-correction loop before halting submission.

## Getting Started

### Prerequisites

- **Python:** `3.11`, `3.12`, or `3.13`
- **Docker:** `7.1` or higher (Required for Polyglot Sandbox execution)
- **GitHub PAT:** A Personal Access Token with standard `repo` scopes.
- **LLM API Key:** A valid Minimax API Key (or OpenRouter/Ollama alternative).

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

Configure the agent using `config.yaml` (copy from `config.example.yaml`) or set the following environment variables (using a `.env` file):

- `GITHUB_TOKEN`: Primary Personal Access Token for read/write GitHub operations.
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated tokens to distribute GET request loads.
- `MINIMAX_API_KEY`: API Key for the Minimax LLM provider.
- `MINIMAX_GROUP_ID`: (Optional) Minimax Group ID header if required.
- `OPENROUTER_API_KEY`: (Optional) Used by the Bloodhound Red Team pipeline for White-Hat audits.
- `EXCLUDED_LANGUAGES`: (Optional) Comma-separated list to filter languages (e.g. `javascript,typescript`).
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: (Optional) Used for Telegram push notifications on events.
- `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`: (Optional) Webhook URLs for additional notifications.

## Usage

Farm-Agent provides an extensive CLI toolchain for targeted or autonomous operations:

**Run a single hunt round (auto-discover, analyze, and create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Run a continuous circular targeting loop on known repositories:**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Monitor open PRs and auto-respond to maintainer feedback:**
```bash
farm_agent patrol
```

**Run the 24/7 autonomous daemon loop (Super Human Mode):**
```bash
farm_agent superhuman
```

**View overall pipeline performance statistics:**
```bash
farm_agent stats
```

## Contributing & License

Contributions to the pipeline logic, sandbox support, and analyzers are highly encouraged. Please run all tests (`pytest tests/`) and follow the `ruff` code formatting before submitting pull requests.

This project is open-source and licensed under the **MIT License**. See the `LICENSE` file for full details.