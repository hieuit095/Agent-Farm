# 🛠️ Farm-Agent v3.0

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous system designed to discover open-source GitHub repositories, identify security vulnerabilities and real bugs, generate precise fixes, and submit pull requests. Operating on a relentless execution loop, it strictly blocks trivial contributions and mandates isolated sandbox validation for every code patch.

## Key Features

- **Bloodhound Red Team Analysis:** Incorporates advanced static analysis with `ast-grep` and `Semgrep` to hunt for CWE-Top-25 and security-audit vulnerabilities, utilizing OpenRouter models for white-hat security auditing.
- **Polyglot Sandbox Validation:** Uses isolated Docker SDK containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and strictly blocks documentation-only PRs to prevent spamming maintainers.
- **DEV-QA Bounty Loop:** A multi-cycle reinforcement mechanism where generated patches are critically scored; rejected patches are fed back as QA lessons until quality standards are met or the cycle aborts.
- **Circular Target Loop:** Deterministic round-robin task orchestration via `target_repo.json` with crash-safe transaction states.
- **Token Pool Rotation:** Built-in secondary GitHub token management to effectively rotate GET requests and bypass aggressive API rate limits.
- **Terminator Execution Loop:** A 24/7 daemon engine orchestrating operations to maximize PR throughput up to API caps, completely devoid of artificial delays or simulated human behaviors.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator interacts with LLM Providers (primarily utilizing Minimax ABAB models, with OpenRouter for White-Hat auditing) and the GitHub REST API. State is persistently managed in a local SQLite database utilizing WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for RAM-only Retrieval-Augmented Generation (RAG) context retrieval. Crucially, before submission, every generated patch undergoes validation within an ephemeral Docker Sandbox on an isolated network. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** Minimax API key (or OpenRouter for Bloodhound mode)

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

Configure the agent using `config.yaml` or set the following key environment variables in an `.env` file:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `OPENROUTER_API_KEY`: API key for Bloodhound Red Team audits.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated tokens for GET request rotation.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run the circular target loop:**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Analyze a repository without contributing:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Run the 24/7 autonomous daemon (Super Human Mode / Terminator Execution Loop):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**View overall performance statistics:**
```bash
farm_agent stats
```

**Show Farm-Agent system status:**
```bash
farm_agent system-status
```

## Contributing & License

We welcome contributions! Please refer to standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
