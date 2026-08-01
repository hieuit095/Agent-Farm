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

## 🔥 Key Features

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: Layer 1 Appraisal (Qwen):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: Layer 2 Supreme Audit (Gemini):** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container DockerSandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

The Agent-Farm framework operates as a closed-loop multi-agent pipeline orchestrating the entire lifecycle of open source contribution:

1. **Discovery & Reconnaissance:** Identifies high-value GitHub repositories, pulling from predefined targets (`target_repo.json`) or discovering organically.
2. **Analysis & Code Mapping:** Employs Bloodhound Red Team code scanning (ast-grep + Semgrep) coupled with an Omniscient Context Engine to deeply understand repository structures, generating module dependency graphs.
3. **Patch Generation & Validation:** Triggers isolated Proof-of-Concept generation. Valid fixes undergo Blast Radius & Regression Auditing inside DockerSandboxes.
4. **Execution & PR Management:** Coordinates PR creation via the `PRManager`, avoiding superficial contributions via the Anti-Farming Filter. `PR Patrol` monitors open PRs, interacting with maintainers and automatically attempting CI auto-fixes on failure.
5. **Continuous Loop Execution:** The `SuperHumanLoop` (Terminator Mode) acts as a relentless continuous execution loop without artificial delays, rotating through target queues securely and maintaining project intelligence in a local SQLite database (`memory.db`).

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** >= 3.11
* **Docker** >= 7.1
* **Docker Desktop** running.
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

3. **Configure Primary Settings:**
   Open the newly created `.env` file and configure your primary API tokens:
   ```env
   GITHUB_TOKEN=your_github_pat_here
   OPENROUTER_API_KEY=your_openrouter_key_here
   ```

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

### Environment Variables

The project utilizes a `.env` file to manage configuration state securely. The core environment variables required for running `farm_agent` include:

* `GITHUB_TOKEN`: Personal access token with repo, read:org, and workflow scopes. Write operations use this primary token.
* `OPENROUTER_API_KEY`: API key for OpenRouter, used by the Bloodhound Red Team pipeline to route White-Hat audit calls.
* `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation to distribute read-only API load.
* `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated, e.g., `javascript,typescript`).
* `MINIMAX_API_KEY`: Minimax API key.
* `MINIMAX_GROUP_ID`: Minimax group ID.
* `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications (merge, close, run complete).
* `TELEGRAM_CHAT_ID`: Telegram chat ID.
* `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for push notifications.
* `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for push notifications.

---

## ⚙️ Usage Reference

Agent-Farm provides a comprehensive suite of CLI utilities accessible via the `farm_agent` command:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Hunt Mode
farm_agent hunt-circular

# Run the Relentless 24/7 Super Human loop (Terminator Mode)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Alumni Sync + Full Friendly Repo List
farm_agent vips

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

# Manage PR templates
farm_agent templates

# View or edit configuration
farm_agent config

# Send a test notification to configured channels
farm_agent notify-test

# Show Farm-Agent system status
farm_agent system-status

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
