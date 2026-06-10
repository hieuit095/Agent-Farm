# 🛠️ Agent-Farm (v4.0.0)

**Autonomous system that automatically contributes to open source projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm (package name `farm_agent`) is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using local Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs to inject precise module dependency linkages directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs. The pipeline strictly blocks trivial PRs using a two-layer filter system (Layer 1 Appraisal with Qwen models and Layer 2 Supreme Audit with Gemini models) to filter out false positives and theoretical edge cases.

### 🧪 Dynamic Bug Verification
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down Docker container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check: applies the patch and re-runs the PoC to ensure efficacy, and executes the project's native test suite to ensure the patch does not break any existing functionality.

---

## 🏗️ System Architecture (High-Level)

The architecture follows the custom **DeerFlow** pattern (registry-based agent architecture). It relies on multiple LLMs via OpenRouter:
- **Code Gen:** `deepseek/deepseek-v4-pro`
- **Layer 1 Appraiser:** `qwen/qwen3.7-max`
- **Layer 2 Supreme Auditor:** `google/gemini-3.5-flash`

The agent utilizes a SQLite database (in persistent memory via `aiosqlite`) to maintain state (such as analyzed repos, submitted PRs, target queues). Core orchestration happens via `farm_agent/orchestrator/pipeline.py`, routing work through Bloodhound security scanning (ast-grep + Semgrep), solving issues proactively, and creating/managing Pull Requests.

---

## 🛠️ Getting Started

### Prerequisites
* **Python** 3.11+
* **Docker Desktop** installed and running (for Sandbox execution).
* **Git** installed on the host machine.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **Setup Virtual Environment & Install:**
   ```bash
   make install
   # Or manually:
   # python3 -m venv venv
   # source venv/bin/activate
   # pip install -e '.[dev]'
   ```

3. **1-Click Docker Launch:**
   * **Windows:** `start.bat`
   * **Unix (Linux/macOS):** `./start.sh`

### Environment Variables

Copy `.env.example` to `.env` and configure:
```env
GITHUB_TOKEN=your_github_pat_here
MINIMAX_API_KEY=your_minimax_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
TELEGRAM_BOT_TOKEN=optional_telegram_token
TELEGRAM_CHAT_ID=optional_chat_id
SLACK_WEBHOOK_URL=optional_slack_webhook
DISCORD_WEBHOOK_URL=optional_discord_webhook
```

Also copy `config.example.yaml` to `config.yaml` to configure runtime defaults.

---

## ⚙️ Usage

Agent-Farm provides a comprehensive suite of Click-based CLI commands (`farm_agent`):

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt

# Deterministic round-robin target loop from target_repo.json
farm_agent hunt-circular

# Run the Relentless 24/7 Super Human loop (patrols PRs and hunts targets)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Perform code analysis pass only; do not generate contributions or open issues
farm_agent analyze <url>

# Show targets queue statuses, overall statistics, and memory db info
farm_agent status
farm_agent stats
farm_agent system-status

# Configuration & Models
farm_agent config
farm_agent models
farm_agent profile <profile_name>

# Leaderboard & PR management
farm_agent leaderboard
farm_agent janitor
farm_agent cleanup

# Database maintenance
farm_agent reset-db
farm_agent gc
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please ensure all patches are validated locally using our test suites (`make test`).

Licensed under the [MIT License](LICENSE).
