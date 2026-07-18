# Agent-Farm

![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Docker Version](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Agent-Farm is an autonomous system that automatically contributes to open-source projects on GitHub. It discovers repositories, deeply analyzes codebases using static analysis and RAG mapping, and orchestrates an AI-driven multi-agent pipeline to generate, verify, and submit high-quality pull requests.

## Key Features

- **Omniscient Context Engine**: Deep codebase mapping via RAG (ChromaDB) and semantic markdown header chunking to provide complete repository context.
- **Dynamic Bug Verification**: Isolated Proof-of-Concept (PoC) execution within a `DockerSandbox` using a Polyglot Guillotine for secure, verifiable patching.
- **Blast Radius & Regression Auditing**: Self-reflective reviewer agents thoroughly verify patches locally, ensuring no regressions are introduced before submission.
- **Bloodhound Red Team**: Automated vulnerability scanning utilizing AST-grep and Semgrep integration during the analysis phase.
- **Issue-First Pipeline & PR Patrol**: Drafts targeted fixes for open GitHub issues and autonomously manages PR discussions, applying CI fixes on the fly.
- **Terminator Mode**: A relentless, continuous execution loop (`SuperHumanLoop`) that hunts for tasks across a deterministic circular target queue.
- **Anti-Farming Filter**: A strict evaluation gate blocking trivial, garbage, or documentation-only PRs to ensure strictly high-quality, substantive contributions.
- **Token Pool Rotation**: Gracefully rotates between multiple GitHub secondary tokens to avoid rate limits during heavy read operations.

## System Architecture (High-Level)

Agent-Farm orchestrates an end-to-end contribution pipeline through several key phases:
1. **Discovery & Reconnaissance**: Explores GitHub for target repositories based on specific parameters (language, stars) and crawls their files.
2. **Analysis & RAG Context**: The Omniscient Context Engine chunks and indexes documentation into ChromaDB, while the RepoMapper constructs AST-based dependency graphs.
3. **Generation & QA**: Utilizes a Multi-Agent architecture. DeepSeek models (e.g., deepseek-v4-pro via OpenRouter) handle general pipeline tasks, Qwen models (e.g., qwen3.7-max) perform Layer 1 Appraisal, and Gemini models (e.g., gemini-3.5-flash) execute Layer 2 Supreme Audit.
4. **Validation (DockerSandbox)**: Proposed fixes are executed and verified in an isolated internal Docker network to ensure safety and correctness.
5. **Submission & Patrol**: Approved changes are committed and pushed. The PR Patrol subsystem monitors maintainer feedback and addresses CI failures autonomously.

## Getting Started

### Prerequisites
- **Docker**: >= 7.1 (Required for 1-Click Launch and Sandbox execution)
- **Git**: For cloning the repository

### Installation

We recommend the 1-Click Docker Launch for a quick and isolated setup:

```bash
# Clone the repository
git clone https://github.com/hieuit095/Agent-Farm.git
cd Agent-Farm

# Copy the example environment configuration
cp .env.example .env

# Run the quick-start script for your OS
# For Unix/Linux/macOS:
./start.sh

# For Windows:
start.bat
```

### Environment Variables

Configure the `.env` file in the root directory before starting. The following environment variables are required or highly recommended:

- `GITHUB_TOKEN`: Primary GitHub Personal Access Token (Requires `repo`, `read:org`, and `workflow` scopes).
- `OPENROUTER_API_KEY`: Core API key for OpenRouter, used to route general tasks to LLM models.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of fallback tokens to distribute read-only GitHub API load.
- `EXCLUDED_LANGUAGES`: Comma-separated list of verbose or costly languages to ignore (e.g., `javascript,typescript`).
- `TELEGRAM_BOT_TOKEN`: (Optional) Token for Telegram push notifications (merge, close, run complete).
- `TELEGRAM_CHAT_ID`: (Optional) Destination chat ID for Telegram alerts.
- `SLACK_WEBHOOK_URL`: (Optional) Incoming webhook URL for Slack notifications.
- `DISCORD_WEBHOOK_URL`: (Optional) Incoming webhook URL for Discord notifications.

## Usage

Agent-Farm is primarily operated via its CLI (`farm_agent`). When running via Docker, you can execute commands directly on the running container:

```bash
# Run a standard contribution loop targeting Python repositories
docker exec -it agent-farm farm_agent run --language python --stars 500 --max-prs 5

# Enter Terminator Mode for continuous autonomous execution
docker exec -it agent-farm farm_agent superhuman --target-repo target_repo.json

# Analyze a specific repository URL
docker exec -it agent-farm farm_agent analyze https://github.com/example/repo

# Resolve specific issues in a repository
docker exec -it agent-farm farm_agent solve https://github.com/example/repo --max-issues 3

# View Leaderboard Statistics
docker exec -it agent-farm farm_agent leaderboard --limit 10

# View Alumni Sync & VIP Roster
docker exec -it agent-farm farm_agent vips
```

## Contributing

Contributions to Agent-Farm are welcome! Please ensure you have the proper development environment set up (`make install`) and that your code passes all linting (`make lint`) and testing (`make test`) checks before submitting a PR.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
