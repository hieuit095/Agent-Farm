# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen?logo=pytest)](tests/)

## Overview

Farm-Agent is a highly advanced, autonomous AI software engineer designed to actively discover, analyze, and contribute to open-source GitHub repositories. Rather than simply raising PRs blindly, it utilizes an "Issue-First" methodology, validates patches via isolated Docker sandboxes, and orchestrates its actions using a "Super Human" mode to mimic organic, human developer workflows and circumvent spam detection.

## Key Features

- **Multi-Strategy Analysis:** Employs concurrent security, code quality, UI/UX, and performance analyzers.
- **Issue-First Pipeline:** Prefers solving open GitHub issues before falling back to static analysis to ensure contributions are valuable to maintainers.
- **Polyglot Sandbox Validation:** Validates patches dynamically in isolated Docker containers before opening any PRs, supporting languages like Python, Node.js, TypeScript, Go, Rust, and more.
- **Context-Aware Code Generation:** Integrates ChromaDB for Local Retrieval-Augmented Generation (RAG) to understand repository-wide code contexts using word-frequency embedding models.
- **PR Patrol (Auto-Heal):** Continuously monitors its opened pull requests, reading maintainer feedback, fixing code formatting, answering questions, and pushing updates automatically.
- **Super Human Mode:** Operates on a stochastic daily schedule simulating human workflows (wake times, circadian rhythm, typing speeds, stress breaks, lunch breaks).
- **Familiar Grounds Sync:** Prioritizes and tracks repositories where the user has previously successfully merged PRs, continuously discovering VIP open-source projects.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops low-impact (e.g., formatting, docs, typo) contributions to maintain high submission quality.
- **Janitor Mode:** Sweeps through all opened PRs, using an LLM to evaluate and destroy garbage or exploratory PRs.

## System Architecture (High-Level)

Farm-Agent is built on a rich **Click** command-line interface. The core execution engine revolves around `ContribPipeline` and `SuperHumanLoop`, orchestrating multiple sub-systems:
- **LLM Engine:** Multi-model routing (defaulting to Minimax models) handles code generation, finding evaluation, and vibe checks.
- **SQLite Memory:** Persistent state and run logs are managed via `aiosqlite` using Write-Ahead Logging (WAL) mode for concurrency safety.
- **Sandbox Environment:** Patches are dynamically tested within ephemeral Docker environments.
- **GitHub Integration:** An asynchronous HTTPX client orchestrates repository discovery, issue tracking, and PR creations securely.

## Getting Started

### Prerequisites

- **Python**: `>= 3.11`
- **Docker**: `>= 7.1` (Required for Sandbox Validation)
- **Git**: `>= 2.0` (For patching and cloning operations)

### Installation

Clone the repository and build the local development environment:

```sh
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent

# Use the included Makefile to install dependencies (hatchling, pytest, ruff, etc.)
make install
```

### Environment Variables

Configuration is handled primarily via `config.yaml`. To authenticate external services, the following environment variables are required (you can set these in your environment or via `.env` files in docker-compose):

- `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires `repo` scope).
- `MINIMAX_API_KEY`: API Key for Minimax LLM (default engine).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.

Alternatively, you may also define `GEMINI_API_KEY` or other provider variables as needed.

## Usage

Farm-Agent provides several powerful CLI commands:

**1. Run a Hunt Mode Round (Discover, analyze, and generate PRs)**
```sh
farm_agent hunt --rounds 5 --delay 30 --mode both
```

**2. Target a Specific Repository**
```sh
farm_agent target https://github.com/owner/repo
```

**3. Solve Open Issues on a Repository**
```sh
farm_agent solve https://github.com/owner/repo --max-issues 3
```

**4. Start Super Human Mode (24/7 Autonomous Daemon)**
```sh
farm_agent superhuman
```
*Note: You can also run the 24/7 autonomous mode via Docker Compose:* `docker compose up -d superhuman`

**5. PR Patrol (Review and react to maintainer feedback)**
```sh
farm_agent patrol
```

**6. Janitor Sweep (Evaluate and close garbage PRs)**
```sh
farm_agent janitor
```

**7. Check System Statistics & Status**
```sh
farm_agent stats
farm_agent system-status
```

## Contributing & License

We welcome contributions! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) for details on submitting pull requests to the project. Check out the [ARCHITECTURE_AND_WORKFLOW.md](ARCHITECTURE_AND_WORKFLOW.md) for in-depth technical details.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.