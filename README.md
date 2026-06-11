# Farm-Agent

![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-supported-blue)
![Status](https://img.shields.io/badge/status-active-success)

## Overview

Farm-Agent (v4.0.0) is a 24/7 autonomous system that automatically contributes to open source projects on GitHub. It operates using an Issue-First Pipeline to discover target repositories, solve complex bugs, optimize code, and submit Pull Requests with simulated human-like behavior.

## Key Features

- **Omniscient Context Engine**: Local Retrieval-Augmented Generation (RAG) codebase mapping using ChromaDB for contextually precise fixes.
- **Dynamic Bug Verification**: Isolated Proof-of-Concept (PoC) execution within a secure DockerSandbox.
- **Blast Radius & Regression Auditing**: Ensures patches do not introduce regressions before submission.
- **Super Human Mode**: A relentless execution loop (`farm_agent superhuman`) that simulates human coding delays and operates 24/7 autonomously.
- **Bloodhound Red Team**: AST-grep and Semgrep-based White-Hat security audits utilizing cost-effective OpenRouter LLMs.
- **Anti-Farming Filter**: Strictly blocks trivial or purely documentation-based PRs to prioritize meaningful code contributions.
- **Multi-Model Intelligence**: Leverages specialized AI models via OpenRouter (e.g., DeepSeek models for general tasks, Qwen for Layer 1 Appraisal, and Gemini for Layer 2 Supreme Audit).

## System Architecture (High-Level)

Farm-Agent follows the custom **DeerFlow** pattern—a registry-based agent architecture. The system orchestrator continuously coordinates tasks across specialized agents (e.g., PR Patrol, IssueSolver). Persistent state and task history are managed by a SQLite database (`memory.db`), ensuring idempotent operations. The entire ecosystem is deployed securely via `docker-compose`, which provides internet and isolated sandbox network boundaries.

## Getting Started

### Prerequisites

- **Python**: `>=3.11`
- **Docker**: `>=7.1` (Required for dynamic bug verification and sandboxing)
- **Git**: Installed and configured

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **Install package and development dependencies**:
   ```bash
   make install
   ```

3. **1-Click Docker Desktop Quick-Start** (Optional but recommended):
   Run the provided start scripts for automated setup:
   - Linux/macOS: `./start.sh`
   - Windows: `start.bat`

### Environment Variables

Copy the `.env.example` file to `.env` and configure your API keys.

```bash
cp .env.example .env
```

Required variables:
- `GITHUB_TOKEN`: Personal Access Token with repo, read:org, and workflow scopes.
- `MINIMAX_API_KEY`: API key for Minimax (default LLM provider if used).

Optional but recommended variables:
- `OPENROUTER_API_KEY`: Used by the Bloodhound Red Team pipeline for cost-effective audits.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary tokens for API rate-limit rotation.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For push notifications on system updates.
- `SLACK_WEBHOOK_URL` & `DISCORD_WEBHOOK_URL`: Additional notification channels.
- `EXCLUDED_LANGUAGES`: Comma-separated languages to filter out (e.g., `javascript,typescript`).

## Usage

Farm-Agent provides a rich CLI to manage the agent lifecycle. Ensure you have configured your `config.yaml` (copy from `config.example.yaml`) and `.env` files before running.

**Start the autonomous loop in Super Human Mode**:
```bash
farm_agent superhuman --target-repo <optional_owner/repo>
```

**Target a specific repository directly**:
```bash
farm_agent target https://github.com/owner/repo
```

**Run PR Patrol (Audit open pull requests)**:
```bash
farm_agent patrol
```

**Analyze a repository manually**:
```bash
farm_agent analyze https://github.com/owner/repo
```

## Contributing

We welcome contributions to Farm-Agent. Please ensure you format and test your code before submitting a Pull Request:
- **Lint and format**: `make lint`
- **Run tests**: `make test`

## License

This project is licensed under the [MIT License](LICENSE).
