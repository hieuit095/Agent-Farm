# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous AI agent designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It operates behind a sophisticated human behavior simulation layer to ensure all contributions provide genuine value to maintainers without creating friction or spam.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs (`farm_agent/issues/solver.py`).
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches before any Pull Request is created, preventing broken code submissions (`farm_agent/core/sandbox.py`).
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files (`farm_agent/core/rag.py`).
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers (`farm_agent/orchestrator/pipeline.py`).
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays to mimic a real developer's circadian rhythm (`farm_agent/orchestrator/human.py`).
- **Security Disclosure Gate:** Automatically detects and aborts the pipeline if a repository's metadata (e.g., SECURITY.md) requests private vulnerability disclosure, preventing public leaks (`farm_agent/github/security_gate.py`).
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes and answer questions (`farm_agent/pr/patrol.py`).

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator interacts with an LLM Provider (supporting MiniMax, OpenRouter, etc.) and the GitHub REST API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** Required for Polyglot Sandbox Validation

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   make install
   ```

### Environment Variables

Configure the agent using `config.yaml` or set the necessary key environment variables based on `.env.example`:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access (if using Minimax).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.

Alternatively, copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` and fill in your details.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes (`farm_agent/cli/main.py`):

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target <url>
```

**Analyze a repo without contributing:**
```bash
farm_agent analyze <url>
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve <url>
```

**Show status of submitted PRs:**
```bash
farm_agent status
```

**Show overall statistics:**
```bash
farm_agent stats
```

**Show current configuration:**
```bash
farm_agent config
```

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
