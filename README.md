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

---

## 🏗️ System Architecture (High-Level)

The Agent-Farm application is orchestrated around a robust pipeline and agent-based design paradigm:

- **Target Acquisition:** Iteratively fetches and analyzes repos from GitHub, extracting critical constraints and style guidelines, while applying blacklists for previously evaluated incompatible targets.
- **Vulnerability Hunting:** Employs abstract syntax trees (AST) and DeepSeek intelligence coupled with ChromaDB context mapping to find issues. Findings are aggressively gated by an Anti-Farming Filter using the Qwen model.
- **Dynamic Exploitation & Sandboxing:** Validates flaws using a generated Proof-of-Concept, executed securely inside Docker network-isolated sandboxes.
- **Patch Synthesis & Dev-QA Loops:** Fixes are generated, dynamically tested, and peer-reviewed by an AI self-evaluator. Multiple QA feedback loops ensure flawless patches.
- **End-to-End Orchestration:** The `Terminator Mode` relentless loop (`SuperHumanLoop`) drives the system continuously. `PR Patrol` automatically fixes CI failures and handles maintainer comments using Gemini-3.5-flash context.
- **Persistence:** A state-of-the-art WAL mode SQLite database (`memory.db`) strictly logs pipelines, findings, cache, logs, limits, quotas, blacklisted repos, and GitHub network preferences.

---

## 🛠️ Getting Started (1-Click Launch)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** (>= 3.11)
* **Docker Desktop** (>= 7.1) installed and running.
* **Git** installed on the host machine.
* A GitHub Personal Access Token (PAT) with `repo` scope.
* Required APIs.

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

3. **Configure Settings (`.env` Variables Required):**
   Open the newly created `.env` file and configure your API tokens (never commit this file):
   * `GITHUB_TOKEN`: Your GitHub PAT.
   * `GITHUB_SECONDARY_TOKENS`: (Optional) Additional tokens for read-only rate-limit distribution.
   * `EXCLUDED_LANGUAGES`: (Optional) Comma-separated languages to bypass.
   * `MINIMAX_API_KEY`: Minimax API Key (Required when provider is "minimax").
   * `MINIMAX_GROUP_ID`: Minimax Group ID (Required by some Minimax plans).
   * `OPENROUTER_API_KEY`: OpenRouter API Key.
   * `TELEGRAM_BOT_TOKEN`: (Optional) Telegram integration bot token.
   * `TELEGRAM_CHAT_ID`: (Optional) Telegram integration chat ID.
   * `SLACK_WEBHOOK_URL`: (Optional) Slack push notification webhook URL.
   * `DISCORD_WEBHOOK_URL`: (Optional) Discord push notification webhook URL.

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ CLI Command Reference

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt

# Run in Hunt Circular Mode: target multiple repositories loaded from a JSON configuration
farm_agent hunt-circular

# Run the Relentless 24/7 Terminator Mode (patrols PRs and hunts targets)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Analyze a repository to evaluate vulnerabilities and generate findings cache
farm_agent analyze <repo_url>

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Check current project execution status and filter by state
farm_agent status

# Show Farm-Agent system status — memory, PRs, rate limits
farm_agent system-status

# Query runtime statistics, and API LLM allocations
farm_agent stats

# Display the global PR Contribution leaderboard
farm_agent leaderboard

# List available models and their capabilities
farm_agent models

# Run with thorough, standard, or quick presets
farm_agent profile <profile_name>

# Check current configuration details
farm_agent config

# Display Alumni Sync + Full Friendly Repo List
farm_agent vips

# List available contribution templates
farm_agent templates

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# Send a test notification to configured channels
farm_agent notify-test

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
