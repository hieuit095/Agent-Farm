# 🛠️ Agent-Farm

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

### 🧠 Omniscient Context Engine
Codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements strict filters:
* **Gate 1: EXPERT APPRAISAL:** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm runs via a sophisticated orchestrator, `FarmAgentPipeline`, integrating the following core components:
1. **GitHubClient & Discovery**: Locates repositories and fetches code.
2. **CodeAnalyzer**: Leverages Bloodhound Red Team logic (ast-grep + Semgrep patterns) to find vulnerabilities and code smells.
3. **ContributionGenerator**: Drafts patches and PoCs to exploit and fix the problem.
4. **Sandbox Verification**: The Docker Sandbox engine runs the PoC and test suites to verify fix efficacy and prevent regressions.
5. **PRManager**: Submits validated PRs or notifies maintainers privately via alerts.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker Desktop** (version >= 7.1) installed and running.
* **Python** (version >= 3.11) installed on the host machine.
* A GitHub Personal Access Token (PAT) with `repo` scope.
* Relevant LLM API keys (e.g., OpenRouter, Minimax).

### 1-Click Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   * **Windows:**
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

Configure the `.env` file generated with the following keys:

* **Core Authentication:**
  * `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT).
  * `GITHUB_SECONDARY_TOKENS`: Additional tokens to distribute read-only API load (comma-separated).
* **LLM Providers:**
  * `OPENROUTER_API_KEY`: OpenRouter API key for general task routing (e.g., DeepSeek models).
  * `MINIMAX_API_KEY`: Minimax API key used as the default fallback.
  * `MINIMAX_GROUP_ID`: Minimax group ID for specific plans.
* **Pipeline Configuration:**
  * `EXCLUDED_LANGUAGES`: Filter out languages (comma-separated, e.g., `javascript,typescript`).
* **Notifications (Optional):**
  * `TELEGRAM_BOT_TOKEN`: Token for Telegram bot notifications.
  * `TELEGRAM_CHAT_ID`: Destination chat ID for Telegram.
  * `SLACK_WEBHOOK_URL`: Slack incoming webhook URL.
  * `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL.

---

## ⚙️ Usage & CLI Reference

Attach to the running Docker instance to use the CLI:
```bash
docker exec -it agent-farm farm_agent <command>
```

**Core Commands:**
* `farm_agent run` - Start the full automated discovery, analysis, and contribution pipeline.
* `farm_agent superhuman` - Run Terminator Mode: a relentless 24/7 continuous execution loop without artificial delays, pulling targets exclusively from the target queue.
* `farm_agent patrol` - Check open PRs for maintainer comments, answer queries, and push CI auto-fixes.
* `farm_agent target <repo_url>` - Target a specific repository directly.
* `farm_agent solve <repo_url>` - Solve open issues in a specific repository.
* `farm_agent hunt` - Aggressively discover repos and solve issues/bugs.
* `farm_agent vips` - Alumni Sync + Full Friendly Repo List.
* `farm_agent status` - Check the current system status and pipeline queue.
* `farm_agent models` - View available models and capabilities.
* `farm_agent profile <profile_name>` - Run with configured presets.
* `farm_agent leaderboard` - View contribution statistics and rankings.
* `farm_agent reset-db` - Clear run logs and start with a fresh state.

*(Note: The `janitor` command has been deprecated and should not be used.)*

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
