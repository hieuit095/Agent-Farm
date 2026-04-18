# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It operates behind a sophisticated execution loop to ensure all contributions provide genuine value to maintainers while strictly respecting API rate limits and quotas.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode (Terminator Execution Loop):** A 24/7 relentless autonomous daemon that cycles through hunt and patrol loops, maximizing API limits without artificial human-like delays.
- **Target Loops:** Offers circular target loop (`hunt-circular`) driven by a database to effectively process repositories round-robin style.
- **Familiar Grounds:** Learns from past merged PRs to prioritize repositories where the agent is already a trusted contributor (VIP Alumni tracking).

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with an LLM Provider (primarily utilizing Minimax ABAB models, with OpenRouter for White-Hat Auditing) and the GitHub REST API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** Minimax API key (default) or supported alternatives (e.g., OpenRouter)

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

Configure the agent using `config.yaml` or set the following key environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: OpenRouter API Key for fallback/White-Hat Auditing.

Alternatively, copy `config.example.yaml` to `config.yaml` and fill in your details.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
```

**Circular Target Loop (Database-driven processing):**
```bash
farm_agent hunt-circular
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Run the 24/7 autonomous daemon (Super Human Mode / Terminator Loop):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Sweep and auto-close garbage PRs via LLM evaluation (Janitor):**
```bash
farm_agent janitor
```

**View overall performance statistics:**
```bash
farm_agent stats
```

## Contributing & License

We welcome contributions! Please refer to the `CONTRIBUTING.md` file (if available) or standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.