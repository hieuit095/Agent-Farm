# 🛠️ Agent-Farm

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with precision, it implements advanced DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and regression-free.

---

## 🔥 Key Features

* **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs to inject precise module dependency links directly into the prompt context.
* **Anti-Farming Filter:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system (Layer 1 Appraisal via Qwen, Layer 2 Supreme Audit via Gemini) and vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.
* **Dynamic Bug Verification:** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check: first, it ensures the PoC no longer triggers the bug; second, it runs the project's native test suite to ensure no existing functionality is broken.
* **PR Patrol:** Checks open PRs created by the agent, reads maintainer review comments, generates code fixes, answers questions, and auto-fixes CI failures.
* **Issue-First Pipeline:** Proactively searches for solvable issues in a repository, constructs deep multi-file fixes, and generates PRs that solve the issues.
* **Terminator Mode:** A relentless continuous execution loop without artificial delays, cycling through a target repository queue to autonomously discover and solve issues 24/7.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm operates as a multi-stage contribution pipeline orchestrated via a central `FarmAgentPipeline`. The system leverages an `AdaptiveConcurrencyManager` to safely interact with LLM providers without hitting rate limits.

1. **Discovery & Reconnaissance:** It fetches target repositories from an internal SQLite database (`memory.db`), clones them into an isolated environment, and indexes their documentation via the Omniscient Context Engine.
2. **Analysis & Bloodhound Scanning:** Code and dependencies are scanned using LLMs and Semgrep rulesets (e.g., CWE-Top-25) to identify high-impact issues. The findings are passed through the Anti-Farming Filter to discard trivial or documentation-only issues.
3. **Generation & Verification:** For validated findings, a patch is generated along with a PoC. The patch is then rigorously tested in a Docker sandbox (Dynamic Bug Verification and Blast Radius & Regression Auditing) to ensure it works and doesn't break existing code.
4. **Submission:** If all tests pass and the Layer 2 Supreme Audit approves, the agent either submits a GitHub Pull Request or performs a private security disclosure. The PR Patrol module then takes over to monitor and refine the submission based on maintainer feedback.

---

## 🛠️ Getting Started

### Prerequisites

* **Docker** >= 7.1 (Docker Desktop recommended, running and accessible)
* **Python** >= 3.11
* **Git** installed on the host machine.

### Installation

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution. Use the 1-Click Docker Launch instructions below:

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
   *Note: The script will pull the latest codebase, initialize your `.env` configuration file from `.env.example`, build the Docker image, and launch the daemon in the background.*

### Environment Variables

Configure your `.env` file with the following required environment variables to run the project.

```env
# GitHub Authentication (Required)
# Personal access token with repo, read:org, and workflow scopes.
GITHUB_TOKEN=

# Additional GitHub tokens for GET request rotation (comma-separated).
GITHUB_SECONDARY_TOKENS=

# LLM Provider (Required)
# API key for OpenRouter, used for the primary LLM, Code Gen LLM, Layer 1, Layer 2, and Bloodhound audits.
OPENROUTER_API_KEY=

# Pipeline & Targeting Options
# Filter out verbose/costly languages (comma-separated) to save LLM API budget.
EXCLUDED_LANGUAGES=javascript,typescript

# Notifications (Optional)
# Telegram bot token and chat ID for push notifications.
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Slack incoming webhook URL for push notifications.
SLACK_WEBHOOK_URL=

# Discord incoming webhook URL for push notifications.
DISCORD_WEBHOOK_URL=
```

---

## 💻 Usage

Agent-Farm provides a comprehensive suite of Click-based CLI utilities. To attach to the CLI running inside your Docker container, use:

```bash
docker exec -it agent-farm farm_agent <command>
```

### Core CLI Commands

```bash
# Run the relentless Terminator Mode (24/7 continuous target loop without artificial delays)
farm_agent superhuman

# Start the automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly for contributions
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and perform analysis or issue solving
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: process one target from target_repo.json
farm_agent hunt-circular

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Analyze a repository without creating contributions
farm_agent analyze <repo_url>

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Clear run logs and start with a fresh database
farm_agent reset-db

# Garbage Collection: purge stale knowledge base entries older than N days
farm_agent gc --days 90

# Output the current loaded runtime settings
farm_agent config

# Show status of submitted pull requests
farm_agent status

# Show overall runtime and API usage statistics
farm_agent stats

# Show contribution leaderboard and success rates
farm_agent leaderboard

# List available models and their capabilities
farm_agent models

# Monitor and synchronize VIP repository radar list
farm_agent vips

# List available contribution templates
farm_agent templates

# Run pipeline with a pre-configured profile
farm_agent profile <profile_name>

# Send a test notification to configured channels
farm_agent notify-test

# Show Farm-Agent system status — memory, PRs, rate limits
farm_agent system-status
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
