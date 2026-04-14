# Farm-Agent 🚜🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)

**Farm-Agent** is an autonomous AI system that intelligently analyzes, solves, and contributes to open-source GitHub repositories 24/7. It autonomously hunts for target repositories, sets up a secure polyglot sandbox, finds/solves issues, pushes PRs, and gracefully handles maintainer feedback via its PR Patrol system.

## 🚀 Key Features

*   **Super Human Mode (24/7 Autonomous Operation):** Mimics a dedicated human developer. It dynamically sets daily PR quotas, shifts between active hunting and PR patrol, and operates continuously without need for human intervention.
*   **PR Patrol & Maintainer Sync:** Scans open Farm-Agent PRs for review feedback, classifies comments (using LLMs), and autonomously generates, tests, and pushes code fixes in response.
*   **Bloodhound Red Team & Semgrep Integration:** Deep code analysis utilizing `ast-grep` and `Semgrep` combined with an LLM Red Team engine (via OpenRouter) for white-hat security auditing.
*   **Polyglot Sandbox Validation:** Uses the Docker SDK to execute and validate generated code for untrusted repositories before submitting any pull request, ensuring safe execution.
*   **Issue Solver:** Automatically filters and categorizes solvable GitHub issues, generates solutions, and submits them.
*   **Persistent SQLite Memory Engine:** Tracks analyzed repos, submitted PRs, outcomes, and rate limits in a robust, local SQLite database (`memory.db`), ensuring fault-tolerant crash recovery.
*   **Multi-LLM Routing Strategy:** Flexibly routes tasks across Minimax (primary), Gemini, OpenAI, Anthropic, and local Ollama models depending on cost, speed, and capabilities.

## 🏗️ System Architecture (High-Level)

Farm-Agent operates through a unified CLI built on `Click` and `Rich`. When executed (e.g., in `SuperHuman` mode), it leverages an **Orchestrator Pipeline** that cycles through the following phases:
1.  **Discovery/Targeting:** Uses GitHub REST API to find or target specific repositories based on language, stars, and activity criteria.
2.  **Analysis & Bloodhound RAG:** Scans the target codebase for security, code quality, UI/UX, or documentation issues, indexing context in a fast, ephemeral ChromaDB RAG store.
3.  **Generation & Sandboxing:** Generates patches using the selected LLM provider, applies them within a secure, isolated Docker Polyglot Sandbox, and attempts verification (tests/lints).
4.  **PR Management & Patrol:** Creates forks and pushes the verified fixes to a new branch. A persistent watcher later reviews PR comments and pushes follow-up fixes automatically.

## 🛠️ Getting Started

### Prerequisites
*   **Python:** 3.11 or higher
*   **Docker:** version 7.1+ (Required for Polyglot Sandbox execution)
*   **Git:** Configured locally for operations

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hieuit095/Farm-Agent.git
    cd Farm-Agent
    ```

2.  **Install the package with development dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```
    *(Note: Using the Makefile, you can also run `make install`)*

### Environment Variables

Copy the provided `.env.example` file to create your own `.env`:
```bash
cp .env.example .env
```
The following variables are **required** to run the agent:
*   `GITHUB_TOKEN`: A GitHub Personal Access Token (classic) with `repo`, `read:org`, and `workflow` scopes.
*   `MINIMAX_API_KEY`: API key for Minimax (the default LLM provider).

*Optional but recommended variables:*
*   `OPENROUTER_API_KEY`: Used by the Bloodhound Red Team pipeline for routing white-hat audits.
*   `GITHUB_SECONDARY_TOKENS`: Additional tokens to distribute read-only API load.
*   `TELEGRAM_BOT_TOKEN` / `SLACK_WEBHOOK_URL`: For push notifications on merges/completions.

## 💻 Usage Examples

The system provides a feature-rich CLI:

*   **Super Human Mode:** (24/7 autonomous loop interleaving Hunt and Patrol)
    ```bash
    farm_agent superhuman
    ```
*   **Target a Specific Repo:**
    ```bash
    farm_agent target https://github.com/owner/repo
    ```
*   **Hunt Mode:** (Auto-discover repos and aggressively contribute)
    ```bash
    farm_agent hunt --language python --stars 1000-5000
    ```
*   **PR Patrol:** (Scan and auto-respond to pending feedback on your open PRs)
    ```bash
    farm_agent patrol
    ```
*   **Solve Issues:** (Target a repo and solve up to 5 open issues)
    ```bash
    farm_agent solve https://github.com/owner/repo -n 5
    ```
*   **Check Stats:**
    ```bash
    farm_agent stats
    ```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check the issues page. If you are submitting a pull request, please make sure your changes pass the existing testing and linting suite:
```bash
make lint
make test
```

## 📜 License

This project is licensed under the MIT License - see the [pyproject.toml](pyproject.toml) file for details.
