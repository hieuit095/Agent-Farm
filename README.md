# Farm-Agent (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Farm-Agent is an autonomous system that automatically contributes to open-source projects on GitHub. Operating with human-like precision, it crawls GitHub repositories, analyzes code for vulnerabilities and flaws, generates high-quality patches, dynamically validates fixes inside isolated Docker sandboxes, and autonomously submits pull requests or private disclosures.

---

## 🔥 Key Features

* **Omniscient Context Engine:** Uses RAG powered by ChromaDB to deeply understand repository documentation and builds AST-based call graphs for precise module dependency resolution.
* **Dynamic Bug Verification (PoC Execution):** Before generating fixes, it dynamically generates and runs Proof-of-Concept exploits inside isolated Docker containers to verify vulnerabilities and avoid false positives.
* **Blast Radius & Regression Auditing:** Employs a double-pass Docker sandbox validation. Pass 1 verifies the PoC is fixed (efficacy), and Pass 2 executes the native test suite to prevent regressions.
* **DEV-QA Bounty Loop:** A multi-agent self-correcting circuit where generated patches are evaluated against coding style guidelines. Failures result in QA lessons, recorded context, and patch generation retries.
* **PR Patrol Daemon:** Continuously monitors open PRs to reply to maintainer feedback, answer questions, sign CLAs, and auto-heal failing CI pipelines using isolated sandboxes.
* **Zero-Garbage PR Gatekeepers:** Strict, multi-layered filters (including Qwen Expert Appraisal and Gemini Supreme Auditor) ensure only high-impact issues (e.g., security, critical bugs) are pursued, rejecting typo fixes or documentation-only PRs.

---

## 🏗️ System Architecture (High-Level)

Farm-Agent is built on the "DeerFlow" pattern, a registry-based agent architecture. It orchestrates execution loops (`FarmAgentPipeline`, `SuperHumanLoop`, `PRPatrol`) via Python's `asyncio`.

When targeting a repository, the pipeline fetches the codebase, analyzes it with Bloodhound (AST-grep + Semgrep), validates findings via LLMs, and enters a DEV-QA self-correction loop to generate patches. Patches are then rigorously tested within Docker sandboxes for efficacy and regression. Once validated, changes pass through an AI policy check, maintainer vibe check, and finally, a security disclosure gate before a PR is opened via the GitHub API.

State and historical run contexts are persisted in an SQLite database operating in WAL mode.

---

## 🛠️ Getting Started

### Prerequisites

* **Python 3.11+**
* **Docker Desktop** installed and running (for sandbox isolation).
* **Git** installed on the host machine.
* A GitHub Personal Access Token (PAT) with `repo` scope.
* An LLM API key (e.g., OpenRouter or Minimax) configured with credits.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **For Local Development (Install with Dev Dependencies):**
   ```bash
   make install
   ```

3. **Or Use 1-Click Docker Quick-Start:**
   * **Windows:** Double-click `start.bat` or run:
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values. Never commit your `.env` file to version control.

Required variables:
* `GITHUB_TOKEN`: Your GitHub personal access token (falls back to `gh auth token` CLI).
* `MINIMAX_API_KEY`: API key for Minimax if using as the main LLM provider.
* `OPENROUTER_API_KEY`: API key for OpenRouter (used for Red Team audits and general pipeline tasks).

Optional variables:
* `GITHUB_SECONDARY_TOKENS`: Additional comma-separated tokens to distribute read-only API load.
* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For Telegram push notifications.
* `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for notifications.
* `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for notifications.

*Note: You must also configure `config.yaml` based on `config.example.yaml` for precise pipeline tuning.*

---

## ⚙️ Usage

The system uses the `farm_agent` CLI tool built with Click and Rich.

```bash
# Start the full automated discovery and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <url>

# Solve open issues in a specific repository
farm_agent solve <url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Run the 24/7 Super Human loop (patrols PRs and hunts targets)
farm_agent superhuman

# Check open PRs for maintainer review comments and auto-fix CI failures
farm_agent patrol

# Show overall Farm-Agent statistics
farm_agent stats
```

---

## 📜 Contributing & License

We welcome contributions! Please run `make lint` and `make test` before submitting pull requests.

Licensed under the [MIT License](LICENSE).
