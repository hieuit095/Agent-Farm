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

* **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
* **Anti-Farming Filter:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
  * **Layer 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
  * **Layer 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.
* **Dynamic Bug Verification (PoC Execution):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check:
  * **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
  * **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.
* **Issue-First Pipeline:** Proactively searches for solvable issues in a repo, constructs deep fixes, and generates PRs.
* **PR Patrol:** Checks open PRs for maintainer review comments, replies to questions, and auto-fixes CI failures.
* **Terminator Mode:** A relentless continuous execution loop without artificial delays, pulling targets exclusively from the deterministic SQLite queue.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm relies on a sophisticated orchestrator bridging LLM capabilities with rigorous dynamic execution:
1. **Target Discovery & Cloning:** Analyzes and selects targets, cloning them locally.
2. **Contextual Analysis:** Combines AST-based dependency mapping with vector-stored documentation (ChromaDB) to arm LLM agents with complete subsystem understanding.
3. **Execution & Validation (Sandbox):** Generates and runs a Proof-of-Concept in a secure, isolated Docker container to confirm vulnerabilities exist. If validated, the pipeline drafts a patch and runs the test suite to prevent regressions.
4. **Appraisal Gates:** Filters all patches through strict model evaluations (DeepSeek, Qwen, Gemini) to reject trivial or invalid changes.
5. **Contribution Management:** Patches that survive the gauntlet are automatically submitted via Pull Request or packaged for private security disclosure, persisting state and logs in a local SQLite database (`memory.db`).

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker Engine** (>= 7.1) running.
* **Git** installed on the host machine.
* **Python** (>= 3.11) installed.
* A GitHub Personal Access Token (PAT) with `repo` scope.

### Environment Variables (.env)

The pipeline requires specific `.env` variables to function correctly. Copy `.env.example` to `.env` and fill in:

| Variable | Requirement | Description |
|---|---|---|
| `GITHUB_TOKEN` | **Required** | Personal Access Token with repo scope for creating PRs and issues. |
| `OPENROUTER_API_KEY` | **Required** | Core LLM routing API key used for primary deepseek/qwen/gemini calls. |
| `GITHUB_SECONDARY_TOKENS` | Optional | Comma-separated tokens to distribute read-only API load. |
| `EXCLUDED_LANGUAGES` | Optional | Comma-separated list (e.g., `javascript,typescript`) to save LLM budget. |
| `TELEGRAM_BOT_TOKEN` | Optional | For Telegram push notifications (merge, close, run complete). |
| `TELEGRAM_CHAT_ID` | Optional | The destination chat ID for Telegram notifications. |
| `SLACK_WEBHOOK_URL` | Optional | For Slack push notifications. |
| `DISCORD_WEBHOOK_URL` | Optional | For Discord push notifications. |
| `MINIMAX_API_KEY` | Optional | For secondary LLM routing via Minimax (not required if using OpenRouter). |
| `MINIMAX_GROUP_ID` | Optional | Used alongside MINIMAX_API_KEY. |

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

3. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage & CLI Command Reference

Agent-Farm provides a comprehensive suite of CLI utilities accessible via the `farm_agent` executable:

### Core Pipelines
```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Run deterministic round-robin target loop from target queue
farm_agent hunt-circular

# Run Terminator Mode: relentless continuous execution loop, pulling targets from SQLite
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol
```

### System Management & Utilities
```bash
# Perform code analysis pass only; do not generate contributions
farm_agent analyze <repo_url>

# Clean up local temporary files and stale forks
farm_agent cleanup

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries older than 90 days
farm_agent gc --days 90

# Monitor and synchronize VIP repository radar list (Alumni Sync + Full Friendly Repo List)
farm_agent vips
```

### Insights & Profiling
```bash
# Query current PR queue, runtime statistics, and LLM allocations
farm_agent status
farm_agent stats

# Show comprehensive Farm-Agent system status (memory, PRs, rate limits)
farm_agent system-status

# Show leaderboards of merged and submitted contributions
farm_agent leaderboard

# Output the current loaded runtime settings
farm_agent config

# Display formatting templates for PR descriptions
farm_agent templates

# Run the pipeline pre-loaded with quick, standard, or thorough presets
farm_agent profile <profile_name>

# List available models and their capability mappings
farm_agent models

# Send a test notification to configured channels
farm_agent notify-test
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
