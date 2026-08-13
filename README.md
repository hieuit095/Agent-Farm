# Agent-Farm

![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Docker](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Agent-Farm is an autonomous system that automatically contributes to open source projects on GitHub. It discovers repositories, analyzes them for improvements (security, code quality, UI/UX), generates fixes via multiple LLMs, validates changes in an isolated Docker sandbox, and submits pull requests entirely autonomously.

## Key Features

* **Omniscient Context Engine (RAG):** Deeply understands codebases by extracting dependencies, discovering subsystem documentation, and utilizing semantic header-based chunking for accurate LLM context generation.
* **Multi-Layer Validation (Dynamic Bug Verification):** Patches are generated and tested automatically using isolated PoC (Proof of Concept) execution in a `DockerSandbox`.
* **Bloodhound Red Team (Semgrep & AST):** Static analysis utilizing AST parsing and semantic searches for pinpoint issue discovery.
* **Anti-Farming Filter:** Prevents low-quality contributions by enforcing strict semantic value checks before generating patches.
* **Terminator Mode:** A relentless, deterministic execution loop driving continuous discovery, analysis, generation, and PR creation.
* **Multi-LLM Routing:** Leverages different LLM models optimized for specific tasks, utilizing DeepSeek for coding, Qwen for QA scoring, and Gemini for supreme code audits.
* **Blast Radius & Regression Auditing:** Analyzes how proposed fixes impact the wider codebase structure.

## System Architecture (High-Level)

The Agent-Farm orchestrates an autonomous loop combining static analysis, LLM generation, and dynamic validation. The `FarmAgentPipeline` reads targets from a deterministic circular queue, passing them to the `CodeAnalyzer` which leverages AST, `Semgrep`, and `ChromaDB` (RAG) to find issues. Detected vulnerabilities or bugs are routed to a `ContributionGenerator` which proposes patches via multi-model LLMs. Finally, a `ReviewerAgent` performs Blast Radius analysis, and a local `DockerSandbox` compiles/tests the proposed changes. Only validated, high-quality fixes are submitted to GitHub via the `PRManager`, logging states in a comprehensive SQLite `Memory` schema.

## Getting Started

### Prerequisites

* **Python:** >= 3.11
* **Docker:** >= 7.1

### 1-Click Docker Quick-Start

Agent-Farm is best executed via its pre-configured Docker Desktop setup which automatically handles the dependency environment and isolated test networks (`internet_access` & `sandbox_isolated`).

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env and insert your API keys and configuration (see below)
   ```

3. **Start the Agent (Unix/Mac):**
   ```bash
   ./start.sh
   ```
   *(For Windows, use `start.bat`)*

### Environment Variables

You **must** configure the following environment variables in your `.env` file before launching:

* `GITHUB_TOKEN`: Primary Personal Access Token (PAT) for GitHub interactions (requires `repo`, `read:org`, and `workflow` scopes).
* `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated list of fallback GitHub PATs used for GET rate-limit rotation.
* `OPENROUTER_API_KEY`: API key for accessing LLMs via OpenRouter (e.g. deepseek, qwen, gemini).
* `MINIMAX_API_KEY`: Fallback API key used if OpenRouter fails.
* `MINIMAX_GROUP_ID`: Minimax plan group ID.
* `EXCLUDED_LANGUAGES`: Comma-separated list of languages to ignore (e.g., `javascript,typescript`).
* `TELEGRAM_BOT_TOKEN`: (Optional) Telegram bot token for push notifications.
* `TELEGRAM_CHAT_ID`: (Optional) Telegram destination chat ID for notifications.
* `SLACK_WEBHOOK_URL`: (Optional) Slack incoming webhook URL for notifications.
* `DISCORD_WEBHOOK_URL`: (Optional) Discord incoming webhook URL for notifications.

## Usage

Once the Docker container is running, you can connect to the CLI and execute agent operations:

**Run Terminator Mode (Relentless continuous loop):**
```bash
docker exec -it agent-farm farm_agent superhuman
```

**Check System Status:**
```bash
docker exec -it agent-farm farm_agent system-status
```

**View Leaderboard & Stats:**
```bash
docker exec -it agent-farm farm_agent leaderboard
```

**List Available Models:**
```bash
docker exec -it agent-farm farm_agent models
```

**View Logs:**
```bash
docker compose logs -f
```

## Contributing & License

Contributions are welcome! Please ensure you verify your frontend changes and adhere to the project formatting and linting rules.

This project is licensed under the MIT License - see the LICENSE file for details.
