# 🛠️ Agent-Farm (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features (v4.0.0 Upgrades)

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🤖 Terminator Mode
A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite target_repos table.

---

## 🏗️ System Architecture (High-Level)

The `FarmAgentPipeline` orchestrator coordinates the main execution flow, supported by several core modules:
1. **GitHubClient & Discovery**: Searches GitHub networks for target repositories or takes explicit target URLs.
2. **CodeAnalyzer**: Scans codebase leveraging the Bloodhound Red Team (ast-grep + Semgrep) for vulnerabilities, bugs, and issues.
3. **Omniscient Context Engine**: Uses RAG (ChromaDB) to construct context from project docs and AST-based module dependency graphs.
4. **ContributionGenerator**: Drafts patches and fixes using DeepSeek models via OpenRouter.
5. **DockerSandbox Engine**: Dynamically verifies bugs with PoCs and ensures patches are regression-free by running the project's native test suite.
6. **PRManager**: Commits the verified patches, handles branch management, and submits pull requests.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker Desktop** >= 7.1 installed and running.
* **Python** >= 3.11
* **Git** installed on the host machine.

### 1-Click Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   * **Windows:** Double-click `start.bat` or run:
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   * *Note: The script will automatically pull the latest codebase, initialize your `.env` configuration file from `.env.example` if missing, build the Docker image, and launch the daemon in the background.*

### Environment Variables

You must configure the following core environment variables in your `.env` file to run the project.

**Required:**
* `GITHUB_TOKEN`: Personal access token with repo, read:org, and workflow scopes.
* `MINIMAX_API_KEY`: API key for Minimax (default LLM provider if OpenRouter is not used).

**Optional / Advanced:**
* `OPENROUTER_API_KEY`: API key for OpenRouter, used by the pipeline to route calls.
* `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications (merge, close, run complete).
* `TELEGRAM_CHAT_ID`: Telegram chat ID for the destination of notification messages.
* `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for push notifications.
* `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for push notifications.
* `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated, e.g., `javascript,typescript`).
* `GITHUB_SECONDARY_TOKENS`: Additional GitHub tokens for GET request rotation (comma-separated).
* `MINIMAX_GROUP_ID`: Minimax group ID (sent as X-Minimax-Group-Id header).

---

## ⚙️ Usage (CLI Commands)

Agent-Farm provides a comprehensive suite of Click-based CLI utilities. Access them inside the Docker container:

```bash
# Attach to the Agent CLI
docker exec -it agent-farm bash
```

**Core Commands:**
```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N]

# Run the Circular Hunt Mode
farm_agent hunt-circular

# Run Terminator Mode: relentless continuous execution loop
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# View PR queue, runtime statistics, and memory database overview
farm_agent system-status
farm_agent stats

# Display contribution leaderboard and success rates
farm_agent leaderboard

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# View available models and their capabilities
farm_agent models

# Other utilities
farm_agent config
farm_agent vips
farm_agent templates
farm_agent profile <profile_name>
farm_agent notify-test
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
