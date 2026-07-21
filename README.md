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
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). The system proactively intercepts and discards low-impact findings that resemble spam/exploratory PRs before any generation happens.

### 🛡️ Layer 1 & Layer 2 Gatekeepers
Implements a strict two-layer filter system to weed out hallucinations and regressions:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: SUPREME AUDIT (Gemini-3.5-Flash):** Final gatekeeper that audits the entire incident dossier (root cause, patch, and sandbox logs) before a PR is deployed to production.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🕵️ Bloodhound Red Team
Pre-scan capability using `ast-grep` and `Semgrep` to quickly identify potential vulnerabilities, saving expensive LLM analysis by pre-filtering out fully clean files.

### 🔄 Circular Target Loop
Deterministic round-robin operation reading from a persistent `target_repos` SQLite table, ensuring crash-safe rotation of targeted repositories.

### 💰 DEV-QA Bounty Loop
A 3-cycle generator mechanism where the DEV agent generates patches and auto-injects context from failures, while the QA Hardcore Scorer evaluates the patch against repository style guides and QA lessons before approving.

### 🤖 Terminator Mode
A relentless continuous execution loop (`farm_agent superhuman`) that runs database-driven `hunt-circular` and `patrol` operations without artificial human delays, leveraging token pool rotation to avoid rate limits.

---

## 🏗️ System Architecture (High-Level)

The Agent-Farm orchestrator coordinates multiple subsystems:
1. **Discovery & Targeting:** Acquires repos either sequentially (`target_repo.json` / Circular Loop) or adaptively (`hunt`). Filters against interaction limits and AI-bans.
2. **Analysis & Indexing:** RAG extracts context and builds an AST-based module dependency graph. `BloodhoundAnalyzer` flags initial issues.
3. **Generation & Verification:** Multi-cycle DEV-QA generation loop using DeepSeek. The resulting patches face the DockerSandbox guillotine (PoC efficacy + native test regression).
4. **Audit & Submission:** Layer 2 Gemini audit verifies the logs. PRManager creates and tracks the PR on GitHub, while PRPatrol monitors open PRs to auto-reply to maintainer comments and fix CI failures.
5. **Memory:** Persistent SQLite backing store tracks AI API usage, repo preferences, submitted PRs, task scheduling, and learned QA lessons.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python:** >= 3.11
* **Docker:** >= 7.1 (Docker Desktop recommended)
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

Agent-Farm requires the following environment variables (defined in your `.env` file):

**Required:**
* `GITHUB_TOKEN`: Personal access token with repo, read:org, and workflow scopes.
* `MINIMAX_API_KEY`: API key for Minimax (if using Minimax provider).
* `OPENROUTER_API_KEY`: API key for OpenRouter (used by Bloodhound Red Team, Qwen, Gemini).

**Optional / Advanced:**
* `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (comma-separated).
* `EXCLUDED_LANGUAGES`: Comma-separated languages to filter out (e.g., `javascript,typescript`).
* `MINIMAX_GROUP_ID`: Sent as X-Minimax-Group-Id header.
* `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications.
* `TELEGRAM_CHAT_ID`: Destination chat for notification messages.
* `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for notifications.
* `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for notifications.

---

## ⚙️ Usage / CLI Commands

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

# Run the Relentless 24/7 Super Human loop (patrols PRs and hunts targets)
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

# Show current VIP Alumni Repositories
farm_agent vips

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
