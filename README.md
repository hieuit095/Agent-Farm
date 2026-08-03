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
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a strict filter system:
* **Layer 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Layer 2: SUPREME AUDIT (Gemini-3.5-Flash):** Ensures real-world value, vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` (via OpenRouter) to dynamically trigger the vulnerability inside a locked-down container sandbox (`DockerSandbox`). If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🤖 Terminator Mode
A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite `target_repos` table, constantly patrolling PRs and hunting for new targets.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm orchestrates an autonomous, multi-agent pipeline targeting GitHub repositories:

1. **Discovery & Recon:** Gathers repos based on criteria, avoiding excluded languages. Maps the codebase via the Omniscient Context Engine (AST parsing, RAG on docs).
2. **Analysis & Triage (Bloodhound Red Team):** Analyzes the code utilizing static analysis (ast-grep, Semgrep) and identifies potential flaws, passing them through the Anti-Farming Filter.
3. **PoC & Validation:** Constructs a PoC and executes it dynamically in a `DockerSandbox`.
4. **DEV-QA Bounty Loop:** Generates a code patch, validates the fix against the PoC, and ensures no regressions via the test suite (Blast Radius Auditing).
5. **PR Submission & Patrol:** Submits the validated patch via PR, and uses PR Patrol to monitor maintainer feedback, actively responding and automatically fixing CI issues.

---

## 🛠️ Getting Started

### Prerequisites

* **Python:** >= 3.11
* **Docker:** >= 7.1 (Docker Desktop recommended for local isolated sandboxes)
* **Git:** Installed on the host machine.

### Environment Variables

The system relies on a `.env` file (copied from `.env.example`). The core required and optional variables are:

| Variable | Description | Requirement |
|----------|-------------|-------------|
| `GITHUB_TOKEN` | Primary GitHub PAT with `repo`, `read:org`, and `workflow` scopes. | **Required** |
| `MINIMAX_API_KEY` | Minimax API key for the default LLM provider. | **Required** (if using Minimax) |
| `OPENROUTER_API_KEY` | OpenRouter API key for DeepSeek/General models. | **Required** |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for push notifications. | Optional |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications. | Optional |
| `SLACK_WEBHOOK_URL` | Slack webhook URL for notifications. | Optional |
| `DISCORD_WEBHOOK_URL`| Discord webhook URL for notifications. | Optional |
| `EXCLUDED_LANGUAGES` | Comma-separated languages to ignore (e.g., `javascript,typescript`). | Optional |
| `GITHUB_SECONDARY_TOKENS` | Comma-separated GitHub PATs for read-only API rotation. | Optional |
| `MINIMAX_GROUP_ID` | Group ID required by some Minimax plans. | Optional |

### 1-Click Installation (Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

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
   * *Note: The script will automatically pull the latest codebase, initialize your `.env` configuration file from `.env.example`, build the Docker image, and launch the daemon in the background.*

3. **Configure Settings:**
   Open the newly created `.env` file and configure your essential API tokens.

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage (CLI Commands)

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: agressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop
farm_agent hunt-circular

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Run the Relentless 24/7 Terminator Mode loop
farm_agent superhuman

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

# Manage config or view alumni/friends
farm_agent config
farm_agent vips

# Test notification channels
farm_agent notify-test

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90
```

*(Note: The legacy `janitor` command has been fully deprecated and removed.)*

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites (e.g. `make test`).

Licensed under the [MIT License](LICENSE).
