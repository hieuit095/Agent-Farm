# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to automatically contribute to open-source GitHub projects. It discovers repositories, identifies real bugs and quality issues (via AST and Semgrep), generates contextually precise fixes (via RAG and LLMs), and strictly validates patches in isolated Docker sandboxes before ever submitting a Pull Request.

## Key Features

- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and strictly validate generated code patches (for Python, Node.js, Rust, Go, etc.) before PR creation. If a patch fails, it enters a self-correction DEV-QA loop.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that strictly blocks trivial findings (e.g., typos, formatting) and documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode & Terminator Execution Loop:** Operates as a relentless 24/7 autonomous engine to maximize PR throughput up to daily API caps.
- **Circular Target Loop:** Deterministic round-robin processing of target repositories for continuous operation and crash-safe rotation.
- **Red Team Auditing (Bloodhound):** Runs Semgrep pre-scans and White-Hat code audits via OpenRouter to identify real security and quality vulnerabilities.
- **X-Ray Vision via RAG:** Uses a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple repository files.
- **PR Patrol:** Autonomously monitors open Farm-Agent PRs for maintainer review feedback, generates code fixes based on that feedback, and pushes updates.
- **Token Pool Rotation:** Supports GitHub GET request rotation across multiple secondary tokens to respect rate limits.

## System Architecture (High-Level)

Farm-Agent is orchestrated via a powerful Click-based CLI (`farm_agent`). The core orchestrator pipeline connects several key modules:
1.  **Discovery:** Finds relevant repositories using GitHub APIs or local target files.
2.  **Bloodhound & Analysis:** Identifies vulnerabilities and issues via static analysis and Red Team LLM audits.
3.  **Generator Engine:** Generates patch code while referencing ChromaDB RAG for deep contextual accuracy.
4.  **Docker Sandbox:** Validates the generated code by applying the patch to a cloned repository inside an isolated Docker container and running tests.
5.  **PR Manager:** Submits the validated patch as a Pull Request to GitHub.

State and configuration are persistently managed via SQLite (`memory.db`) and YAML configuration files.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Polyglot Sandbox Validation)
- **Hatchling:** Used as the build backend

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configure the agent using `config.yaml` (copy from `config.example.yaml`) or set the following key environment variables in a `.env` file (copy from `.env.example`):

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (PAT).
- `GITHUB_SECONDARY_TOKENS`: Additional tokens (comma-separated) for GET request rotation.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM code generation (default).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: OpenRouter API key for Red Team audits (optional but recommended).

## Usage

Farm-Agent provides a rich command-line interface.

**Core Commands:**

*   `farm_agent run`: Auto-discover repositories and run the contribution pipeline.
*   `farm_agent target <url>`: Target a specific repository directly for contributions.
*   `farm_agent analyze <url>`: Analyze a repository without generating contributions or PRs.
*   `farm_agent solve <url>`: Solve open issues in a specific repository.
*   `farm_agent hunt`: Run hunt mode (aggressively discover and contribute across multiple rounds).
*   `farm_agent hunt-circular`: Run the circular target loop, processing targets from `target_repo.json`.
*   `farm_agent patrol`: Monitor open PRs for maintainer feedback and auto-respond.
*   `farm_agent superhuman`: Run the 24/7 Super Human Mode operational loop.

**System and Status Commands:**

*   `farm_agent status`: Show the status of submitted Pull Requests.
*   `farm_agent stats`: Show overall agent statistics (runs, repos analyzed, PRs).
*   `farm_agent config`: Show the current configuration.
*   `farm_agent system-status`: Show system memory, PR stats, and GitHub rate limits.
*   `farm_agent leaderboard`: Show contribution leaderboard and PR merge rates.
*   `farm_agent templates`: List available contribution templates.
*   `farm_agent profile <name>`: Run the pipeline with a specific named profile.
*   `farm_agent models`: List available LLM models and their configured capabilities.
*   `farm_agent gc`: Run garbage collection to purge stale knowledge base entries.
*   `farm_agent reset-db`: Safely reset the run history database.
*   `farm_agent notify-test`: Send a test notification to configured channels.

*(Note: The `janitor` command is currently disabled).*

## Contributing & License

We welcome contributions! Please follow standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
