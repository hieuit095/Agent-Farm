# 🛠️ Farm-Agent

**Autonomous Open-Source Contributor**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify bugs or quality issues, generate patches, and submit pull requests. It operates behind a sophisticated execution loop mimicking human behavior to ensure quality and value to maintainers.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving open GitHub issues before falling back to static code analysis, ensuring contributions align with immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches before any Pull Request is created.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs.
- **Super Human Mode:** A 24/7 autonomous daemon that mimics a human developer with unpredictable coding delays, dynamic daily PR quotas, and interleaved Hunt and PR Patrol phases.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Bloodhound Red Team:** An auditing engine leveraging Semgrep rules and OpenRouter-routed LLM models to identify vulnerabilities and code quality issues.
- **Familiar Grounds (VIP Roster):** Learns from past merged PRs to prioritize repositories where the agent is already a trusted contributor.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with LLM Providers (e.g., Minimax, Gemini, OpenAI, Anthropic, Ollama) and the GitHub API.

The pipeline flow follows these sequential steps:
`Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR`

State is persistently managed in an SQLite database (`data/memory.db`), tracking analyzed repositories, submitted PRs, LLM api usage, and learned knowledge base items.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** Minimax API key (default) or other supported providers

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   pip install -e '.[dev]'
   # Or using make:
   make install
   ```

### Environment Variables

Copy `.env.example` to `.env` and configure it, or edit `config.yaml`.

Key Variables:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: Optional list of tokens for GET request rotation.
- `MINIMAX_API_KEY`: Required if using Minimax provider.
- `OPENROUTER_API_KEY`: API key for OpenRouter (used by Bloodhound Red Team audits).

## Usage

Farm-Agent offers a set of CLI commands for different operational modes:

**Run a single round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Hunt mode: aggressive multi-round discovery and contribution:**
```bash
farm_agent hunt
```

**Circular target loop: process targets from `target_repo.json` sequentially:**
```bash
farm_agent hunt-circular
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**View overall performance statistics:**
```bash
farm_agent stats
```

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
