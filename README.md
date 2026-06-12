# 🛠️ Agent-Farm

**Autonomous System that Automatically Contributes to Open Source Projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-%3E%3D7.1-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. It implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and regression-free.

## 🔥 Key Features

* **Omniscient Context Engine**: Uses Retrieval-Augmented Generation (RAG) powered by ChromaDB to ingest repository documentation and map local module/function dependencies via AST.
* **Dynamic Bug Verification**: Generates and executes Proof-of-Concept (PoC) scripts in an isolated container sandbox to dynamically trigger and verify vulnerabilities before attempting a fix.
* **Blast Radius & Regression Auditing**: Employs a double-pass check by running the PoC on the patched code (Efficacy) and the project's native test suite (Regression).
* **Zero-Garbage PR Gatekeepers**: Enforces strict verdicts via a two-layer filter system (Expert Appraisal and Supreme Audit) to veto low-value patches and false positives.
* **PR Patrol Daemon**: Continuously checks open PRs for maintainer comments, auto-replies to questions, signs CLAs, and auto-fixes CI pipeline failures.
* **Anti-Farming Filters**: Strict zero-tolerance for typo-fixes, formatting tweaks, or documentation-only PRs, ensuring high-impact security and feature contributions.

## 🏗️ System Architecture (High-Level)

Agent-Farm operates using a custom registry-based agent architecture ("DeerFlow"). It orchestrates the entire contribution pipeline from repository discovery, code analysis, patch generation, sandbox validation, and final PR submission. A central SQLite memory database tracks state in WAL mode, while an Adaptive Concurrency Manager ensures GitHub API rate limits are respected. The execution utilizes multi-model routing to designate task-specific models (e.g., DeepSeek, Qwen, Gemini).

## 🛠️ Getting Started

### Prerequisites
* **Python**: `3.11` or higher.
* **Docker**: Version `7.1` or higher (required for isolated sandbox validation).
* **Git**: Installed and available in PATH.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **Quick Start using Docker (Recommended):**
   * **Linux / macOS:**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   * **Windows:**
     ```cmd
     start.bat
     ```

3. **Manual Development Setup:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   make install              # Installs via pip install -e '.[dev]'
   ```

### Environment Variables

Copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` before running. Required variables in `.env`:
* `GITHUB_TOKEN`: Your GitHub Personal Access Token (with repo scope).
* `MINIMAX_API_KEY`: API key if using Minimax provider.
* `OPENROUTER_API_KEY`: Required for multi-model routing and Bloodhound Red Team audits via OpenRouter.
* `TELEGRAM_BOT_TOKEN`: (Optional) For push notifications on pipeline status.

## ⚙️ Usage

Agent-Farm provides a rich CLI application (`farm_agent`) for interacting with the pipeline.

**Attach to Docker Container:**
```bash
docker exec -it agent-farm farm_agent superhuman
```

**Core CLI Commands:**
* `farm_agent run`: Start the full automated discovery, analysis, and contribution pipeline.
* `farm_agent target <url>`: Target a specific repository directly.
* `farm_agent hunt`: Run multi-round aggressive search and analysis (analysis, issues, or both).
* `farm_agent hunt-circular`: Run deterministic round-robin target loop from `target_repo.json`.
* `farm_agent solve <url>`: Proactively search for solvable issues in a repo and generate deep fixes.
* `farm_agent patrol`: Check open PRs for maintainer review comments, reply to questions, and auto-fix CI failures.
* `farm_agent superhuman`: Run the relentless 24/7 Super Human loop cycling through circular targets and patrol operations.
* `farm_agent janitor`: Sweep all open PRs and close low-quality/garbage contributions.

## 🤝 Contributing

We welcome contributions! Please follow the conventional commit formats and ensure all patches are validated locally.

1. Fork the repository.
2. Create your feature branch.
3. Commit your changes using conventional commits.
4. Push to the branch and open a Pull Request.

Run tests locally using `make test`.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.