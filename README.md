# 🛠️ Agent-Farm (v4.0.0)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Build Backend: Hatchling](https://img.shields.io/badge/build-hatchling-blue)](https://hatch.pypa.io/latest/)

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, and submit robust pull requests or private disclosures. By executing dynamic bug verification in isolated Docker sandboxes and enforcing strict multi-layer filter gates, it ensures that every contribution is precise, high-value, and regression-free.

## 🔥 Key Features

* **Omniscient Context Engine:** Uses Retrieval-Augmented Generation (RAG) powered by ChromaDB to ingest repository documentation and construct deep AST-based call graphs, injecting precise dependency links directly into the LLM context.
* **Dynamic Bug Verification:** Before generating patches, the agent writes and executes self-contained Proof-of-Concept (PoC) exploit scripts in a strictly locked-down Docker sandbox to confirm vulnerabilities are genuine.
* **Blast Radius & Regression Auditing:** Executes a dual-pass validation in the isolated sandbox, confirming both that the bug is resolved by the generated patch and that the project's native test suite still passes without regressions.
* **Zero-Garbage PR Gatekeepers:** Employs multi-layer AI auditing (Layer 1: Qwen-3.7-Max, Layer 2: Gemini-3.5-Flash) to strictly filter out low-quality patches, typo-fixes, or modifications to deprecated code, eliminating maintainer spam.
* **Super Human Mode:** A relentless 24/7 autonomous loop featuring built-in human-like delays, PR patrolling for comment replies and automated CI failure fixes, and intelligent context switching.

## 🏗️ System Architecture (High-Level)

The system orchestrates a "DeerFlow" architecture utilizing multiple discrete agent roles. The Pipeline discovers repositories and relies on Bloodhound Red Team rules to scan the codebase. When vulnerabilities are detected, a Generator engine creates dynamic PoC tests and proposes fixes. These fixes undergo rigorous sandbox isolation checks against the host application's test suite and strict LLM expert reviews before the PR Manager formulates a final, polished GitHub Pull Request or Security Advisory. State is continuously persisted into an idempotently managed SQLite database.

## 🛠️ Getting Started

### Prerequisites

* **Python:** `>= 3.11`
* **Docker:** `>= 7.1` (Required for isolated PoC and test execution)
* **Git** installed locally.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Quick-Start via Docker (1-Click Launch):**
   * **Windows:**
     ```cmd
     start.bat
     ```
   * **Linux/macOS:**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   This pulls the latest image, sets up your `.env` file, and launches the `agent-farm` daemon.

3. **Manual / Development Installation:**
   ```bash
   make install
   ```

### Environment Variables

Configure these settings in your `.env` file (copied from `.env.example`):

* `GITHUB_TOKEN` (Required): Personal Access Token for creating PRs and interacting with repositories.
* `MINIMAX_API_KEY`: Required if using Minimax as the default LLM provider.
* `OPENROUTER_API_KEY`: API key for accessing models like `deepseek-v4-pro`, `qwen3.7-max`, and `gemini-3.5-flash` through OpenRouter.
* `TELEGRAM_BOT_TOKEN`: (Optional) For automated project notifications.
* `EXCLUDED_LANGUAGES`: (Optional) Comma-separated languages to bypass (e.g., `javascript,typescript`).

## 💻 Usage

Agent-Farm utilizes a comprehensive, Rich-powered Click CLI:

```bash
# Analyze a specific repository without contributing
farm_agent analyze <repo_url>

# Target a repository to discover issues and generate PRs
farm_agent target <repo_url>

# Focus exclusively on solving open issues in a targeted repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repositories and solve issues
farm_agent hunt --rounds 5 --mode both

# Run the 24/7 Super Human loop (patrols PRs, hunts targets, acts human)
farm_agent superhuman

# Patrol open PRs to answer maintainer comments and fix CI pipelines
farm_agent patrol

# View system configuration and runtime statistics
farm_agent config
farm_agent stats
```

*For Docker users, run commands inside the container:*
```bash
docker exec -it agent-farm farm_agent superhuman
```

## 🤝 Contributing

Contributions are heavily encouraged from AI engineers and white-hat security researchers. Please ensure code complies with the project's Ruff style rules (`make lint`) and passes all tests (`make test`).

## 📄 License

This project is licensed under the [MIT License](LICENSE).
