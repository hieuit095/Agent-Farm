# 🛠️ Farm-Agent

**Autonomous System that Automatically Contributes to Open Source Projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a relentless, autonomous AI system designed to automatically discover open-source GitHub repositories, find vulnerabilities or bugs, generate precise fixes, and submit pull requests. Engineered for high-throughput operation, it operates a continuous execution loop (Super Human Mode) backed by a highly secure Sandbox environment to maximize PR contributions.

## Key Features

- **Bloodhound Red Team (Semgrep):** Pre-scans repository file trees for security vulnerabilities using Semgrep rulesets before engaging the LLM, saving tokens and prioritizing critical issues.
- **Polyglot Sandbox Validation:** Patches are rigorously validated inside isolated Docker containers across multiple languages (Python, JavaScript, Rust, Go, TypeScript) prior to Pull Request creation.
- **DEV-QA Bounty Loop:** A multi-cycle agentic loop where patches are self-corrected against strict QA evaluations and sandbox execution results.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that strictly blocks trivial, low-impact, or documentation-only PRs to protect maintainers from low-quality spam.
- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **PR Patrol:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs.
- **Contextual RAG Indexing:** Utilizes local ChromaDB for Retrieval-Augmented Generation, ensuring accurate context resolution across multiple files during code patch generation.
- **Security Disclosure Gate:** Autonomously scans for private disclosure requests (e.g., in `SECURITY.md`) and securely aborts the pipeline to prevent public exposure of critical vulnerabilities.
- **Super Human Mode:** A 24/7 continuous operation engine running relentless discovery and PR submissions up to daily API caps.

## System Architecture (High-Level)

Farm-Agent is orchestrated via a Click-based CLI that runs a relentless execution loop (`ContribPipeline` / `SuperHumanLoop`). The core pipeline uses Minimax ABAB models (default) and OpenRouter (for Bloodhound audits) alongside the GitHub API. It maintains persistent state in a local SQLite database (WAL mode via `aiosqlite`).

During operations, the system filters targets, retrieves context using a ChromaDB RAG index, and iteratively builds patches. These patches must pass the **Sandbox Guillotine**—a Docker-isolated environment that validates the code before the system creates a Pull Request via GitPython and the GitHub REST API.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with repository scopes
- **LLM API Key:** Minimax API key (default) or other supported providers via OpenRouter.

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

Configure the agent using `config.yaml` or set the following environment variables (an example is provided in `.env.example`):

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: OpenRouter API key for Red Team Bloodhound audits.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated secondary tokens for GET request rotation.

## Usage

Farm-Agent provides several CLI commands for operations:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Run continuous operations via Circular Target Loop:**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Run the continuous 24/7 autonomous loop (Super Human Mode):**
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

## Contributing & License

We welcome contributions! Please refer to the `CONTRIBUTING.md` file (if available) or standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
