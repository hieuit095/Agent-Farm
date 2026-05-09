# 🛠️ Farm-Agent

**Autonomous, Relentless Open Source Contribution Engine**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous system designed to relentlessly discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. Operating via a Terminator execution loop, it maximizes PR throughput up to daily API caps while utilizing rigorous polyglot sandbox validation to ensure all contributions are tested, functional, and valuable to maintainers.

## Key Features

- **Bloodhound Red Team Pipeline:** Combines ast-grep and Semgrep to scan for exact vulnerability patterns, followed by a local OpenRouter/Minimax LLM White-Hat audit for precise issue discovery.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Terminator Execution Loop:** A relentless 24/7 autonomous daemon that operates across continuous cycles, maximizing daily API caps strictly without simulated human delays or breaks.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Circular Target Loop & DEV-QA Bounty Loop:** Iteratively revisits analyzed targets to maximize PR outputs and enforces rigorous self-correction via a QA Hardcore Scorer before submission.
- **Token Pool Rotation:** Seamlessly rotates between `GITHUB_SECONDARY_TOKENS` for GET requests to maximize rate limits across intensive hunting rounds.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback, uses an LLM to classify comments, and automatically pushes code fixes or closes PRs.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a comprehensive Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with LLM Providers (Minimax, OpenRouter, etc.) and the GitHub API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a DEV-QA self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Polyglot Sandbox Validation)

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

Configure the agent using `config.yaml` or set the following key environment variables in `.env`:

- `GITHUB_TOKEN`: Primary GitHub Personal Access Token (used for mutations).
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of additional GitHub tokens for GET request rotation.
- `MINIMAX_API_KEY`: Minimax API Key for primary LLM access.
- `MINIMAX_GROUP_ID`: Minimax Group ID.
- `OPENROUTER_API_KEY`: OpenRouter API Key for Bloodhound White-Hat audits (fallback to Minimax).

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Core Operations:**
- `farm_agent run`: Run a single PR pipeline execution.
- `farm_agent target`: Target a specific repository directly.
- `farm_agent hunt`: Run a hunt loop (discover, analyze, create PRs) across multiple repositories.
- `farm_agent hunt-circular`: Run a circular hunt loop using a JSON list of targets.
- `farm_agent superhuman`: Run the 24/7 relentless autonomous daemon.
- `farm_agent patrol`: Monitor open PRs and auto-respond to feedback.
- `farm_agent analyze`: Analyze a repository without generating PRs.
- `farm_agent solve`: Solve open issues in a specific repository.

**System & Maintenance:**
- `farm_agent status`: View system and PR status.
- `farm_agent stats`: View overall performance statistics.
- `farm_agent cleanup`: Clean up temporary files and memory.
- `farm_agent reset-db`: Reset the SQLite database.
- `farm_agent config`: Show active system configuration.
- `farm_agent vips`: Manage VIP repositories.
- `farm_agent templates`: List available contribution templates.
- `farm_agent profile`: Manage agent profiles.
- `farm_agent models`: Show configured LLM models.
- `farm_agent leaderboard`: Show the PR leaderboard.
- `farm_agent notify-test`: Test notification integrations.
- `farm_agent system-status`: Display current system health and status.
- `farm_agent gc`: Garbage collect old database entries.
- `farm_agent janitor`: Auto-close and clean up garbage PRs. *(Note: Currently disabled)*

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
