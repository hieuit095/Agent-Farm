# 🛠️ Agent-Farm (v4.0.0)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## 🚀 Overview

Agent-Farm is an autonomous AI system designed to automatically contribute to open-source projects on GitHub. It discovers repositories, scans for vulnerabilities and code flaws, generates patches, and dynamically verifies them within isolated Docker sandboxes before submitting pull requests.

## 🔥 Key Features

*   **Omniscient Context Engine:** Uses local RAG (ChromaDB) to map local module dependency linkages and ingest subsystem documentation, feeding rich context to the LLM.
*   **Dynamic Bug Verification:** Validates bug fixes by dynamically executing generated Proof-of-Concept (PoC) scripts in a highly isolated Docker container.
*   **Blast Radius & Regression Auditing:** Checks if a generated patch causes regressions by running baseline native tests, effectively operating as a DEV-QA loop.
*   **Zero-Garbage PR Gatekeepers:** Two-layer filter pipeline powered by deep LLMs (Qwen Layer 1 Appraisal and Gemini Layer 2 Supreme Audit) preventing trivial, documentation-only, or false-positive submissions.
*   **Super Human Mode:** A relentless Terminator Mode operation loop running 24/7, pulling targets from an SQLite database and dynamically solving issues.

## 🏗️ System Architecture (High-Level)

The orchestrator operates as a `FarmAgentPipeline` executing continuous execution loops or targeting single repositories. The pipeline first discovers targets, pulls dependencies and builds an AST-level dependency linkage. The Bloodhound Red Team then scans for actionable issues. Issues are sent through the Hybrid Router to determine if a PR can be drafted immediately (Route A) or if an issue must be proposed first (Route B). Generated patches are heavily scrutinized in an isolated Docker environment against baseline metrics. If all safety metrics and regression checks pass, the PR Manager signs a CLA, executes commit actions, and monitors the PR lifecycle through PR Patrol interactions.

## 🛠️ Getting Started

### Prerequisites

*   **Python:** >= 3.11
*   **Docker:** >= 7.1
*   **Git**

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hieuit095/Agent-Farm.git
    cd Agent-Farm
    ```
2.  **Set up the development environment:**
    ```bash
    make install
    ```
    Alternatively, using pip:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -e '.[dev]'
    ```
3.  **1-Click Docker Launch:**
    Use the provided quick-start scripts to build and start the Docker containers:
    ```bash
    # On Unix (Linux/macOS)
    ./start.sh

    # On Windows
    start.bat
    ```

### Environment Variables

You need to provide the necessary environment variables, typically loaded from a `.env` file. A `.env.example` file is provided as a template.

*   `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT).
*   `OPENROUTER_API_KEY`: API key for OpenRouter (used for models like `deepseek-v4-pro`, `qwen3.7-max`, `gemini-3.5-flash`).
*   `MINIMAX_API_KEY`: Required for the PR Janitor LLM evaluation.
*   `TELEGRAM_BOT_TOKEN`: Optional, required if you want to use the Telegram notifications.

## 💻 Usage

Agent-Farm offers a robust CLI (`farm_agent`) for various autonomous workflows:

*   **Run Auto-Discovery Pipeline:** Discover repositories and contribute aggressively.
    ```bash
    farm_agent run
    ```
*   **Target Specific Repository:** Execute the pipeline on a single known URL.
    ```bash
    farm_agent target https://github.com/user/repo
    ```
*   **Solve Specific Issues:** Search and resolve open GitHub issues on a target repository.
    ```bash
    farm_agent solve https://github.com/user/repo
    ```
*   **Hunt Mode:** Multi-round search and analysis loop.
    ```bash
    farm_agent hunt --rounds 5 --mode both
    ```
*   **Super Human Mode:** Terminator Mode; 24/7 continuous operation cycling between hunting and PR patrol.
    ```bash
    farm_agent superhuman
    ```
*   **PR Patrol:** Checks open PRs for reviewer feedback and pushes AI-generated fixes.
    ```bash
    farm_agent patrol
    ```
*   **System Status & Analytics:** View runtime statistics and leaderboard information.
    ```bash
    farm_agent stats
    farm_agent status
    farm_agent leaderboard
    ```

## 🤝 Contributing

Contributions are welcome! Please run `make lint` and `make test` before submitting pull requests. Ensure any new features are accompanied by tests.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
