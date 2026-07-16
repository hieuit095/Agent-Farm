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
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm orchestrates an autonomous pipeline by discovering repositories, scanning for issues, and executing fixes in an isolated environment.

1. **Discovery & Auditing**: Utilizing the Bloodhound Red Team model (AST-grep + Semgrep), targets are scanned for real vulnerabilities. Trivial issues are filtered via the Anti-Farming Filter.
2. **Context Engine Mapping**: The codebase is indexed using ChromaDB, enabling semantic understanding of documentation and modular dependencies.
3. **Execution Sandbox**: Validates patches using Docker to prevent side effects, ensuring patches run flawlessly via dual efficacy and regression passes.
4. **Contribution Mechanism**: Once changes pass the rigorous Layer 2 Supreme Audit by Gemini, PRs or issue comments are created via the PR Manager.

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** >= 3.11
* **Docker** >= 7.1
* **Docker Desktop** installed and running.
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

3. **Configure Environment Variables (`.env`):**
   Open the newly created `.env` file and configure your settings. Required and core environment variables:
   * `GITHUB_TOKEN`: (Required) Your GitHub personal access token with repo, read:org, and workflow scopes.
   * `OPENROUTER_API_KEY`: API key for general task models via OpenRouter (e.g., Bloodhound audits).
   * `MINIMAX_API_KEY`: API key for Minimax models.
   * `TELEGRAM_BOT_TOKEN`: (Optional) Bot token for notifications.
   * `TELEGRAM_CHAT_ID`: (Optional) Chat ID for notifications.
   * `SLACK_WEBHOOK_URL`: (Optional) Webhook URL for Slack alerts.
   * `DISCORD_WEBHOOK_URL`: (Optional) Webhook URL for Discord alerts.
   * `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated).
   * `GITHUB_SECONDARY_TOKENS`: Additional tokens for read-only API load distribution.
   * `MINIMAX_GROUP_ID`: Sent as X-Minimax-Group-Id header.

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage & CLI Commands

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Run the Relentless Circular Target Loop from SQLite target_repos
farm_agent hunt-circular

# Run the Relentless 24/7 Terminator loop (patrols PRs and hunts targets)
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
farm_agent system-status

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

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
