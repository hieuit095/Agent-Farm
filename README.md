# 🛠️ Farm-Agent

**Autonomous Agent Orchestration — Polyglot, 24/7, Zero-Friction Open Source Contributions.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent (v3.0.0+) is an advanced, autonomous system designed to automatically discover repositories on GitHub, analyze their codebases or open issues, generate patches using large language models, and submit validated pull requests. It leverages a rigorous polyglot sandbox environment to ensure every contribution is highly accurate and free of regressions.

## Key Features

- **Polyglot Sandbox Validation:** Patches are rigorously tested within isolated, offline Docker containers (`agent-farm` internal network) across 12 supported languages to guarantee functional correctness before PR submission.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., simple formatting) and strictly blocks documentation-only PRs, preventing repository spam.
- **Bloodhound Red Team Audits:** Employs advanced scanning (ast-grep, Semgrep) combined with secondary LLM analysis via OpenRouter to unearth deeper vulnerabilities and code quality improvements.
- **PR Patrol & Auto-Responder:** Monitors open Farm-Agent pull requests for maintainer feedback, classifies comments with LLMs, and autonomously generates and pushes code fixes or conversational replies.
- **Super Human Mode:** A relentless, 24/7 autonomous loop that operates continuously to maximize throughput up to daily API caps, efficiently interleaving repository hunts with PR patrol duties.
- **Terminator Execution Loop & Token Pool Rotation:** Employs robust error handling and rotates multiple secondary GitHub tokens to circumvent secondary rate limits, ensuring continuous execution.
- **Alumni Sync & VIP Roster:** Learns from successfully merged PRs, prioritizing friendly repositories where the agent has established a trusted contribution history.

## System Architecture (High-Level)

Farm-Agent orchestrates its core execution loop starting from an interactive CLI built with `click`. The **ContribPipeline** serves as the master orchestrator, driving the system through several phases:
1. **Discovery:** Identifies target repositories via GitHub Search or specified URLs.
2. **Gate:** Enforces strict codebase boundaries (Security MD checks, skipping excluded files) to avoid touching protected zones.
3. **Analysis:** The `CodeAnalyzer` coordinates strategies (or the `IssueSolver` identifies solvable GitHub issues).
4. **Engine:** The `ContributionGenerator` formulates solutions, utilizing a local ChromaDB-backed RAG engine for deep context retrieval.
5. **Sandbox:** The generated patch undergoes execution and testing inside the offline `DockerSandbox`.
6. **PR:** Finalized patches are pushed to forks via the `PRManager`, creating the final pull request.

Data persistence is managed locally with a persistent SQLite database (WAL mode enabled via `aiosqlite`), tracking PR outcomes, analyzed repositories, quotas, and agent memory.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for the Polyglot Sandbox Validation container execution)

### Installation

1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package alongside development dependencies (uses Hatchling backend):
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configure the system by copying `.env.example` to `.env`. Key required variables include:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (requires `repo`, `read:org`, and `workflow` scopes).
- `GITHUB_SECONDARY_TOKENS`: Comma-separated secondary tokens to distribute read-only API load.
- `MINIMAX_API_KEY`: Primary API key for the Minimax ABAB models.
- `OPENROUTER_API_KEY`: (Optional) Used by the Bloodhound Red Team pipeline for White-Hat audits.
- `EXCLUDED_LANGUAGES`: (Optional) Comma-separated list to ignore specific languages.

Additional logging and configuration settings can be found in `config.yaml`.

## Usage

Farm-Agent provides several powerful CLI entry points:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Run the relentless 24/7 Super Human loop:**
```bash
farm_agent superhuman
```

**Target a specific repository url directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve solvable open issues on a repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Review active pull requests and respond to maintainer comments:**
```bash
farm_agent patrol
```

**Clean up closed/merged forks to save space:**
```bash
farm_agent cleanup
```

**Check system status (memory stats, rate limits, recent PRs):**
```bash
farm_agent system-status
```

## Contributing & License

Farm-Agent is open-source software licensed under the **MIT License**. See the `LICENSE` file for full details.
