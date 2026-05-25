# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It operates behind a sophisticated human behavior simulation layer to ensure all contributions provide genuine value to maintainers and respect standard open-source workflows.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches across multiple languages (Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, and structural analyzers against repository file trees.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The independent "Janitor" sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and strictly blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays and randomized PR quotas to mimic a real developer's circadian rhythm.
- **Security Disclosure Gate:** Scans repository meta files for private disclosure phrases to abort the pipeline and avoid accidental public exposure of security issues.
- **Familiar Grounds (VIP Roster):** Learns from past merged PRs to prioritize repositories where the agent is already a trusted contributor.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Rich CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with an LLM Provider (Minimax, Gemini, OpenAI, Anthropic, or Ollama) and the GitHub REST API. State is persistently managed in a local SQLite database (`memory.db`).

The Code Generation Engine leverages a ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an isolated Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

For a deeper dive, check out the [PROJECT_MAP.md](PROJECT_MAP.md) architectural blueprint.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** e.g., Minimax API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   make install
   # or
   pip install -e '.[dev]'
   ```

### Environment Variables

Configure the agent by copying `config.example.yaml` to `config.yaml` and `.env.example` to `.env`. Set the following key environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access (or `OPENAI_API_KEY`, etc. based on config).
- `TELEGRAM_BOT_TOKEN`: (Optional) For notifications.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes. Use `--help` for more options.

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt --rounds 1
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

**Sweep and auto-close garbage PRs via LLM evaluation (Janitor):**
```bash
farm_agent janitor
```

**View overall performance statistics and VIP Roster:**
```bash
farm_agent stats
farm_agent vips
```

## Contributing & License

We welcome contributions via standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
