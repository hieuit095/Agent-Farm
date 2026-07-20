# 🛠️ Agent-Farm

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## 🚀 Overview

Agent-Farm is an autonomous system that automatically contributes to open source projects on GitHub. It discovers repositories, analyzes them for issues or vulnerabilities, generates high-quality fixes, validates them in an isolated Docker sandbox, and submits pull requests or private disclosures with human-like precision.

## 🔥 Key Features

- **Omniscient Context Engine:** Uses Retrieval-Augmented Generation (RAG) powered by ChromaDB to index project documentation and build AST-based dependency graphs for injected prompt context.
- **Anti-Farming Filter:** A stringent dual-layer gatekeeping system that strictly blocks trivial, formatting, or documentation-only PRs, ensuring only high-value contributions are made.
- **Dynamic Bug Verification:** Executes generated Proof-of-Concept (PoC) scripts inside isolated Docker containers to validate vulnerabilities before attempting to patch them.
- **Blast Radius & Regression Auditing:** Validates generated patches by re-running the PoC (to confirm the fix) and the project's native test suite (to ensure no regressions are introduced).
- **Terminator Mode:** A relentless continuous execution loop (`farm_agent superhuman`) that hunts targets and patrols PRs autonomously.
- **Issue-First Pipeline:** Specifically targets and resolves open issues in repositories (`farm_agent solve <url>`).

## 🏗️ System Architecture (High-Level)

Agent-Farm operates as a multi-agent orchestration pipeline (`FarmAgentPipeline`). It begins with target discovery (GitHub crawling or database queues). Targets are then deeply analyzed (`CodeAnalyzer`, `BloodhoundAnalyzer`) and enriched with context via the Omniscient Context Engine. Identified issues or vulnerabilities are passed to the `ContributionGenerator`, which drafts patches and PoCs. These are rigorously validated in a secure, isolated `DockerSandbox`. Finally, successful fixes are evaluated by an `Expert Appraisal` layer before the `PRManager` submits the contribution to GitHub. The system maintains continuous state and learning in a local SQLite memory database.

## 🛠️ Getting Started

### Prerequisites

- **Python:** `^3.11`
- **Docker:** `>=7.1` (with host socket access)
- **Git**

### Installation & 1-Click Docker Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Initialize Environment Configuration:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Configure the `.env` file with the required variables (see below).

3. **Start the System:**
   - **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   - **Windows:**
     ```cmd
     start.bat
     ```

### Environment Variables (`.env`)

The system requires the following environment variables to function correctly:

- `GITHUB_TOKEN`: Primary GitHub Personal Access Token (requires repo, read:org, workflow scopes).
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated secondary tokens for load-balancing GET requests.
- `MINIMAX_API_KEY`: Required if using Minimax as the primary LLM provider.
- `MINIMAX_GROUP_ID`: Required by some Minimax plans.
- `OPENROUTER_API_KEY`: API key for OpenRouter (used for DeepSeek, Qwen models, etc.).
- `EXCLUDED_LANGUAGES`: Comma-separated list of languages to ignore (e.g., `javascript,typescript`).
- `TELEGRAM_BOT_TOKEN`: (Optional) Telegram bot token for notifications.
- `TELEGRAM_CHAT_ID`: (Optional) Telegram chat ID for notifications.
- `SLACK_WEBHOOK_URL`: (Optional) Slack webhook for notifications.
- `DISCORD_WEBHOOK_URL`: (Optional) Discord webhook for notifications.

## 💻 Usage (CLI Commands)

Agent-Farm provides a robust CLI via the `farm_agent` command. Access it by attaching to the running Docker container:

```bash
docker exec -it agent-farm bash
```

### Core Commands

- **Run Standard Pipeline:** Start discovery, analysis, and contribution.
  ```bash
  farm_agent run
  ```
- **Target Repository:** Target a specific repository directly.
  ```bash
  farm_agent target <repo_url>
  ```
- **Solve Issues:** Solve open issues for a specific repository.
  ```bash
  farm_agent solve <repo_url>
  ```
- **Hunt Mode:** Aggressively discover repos and solve issues/bugs.
  ```bash
  farm_agent hunt --rounds 5
  ```
- **Circular Hunt:** Run hunt on deterministic circular target queue.
  ```bash
  farm_agent hunt-circular
  ```
- **Superhuman (Terminator Mode):** Run the relentless 24/7 continuous execution loop.
  ```bash
  farm_agent superhuman
  ```
- **Patrol PRs:** Check open PRs for maintainer comments and push CI auto-fixes.
  ```bash
  farm_agent patrol
  ```

### System & Database Management

- **Status:** View PR queue and system status.
  ```bash
  farm_agent status
  farm_agent system-status
  ```
- **Statistics:** View runtime statistics and LLM usage.
  ```bash
  farm_agent stats
  ```
- **Leaderboard:** View performance leaderboard.
  ```bash
  farm_agent leaderboard
  ```
- **Models:** View configured models.
  ```bash
  farm_agent models
  ```
- **Garbage Collection:** Purge stale database entries.
  ```bash
  farm_agent gc --days 90
  ```
- **Reset Database:** Clear target queues and run logs.
  ```bash
  farm_agent reset-db
  ```
- **View Config:** Show active configuration.
  ```bash
  farm_agent config
  ```
- **VIP Roster:** View alumni sync and full friendly repo list.
  ```bash
  farm_agent vips
  ```
- **Templates:** View builtin templates.
  ```bash
  farm_agent templates
  ```
- **Profiles:** Run with thorough, standard, or quick presets.
  ```bash
  farm_agent profile <profile_name>
  ```

## 📜 Contributing & License

We welcome contributions to Agent-Farm! Please ensure all changes are validated locally using `make test` and `make lint`.

Licensed under the [MIT License](LICENSE).
