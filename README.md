# Agent-Farm

![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)
![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Docker Version](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

**Agent-Farm** is an autonomous system that automatically contributes to open source projects on GitHub. It discovers repositories, analyzes them for vulnerabilities or issues, generates contributions (fixes or features), verifies them dynamically, and submits high-quality Pull Requests autonomously.

## Key Features

- **Autonomous Contribution Flow:** End-to-end orchestration (`discover → analyze → generate → PR`).
- **Terminator Mode:** A relentless, continuous execution loop pulling targets from the internal SQLite database (`target_repos`), enabling high-throughput operations without artificial delays.
- **Issue-First Pipeline:** Strategically prioritizes discovering and resolving explicit repository issues over arbitrary code changes.
- **Multi-Model LLM Routing:** Utilizes DeepSeek (e.g., deepseek-v4-pro) via OpenRouter for general tasks, Qwen (e.g., qwen3.7-max) for Layer 1 Appraisal, and Gemini (e.g., gemini-3.5-flash) for Layer 2 Supreme Audit.
- **Dynamic Bug Verification:** Executes isolated proof-of-concept tests within a `DockerSandbox` to verify bugs and validate patches before submission.
- **Local RAG (Retrieval-Augmented Generation):** Leverages ChromaDB for contextually precise fixes by mapping the codebase architecture.
- **Security Disclosure Gate:** Automatically scans repository meta-files to detect private disclosure requirements and aborts the pipeline to prevent irresponsible public PRs.

## System Architecture (High-Level)

The system operates on a custom registry-based agent architecture known as the **DeerFlow pattern**. The main orchestrator (`FarmAgentPipeline`) coordinates several subsystems:
1. **GitHubClient:** Handles repository discovery, cloning, and API interactions.
2. **CodeAnalyzer & Bloodhound Red Team:** Scans the codebase using AST parsing and semantic grep to identify vulnerabilities and context.
3. **ContributionGenerator:** Uses routed LLMs and RAG context to formulate code changes and draft patches.
4. **PRManager & PR Patrol:** Manages the PR submission process, enforcing strict 'AI Gag Orders' and Anti-Farming Filters to ensure contributions are substantial and indistinguishable from expert human engineers.
5. **Memory:** Maintains persistent state (e.g., analyzed repos, submitted PRs) using SQLite.

## Getting Started

### Prerequisites

- **Python:** `>=3.11`
- **Docker:** `>=7.1` (Required for sandboxed execution and the `DockerSandbox`)

### Installation

To set up the development environment locally:

```bash
# Clone the repository
git clone https://github.com/hieuit095/Agent-Farm.git
cd Agent-Farm

# Install the package and its development dependencies
make install
```

Alternatively, you can use the 1-Click Docker Desktop Quick-Start:

```bash
chmod +x start.sh
./start.sh
```

### Environment Variables

Agent-Farm requires specific environment variables to function correctly. Copy `.env.example` to `.env` and fill in your values.

```bash
cp .env.example .env
```

**Required Variables:**
- `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires `repo`, `read:org`, and `workflow` scopes).
- `MINIMAX_API_KEY`: Required if using Minimax as the default provider.

**Optional Variables:**
- `GITHUB_SECONDARY_TOKENS`: Comma-separated tokens for GET request rotation.
- `EXCLUDED_LANGUAGES`: E.g., `javascript,typescript` to save LLM budget.
- `OPENROUTER_API_KEY`: For routing the Bloodhound Red Team audits.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: For pipeline push notifications.
- `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`: Additional notification channels.

## Usage

Agent-Farm provides a rich command-line interface via `click` and `rich`.

```bash
# Auto-discover repos and contribute
farm_agent run

# Target a specific repository
farm_agent target <url>

# Analyze a repository without contributing
farm_agent analyze <url>

# Solve issues in a specific repository
farm_agent solve <url>

# Run Terminator Mode (relentless continuous execution)
farm_agent superhuman

# Show status of submitted PRs
farm_agent status

# Show overall statistics
farm_agent stats

# Show current configuration
farm_agent config
```

If running via Docker:
```bash
docker exec -it agent-farm farm_agent superhuman
```

## Contributing

Contributions are welcome! Please ensure you run the test suite and code formatters before submitting a pull request.

```bash
# Run tests with coverage
make test

# Lint and format code
make lint
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
