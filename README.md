# Agent-Farm

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Docker Version](https://img.shields.io/badge/docker-7.1%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

Agent-Farm is an autonomous AI system that automatically contributes to open source projects on GitHub. By integrating deep codebase reconnaissance, dynamic sandbox execution, and advanced multi-agent orchestration, it discovers repositories, analyzes their architecture, generates meaningful contributions, and submits verified pull requests.

## Key Features

*   **Omniscient Context Engine**: Deep documentation discovery and linkage mapping utilizing RAG (Retrieval-Augmented Generation) and ChromaDB to parse and retrieve semantic codebase chunks.
*   **Terminator Mode**: A relentless, continuous execution loop (`SuperHumanLoop`) that processes target repositories without artificial delays.
*   **Bloodhound Red Team**: Advanced vulnerability auditing combining `ast-grep` and Semgrep via `BloodhoundAnalyzer`.
*   **Dynamic Bug Verification**: Isolated Proof of Concept (PoC) execution and validation using a custom `DockerSandbox` to guarantee exploitability and correctness.
*   **Blast Radius & Regression Auditing**: Employs `ReviewerAgent` to perform self-reflective code auditing, identifying the impact of proposed changes before submission.
*   **Anti-Farming Filter**: A strict heuristic filter that blocks trivial or low-effort PRs (e.g., purely cosmetic documentation tweaks), ensuring high-quality contributions.

## System Architecture (High-Level)

Agent-Farm leverages a multi-layered architecture coordinated by the `FarmAgentPipeline`.
*   **Discovery & Target Routing**: Pulls targets from databases or GitHub APIs using strategies like `DatabaseTargetDiscovery`.
*   **Deep Analysis**: Parses code ASTs and dependencies to build a module linkage graph (`RepoMapper`).
*   **Secure Validation**: Generates fixes and validates them dynamically within an isolated `DockerSandbox`.
*   **State Persistence**: Uses a WAL-mode SQLite database (`data/memory.db`) to track analyzed repositories, run logs, PR outcomes, and API rate limits.
*   **Multi-Model LLM Routing**: Intelligently routes tasks to appropriate models (e.g., DeepSeek via OpenRouter, Qwen, Gemini) depending on the task requirements.

## Getting Started

### Prerequisites

*   **Python**: `>= 3.11`
*   **Docker**: `>= 7.1` (Required for dynamic bug verification and sandboxing)

### Installation

**Option 1: 1-Click Docker Launch (Recommended)**

```bash
./start.sh
# For Windows: start.bat
```

**Option 2: Local Development Setup**

```bash
# Clone the repository
git clone https://github.com/hieuit095/Agent-Farm.git
cd Agent-Farm

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with development dependencies
pip install -e '.[dev]'
```

### Environment Variables

Before running Agent-Farm, copy `.env.example` to `.env` and fill in the required values. The following core variables are required or supported:

*   `GITHUB_TOKEN`: Primary GitHub Personal Access Token (with `repo`, `read:org`, and `workflow` scopes).
*   `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary GitHub tokens for GET request load balancing.
*   `MINIMAX_API_KEY`: API key for Minimax (if using Minimax provider).
*   `MINIMAX_GROUP_ID`: Minimax group ID for specific plans.
*   `OPENROUTER_API_KEY`: OpenRouter API key for Red Team audits and general multi-model LLM access.
*   `EXCLUDED_LANGUAGES`: Comma-separated list of languages to skip (e.g., `javascript,typescript`).
*   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: For push notifications via Telegram.
*   `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`: Webhooks for Slack and Discord notifications.

## Usage

Agent-Farm operates entirely through a rich CLI interface.

```bash
# Target a specific repository
farm_agent target https://github.com/owner/repo

# Analyze a repository without contributing (dry run)
farm_agent analyze https://github.com/owner/repo

# Run in Terminator Mode (SuperHumanLoop) for relentless continuous execution
farm_agent superhuman

# View the leaderboard of repositories and merge rates
farm_agent leaderboard

# View the system status and database metrics
farm_agent system-status
```

## Contributing

We welcome contributions! Please review our coding guidelines. We enforce code style using `ruff` with a 100-character line limit. Ensure that you run `make lint` and `make test` before submitting changes.

## License

This project is licensed under the [MIT License](LICENSE).
