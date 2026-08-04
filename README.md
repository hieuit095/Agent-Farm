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
* **Layer 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Layer 2: REAL-WORLD VALUE CHECK (Gemini-3.5-Flash):** Supreme Audit vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using DeepSeek models (e.g., `deepseek-v4-pro`) to dynamically trigger the vulnerability inside a locked-down Docker container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🤖 Terminator Mode
A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite target queue for non-stop autonomous bounty hunting.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm leverages an orchestrated pipeline of specialized AI agents built around a core set of execution loops.
* **Discovery & Analysis**: Red Team pipelines powered by Semgrep and AST scanning unearth code vulnerabilities.
* **Omniscient Context**: ChromaDB indexes codebase documentation, while the RepoMapper maps dependency graphs, grounding LLM prompts in reality.
* **Execution & Verification**: Patches and Proof-of-Concepts (PoCs) are dynamically evaluated in a secure `DockerSandbox` with complete capability isolation.
* **State Management**: A persistent SQLite (`memory.db`) database tracks PR statuses, project preferences, blacklists, API quotas, and the circular target loops.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** `>= 3.11`
* **Docker Desktop** `>= 7.1` installed and running.
* **Git** installed on the host machine.

### 1-Click Docker Launch

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

3. **Configure Settings:**
   Open the newly created `.env` file and configure your core API tokens:
   ```env
   GITHUB_TOKEN=your_github_pat_here
   OPENROUTER_API_KEY=your_openrouter_key_here
   ```

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent run
   ```

### Environment Variables

Agent-Farm requires the following environment variables (typically loaded via `.env`):

* `GITHUB_TOKEN`: Primary GitHub PAT with `repo` and workflow scopes (Required).
* `OPENROUTER_API_KEY`: API key for OpenRouter (used by Bloodhound Red Team pipeline and core LLMs).
* `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (comma-separated).
* `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated, e.g., `javascript,typescript`).
* `MINIMAX_API_KEY`: Minimax API key.
* `MINIMAX_GROUP_ID`: Minimax group ID.
* `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications.
* `TELEGRAM_CHAT_ID`: Destination chat for notification messages.
* `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for notifications.
* `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for notifications.

---

## ⚙️ Usage Reference

Agent-Farm provides a comprehensive suite of Click-based CLI utilities. Attach to the Docker container to execute commands:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository (Issue-First Pipeline)
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N]

# Run the Deterministic Circular target loop
farm_agent hunt-circular

# Run Terminator Mode: relentless 24/7 continuous execution loop without delays
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Query current PR queue, runtime statistics, and LLM allocations
farm_agent status
farm_agent stats
farm_agent models
farm_agent leaderboard

# Run with thorough, standard, or quick presets
farm_agent profile <profile_name>

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# Alumni Sync + Full Friendly Repo List
farm_agent vips
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats.

Licensed under the [MIT License](LICENSE).
