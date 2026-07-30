# 🛠️ Agent-Farm (v4.0.0)

**Autonomous system that automatically contributes to open source projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## 🚀 Overview

Agent-Farm is an autonomous system that crawls open-source GitHub repositories to pinpoint real security vulnerabilities, solve issues, and automatically generate high-quality, regression-free pull requests. It leverages multi-agent pipelines and isolated Docker sandboxing to evaluate patches thoroughly before submitting them, ensuring every contribution provides tangible value to project maintainers.

## 🔥 Key Features

*   **Omniscient Context Engine**: Deep codebase understanding using RAG (ChromaDB) to recursively discover internal documentation and AST-based graphing to inject precise module dependencies.
*   **Dynamic Bug Verification**: Generates self-contained Proof-of-Concept (PoC) scripts to validate vulnerabilities dynamically inside locked-down Docker sandboxes.
*   **Blast Radius & Regression Auditing**: Ensures generated patches do not cause regressions by running native test suites and validating fixes in a localized sandbox environment.
*   **Anti-Farming Filter**: A strict two-layer gatekeeper pipeline powered by Qwen and Gemini models to discard trivial or typo-fixing PRs.
*   **Terminator Mode**: A relentless continuous execution loop (`SuperHumanLoop`) that systematically processes targets from a deterministic database.
*   **Issue-First Pipeline & PR Patrol**: Solves specific open issues accurately, whilst PR Patrol automatically interacts with maintainer comments, pushes CI fixes, and iterates patches autonomously.

## 🏗️ System Architecture (High-Level)

Agent-Farm operates as a multi-stage, autonomous pipeline orchestrated around an issue-first and bug-discovery loop. Upon identifying a target repository, the system maps code dependencies via an AST-powered RAG context engine, building a profound understanding of the codebase structure. Vulnerabilities or issues are identified and dispatched to a multi-model LLM generation tier (utilizing DeepSeek and specialized Qwen/Gemini models via OpenRouter). Proposed patches are subjected to rigorous testing within isolated Docker sandboxes, including Proof-of-Concept execution and full regression test audits. Only after a strict "Anti-Farming" vetting process confirms the value and safety of a patch is a Pull Request or private security disclosure finalized via the GitHub client. State, learning logs, and targeting queues are continuously persisted to an optimized local SQLite WAL-mode database.

## 🛠️ Getting Started

### Prerequisites

*   **Python**: >= 3.11
*   **Docker**: >= 7.1
*   **Git** installed on the host machine.

### 1-Click Launch

The simplest and recommended way to start Agent-Farm is via the provided Docker Quick-Start scripts, which handle configuration, pulling the latest code, building the image, and launching the daemon.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hieuit095/Agent-Farm.git
    cd Agent-Farm
    ```

2.  **Initialize Environment Configuration:**
    Copy the sample configuration file.
    ```bash
    cp .env.example .env
    ```

3.  **Run the Quick-Start Script:**
    *   **Windows:**
        ```cmd
        start.bat
        ```
    *   **Unix (Linux/macOS):**
        ```bash
        chmod +x start.sh
        ./start.sh
        ```

### Environment Variables

Configure your `.env` file with the exact variables required by the system. Note: omit development keys when setting up the public deployment.

*   `GITHUB_TOKEN`: (Required) Personal access token with `repo`, `read:org`, and `workflow` scopes.
*   `OPENROUTER_API_KEY`: (Required) API key for OpenRouter to access DeepSeek, Qwen, and Gemini models.
*   `EXCLUDED_LANGUAGES`: (Optional) Comma-separated list of languages to ignore (e.g., `javascript,typescript`).
*   `GITHUB_SECONDARY_TOKENS`: (Optional) Additional tokens for read-only GET request rotation.
*   `TELEGRAM_BOT_TOKEN`: (Optional) Telegram bot token for push notifications.
*   `TELEGRAM_CHAT_ID`: (Optional) Destination chat ID for Telegram.
*   `SLACK_WEBHOOK_URL`: (Optional) Webhook URL for Slack notifications.
*   `DISCORD_WEBHOOK_URL`: (Optional) Webhook URL for Discord notifications.
*   `MINIMAX_API_KEY`: (Optional) API key for Minimax.
*   `MINIMAX_GROUP_ID`: (Optional) Group ID for Minimax.

## 💻 Usage

Once the Agent-Farm daemon is running in Docker, you can interact with the CLI by executing commands against the container.

Attach to the CLI and run the primary continuous mode (Terminator Mode):
```bash
docker exec -it agent-farm farm_agent superhuman
```

Run a specific hunt pipeline directly:
```bash
docker exec -it agent-farm farm_agent hunt
```

Solve issues for a particular open-source target:
```bash
docker exec -it agent-farm farm_agent solve <repo_url>
```

Check the status of the system and view open PR queues:
```bash
docker exec -it agent-farm farm_agent status
```

View the runtime statistics and leaderboard:
```bash
docker exec -it agent-farm farm_agent stats
docker exec -it agent-farm farm_agent leaderboard
```

## 🤝 Contributing & License

We welcome white-hat security researchers, developers, and AI enthusiasts to contribute to Agent-Farm. Please ensure changes are covered by tests and adhere to the strict code conventions via `make lint`.

Agent-Farm is open-source software licensed under the [MIT License](LICENSE).
