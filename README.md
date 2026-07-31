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

- **Omniscient Context Engine**: Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. Recursively discovers internal documentation, semantically chunks docs, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents.
- **Dynamic Bug Verification**: Generates and executes Proof-of-Concept (PoC) exploits in an isolated container sandbox via Docker. If the PoC fails to trigger the bug, the finding is dropped as a false positive.
- **Terminator Mode**: A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite database.
- **Anti-Farming Filter**: A strict two-layer filter system (Layer 1 Appraisal using Qwen, Layer 2 Supreme Audit using Gemini) that blocks trivial/documentation PRs and validates real-world value.
- **Blast Radius & Regression Auditing**: Employs baseline test suite runs and downstream dependent analysis to guarantee zero regressions.
- **Issue-First Pipeline**: Discovers and proposes solutions for open GitHub issues autonomously.
- **PR Patrol**: Automatically patrols and auto-replies to comments, addresses code reviews, and self-corrects CI failures for submitted PRs.
- **Bloodhound Red Team**: Integrated Semgrep rulesets and AST-grep for deep security auditing.

---

## 🏗️ System Architecture (High-Level)

The Agent-Farm ecosystem orchestrates multiple specialized components to automate software contributions:
1. **CLI / Entry Points**: The `farm_agent` CLI triggers execution loops (`run`, `superhuman`, `hunt`, `patrol`).
2. **Orchestrator Pipeline**: Manages the end-to-end contribution flow (`FarmAgentPipeline`), coordinating Git cloning, analysis, and validation.
3. **LLM Router**: Dynamically routes tasks to specialized models (e.g., DeepSeek v4 Pro for coding, Qwen 3.7 Max for Layer 1 appraisal, Gemini 3.5 Flash for Layer 2 audit) via OpenRouter to balance cost, speed, and accuracy.
4. **Sandboxed Verification**: Executes code, PoCs, and test suites in a secure, isolated Docker container (`sandbox_isolated` network) to dynamically verify patches.
5. **Memory & State**: Stores repository analysis, PR outcomes, targets, and knowledge base chunks in a local SQLite database (`memory.db`), enabling long-term learning and tracking.

---

## 🚦 Getting Started

### Prerequisites
- **Python**: `>=3.11`
- **Docker**: `>=7.1` (Required for dynamic bug verification and isolated execution)
- **Git**: Installed and accessible

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Install with Dev Dependencies (Standard Development Setup):**
   ```bash
   make install
   # This runs: pip install -e '.[dev]'
   ```

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in the required keys.
   ```bash
   cp .env.example .env
   ```
   **Required `.env` Variables:**
   - `GITHUB_TOKEN`: Personal access token with repo, read:org, and workflow scopes.
   - `OPENROUTER_API_KEY`: Required for LLM routing and Red Team Bloodhound audits.
   - `MINIMAX_API_KEY`: Required if using Minimax as the primary provider.

   **Optional `.env` Variables:**
   - `GITHUB_SECONDARY_TOKENS`: Comma-separated list for GET request rotation.
   - `EXCLUDED_LANGUAGES`: E.g., `javascript,typescript` to save LLM budget.
   - `MINIMAX_GROUP_ID`: Sent as X-Minimax-Group-Id header.
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`: For notifications.

4. **1-Click Docker Launch (Optional):**
   Use the provided scripts for a quick Docker desktop start:
   ```bash
   ./start.sh  # Or start.bat on Windows
   ```

---

## 💻 Usage

Agent-Farm provides a comprehensive CLI for managing operations.

**Run a standard hunt against a specific target:**
```bash
farm_agent run --repo owner/repo
```

**Run continuous Terminator Mode (relentless execution from database targets):**
```bash
farm_agent superhuman
```

**Run the PR Patrol to address CI failures and code reviews:**
```bash
farm_agent patrol
```

**View system status and memory metrics:**
```bash
farm_agent system-status
```

---

## 🤝 Contributing & License

Agent-Farm is licensed under the [MIT License](LICENSE).

Contributions are welcome! Please ensure all code passes formatting and linting checks by running `make lint` before submitting a Pull Request. Testing requires Docker to be running on your machine.
