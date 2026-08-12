# 🛠️ Agent-Farm (v4.0.0)

**Autonomous system that automatically contributes to open source projects on GitHub with human-like precision and rigorous validation.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and strict filters to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

* **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It semantically maps module dependencies (using AST for Python, Rust, Go, TypeScript) and recursively discovers documentation.
* **Dynamic Bug Verification:** Before writing a fix, the agent generates a Proof-of-Concept (PoC) script to dynamically trigger vulnerabilities inside a locked-down DockerSandbox. If the bug can't be triggered, the finding is discarded.
* **Blast Radius & Regression Auditing:** Validates generated patches by applying them locally and running the project's native test suite to ensure no downstream dependencies or existing functions are broken.
* **Anti-Farming Filter:** A stringent dual-layer gatekeeping system that strictly blocks trivial, documentation-only, or formatting PRs.
  * *Layer 1 Appraisal:* Powered by Qwen (e.g., qwen3.7-max) to assess finding severity.
  * *Layer 2 Supreme Audit:* Powered by Gemini (e.g., gemini-3.5-flash) as the final veto.
* **Terminator Mode:** A relentless, continuous execution loop (`SuperHumanLoop`) that hunts for targets directly from the SQLite memory queue without artificial delays.
* **Issue-First Pipeline & PR Patrol:** Solves existing issues intelligently via `issues/solver.py` and actively monitors submitted PRs for maintainer feedback or CI failures to provide auto-fixes (`pr/patrol.py`).

---

## 🏗️ System Architecture (High-Level)

Agent-Farm leverages a multi-model approach, routing tasks to specialized LLMs based on cost and capability (e.g., DeepSeek models via OpenRouter for general pipeline tasks, Qwen for appraisal, and Gemini for final audits).

The core orchestration loop targets repositories via `target_repos` and initiates the **Bloodhound Red Team** analysis (utilizing Semgrep and AST scanning). Once a vulnerability or issue is pinpointed, the **Contribution Generator** attempts a fix. The fix undergoes rigorous testing within the **DockerSandbox**, a highly isolated container environment where the PoC and test suites execute safely. If the sandbox validates the patch, the **PR Manager** forks the repository, pushes the commit, and opens a meticulously documented pull request. All historical data, cache, and state are persistently tracked in a WAL-enabled SQLite database (`memory.db`).

---

## 🛠️ Getting Started

### Prerequisites

* **Python:** `>= 3.11`
* **Docker:** `>= 7.1` (Docker Desktop recommended for local execution)
* **Git:** Required for shallow cloning and patching repositories locally.

### 1-Click Docker Launch

We provide wrapper scripts for a seamless 1-Click Docker Desktop Quick-Start experience.

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Configure Environment Variables:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   *The start scripts will also attempt to handle this initialization automatically.*

3. **Run the Quick-Start Script:**
   * **Windows:**
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

### Environment Variables

Configure the `.env` file with the following variables. The exact variables required are:

* `GITHUB_TOKEN` *(Required)*: Your primary GitHub Personal Access Token (with `repo`, `read:org`, and `workflow` scopes).
* `OPENROUTER_API_KEY` *(Required for Bloodhound & General Tasks)*: API key for OpenRouter routing.
* `MINIMAX_API_KEY` *(Required if using Minimax fallback)*: Minimax API key.
* `MINIMAX_GROUP_ID` *(Optional)*: Sent as X-Minimax-Group-Id header.
* `GITHUB_SECONDARY_TOKENS` *(Optional)*: Comma-separated tokens to distribute read-only API load.
* `EXCLUDED_LANGUAGES` *(Optional)*: Comma-separated languages to skip (e.g., `javascript,typescript`).
* `TELEGRAM_BOT_TOKEN` *(Optional)*: Telegram token for push notifications.
* `TELEGRAM_CHAT_ID` *(Optional)*: Telegram chat ID for notifications.
* `SLACK_WEBHOOK_URL` *(Optional)*: Slack incoming webhook for push notifications.
* `DISCORD_WEBHOOK_URL` *(Optional)*: Discord incoming webhook for push notifications.

---

## 💻 Usage

Agent-Farm provides a rich CLI interface. Here are common usage examples:

**Run Terminator Mode (Relentless Execution):**
```bash
docker exec -it agent-farm farm_agent superhuman
```

**Target a Specific Repository:**
```bash
docker exec -it agent-farm farm_agent target https://github.com/user/repo
```

**Solve Existing Issues:**
```bash
docker exec -it agent-farm farm_agent solve https://github.com/user/repo
```

**Run PR Patrol (Monitor & Auto-Fix):**
```bash
docker exec -it agent-farm farm_agent patrol
```

**Check System Status:**
```bash
docker exec -it agent-farm farm_agent system-status
```

*Note: For local development outside of Docker, install dependencies using `pip install -e '.[dev]'` within an activated virtual environment.*

---

## 📜 Contributing & License

We welcome open-source contributions! If you would like to contribute, please fork the repository and ensure you run `make test` and `make lint` before submitting a pull request.

Licensed under the [MIT License](LICENSE).
