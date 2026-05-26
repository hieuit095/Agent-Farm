# 🛠️ Farm-Agent

**Autonomous Agent Orchestration — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to automatically contribute to open-source projects on GitHub. It discovers repositories, identifies bugs or quality issues, generates precise code patches, and submits pull requests, operating with simulated human-like behavior to ensure all contributions provide genuine value to maintainers.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays and randomized PR quotas to mimic a real developer's circadian rhythm.
- **Security Disclosure Gate:** Scans repository meta files for private disclosure instructions and aborts the pipeline if found to avoid publicizing sensitive security issues.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Rich CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with an LLM Provider (via multi-model routing, defaults to Minimax, OpenAI, Anthropic, Gemini, or Ollama) and the GitHub REST/GraphQL APIs. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** >=3.11
- **Docker:** >=7.1 (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo`, `read:org`, and `workflow` scopes.
- **LLM API Key:** e.g., Minimax API key, OpenAI API key, or other supported alternatives.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   make install
   # Or manually: pip install -e '.[dev]'
   ```

### Environment Variables

Configure the agent using `config.yaml` (copy from `config.example.yaml`) or set the following key environment variables in a `.env` file (copy from `.env.example`):

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key (if using Minimax).
- `OPENROUTER_API_KEY`: For Bloodhound Red Team pipeline.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For push notifications.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Hunt mode (auto-discover repos and contribute aggressively in multiple rounds):**
```bash
farm_agent hunt --rounds 5 --mode both
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Analyze a repository without creating contributions:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Sweep and auto-close garbage PRs via LLM evaluation (Janitor):**
```bash
farm_agent janitor
```

**View overall performance statistics:**
```bash
farm_agent stats
```

## Contributing

We welcome contributions! Please refer to the `CONTRIBUTING.md` file (if available) or standard open-source pull request workflows. Code style enforces Ruff with a 100-character line limit. Ensure tests pass before submitting your PR.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.