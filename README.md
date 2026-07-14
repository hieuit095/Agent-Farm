# 🛠️ Agent-Farm (v4.0.0)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features (v4.0.0 Upgrades)

* **Omniscient Context Engine (RAG codebase mapping):** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
* **Anti-Farming Filter:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system using Qwen-3.7-Max (Layer 1 Appraisal) and Gemini-3.5-Flash (Layer 2 Supreme Audit) to filter out false positives and theoretical edge cases.
* **Dynamic Bug Verification (isolated PoC execution in DockerSandbox):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check: Efficacy (re-running the PoC) and Regression (executing the project's native test suite).
* **Database/State Persistence:** Utilizes a SQLite database (`memory.db`) with schemas mapping to analyzed repos, submitted PRs, findings, run logs, PR outcomes, repo preferences, blacklisted repos, API usage logs, tasks, knowledge base, targets, and style guides.

---

## 🏛️ System Architecture (High-Level)

The `FarmAgentPipeline` orchestrates the core workflow, coordinating between the `GitHubClient` (for interactions with repositories and PRs), `Memory` (for state persistence in SQLite), `CodeAnalyzer` (for detecting issues), `ContributionGenerator` (for generating patches), and `PRManager` (for branch and PR lifecycle).

The system employs a multi-phase AI routing architecture. It uses `deepseek-v4-flash` via OpenRouter for general pipeline tasks (like Bloodhound Red Team vulnerability scanning via ast-grep and Semgrep). When a vulnerability is found, `deepseek-v4-pro` is used to write PoC scripts and patch the code. These patches are then rigorously evaluated by a DEV-QA Bounty Loop inside an isolated Docker sandbox. It leverages `qwen3.7-max` for rigorous Layer 1 Expert Appraisal and `gemini-3.5-flash` for the Layer 2 Supreme Audit before finalizing any contributions.

The agent also operates a continuous `Terminator Mode` (via `farm_agent superhuman`), a relentless continuous execution loop without artificial delays that cycles between Circular Target Loops and DEV-QA Bounty Loops.

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker** >= 7.1
* **Python** >= 3.11
* **Git** installed on the host machine.

### Installation & 1-Click Launch

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

3. **Environment Variables:**
   Configure your `.env` file with the following required environment variables to run the project (inferred from config files):
   * `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with repo scope.
   * `OPENROUTER_API_KEY`: API key for OpenRouter, used for DeepSeek, Qwen, and Gemini model routing.
   * `MINIMAX_API_KEY`: API key for Minimax.
   * `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications.

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage Reference

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <url>

# Analyze a repo without contributing
farm_agent analyze <url>

# Solve open issues in a specific repository
farm_agent solve <url>

# Run in Hunt Mode: auto-discover repos and contribute aggressively
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: process one target from target_repo.json
farm_agent hunt-circular

# Run the Terminator Mode (relentless 24/7 continuous execution loop)
farm_agent superhuman

# Patrol: check open PRs for review feedback and auto-respond
farm_agent patrol

# Show status of submitted pull requests
farm_agent status

# Show overall statistics
farm_agent stats

# Show current configuration
farm_agent config

# Clean up forks created by Farm-Agent
farm_agent cleanup

# Reset the run history database
farm_agent reset-db

# Alumni Sync + Full Friendly Repo List
farm_agent vips

# List available contribution templates
farm_agent templates

# Run pipeline with a named profile
farm_agent profile <profile_name>

# List available models and their capabilities
farm_agent models

# Show contribution leaderboard and success rates
farm_agent leaderboard

# Send a test notification to configured channels
farm_agent notify-test

# Show Farm-Agent system status
farm_agent system-status
```

---

## 📜 Contributing

We welcome white-hat security researchers, AI engineers, and open-source enthusiasts to contribute to Agent-Farm!

To get started:
1. Fork the repository and create your feature branch (`git checkout -b feature/amazing-feature`).
2. Follow our code style guidelines (run `make lint` before committing).
3. Ensure all local tests pass by running the pytest suite (`python -m pytest tests/unit/` or `make test`).
4. Commit your changes and open a Pull Request.

Please read `CONTRIBUTING.md` for details on our code of conduct, and the process for submitting pull requests to us.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
