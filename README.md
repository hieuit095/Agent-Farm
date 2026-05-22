# 🛠️ Farm-Agent

**Autonomous AI Agent for Open Source Contributions**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is an advanced autonomous system that automatically discovers open-source GitHub repositories, analyzes them for real bugs or quality issues, generates precise code patches via Large Language Models (LLMs), validates them in polyglot sandboxes, and seamlessly creates pull requests. It operates behind a sophisticated human behavior simulation layer to ensure all contributions provide genuine value to maintainers.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues before falling back to static code analysis, ensuring contributions align with maintainers' immediate needs.
- **Polyglot Sandbox Validation:** Employs an unbypassable "Sandbox Guillotine" using isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) prior to pull request creation. If a patch fails, it invokes an LLM self-correction loop.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees. It features an aggressive Bloodhound Red Team engine (powered by OpenRouter/Semgrep) to uncover deep vulnerabilities.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" command sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and explicitly blocks documentation-only PRs to prevent spamming maintainers.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated coding delays and PR quotas, to mimic a human developer's rhythm.
- **Familiar Grounds:** Tracks VIP repos via Alumni Sync, prioritizing repositories where the agent is already a trusted contributor to leverage existing reputation.

## System Architecture (High-Level)

Farm-Agent's core architecture follows the **DeerFlow pattern**, a custom registry-based agent middleware. Execution is orchestrated via a Click-based CLI. The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with various components:
- **LLM Provider:** Supports MiniMax (default), OpenRouter, Gemini, OpenAI, and Anthropic for intelligent code generation and validation.
- **GitHub REST & GraphQL API:** Facilitates code retrieval, issue fetching, and PR submission.
- **SQLite Persistent Memory:** Maintains state via WAL mode (`aiosqlite`), tracking PR outcomes, findings, rate limits, API usage, and scheduling across pipeline runs.
- **Polyglot Sandbox:** Validates the code dynamically in ephemeral Docker environments to guarantee safety and correctness.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (Required for Polyglot Sandbox Validation)
- **Git**
- **GitHub CLI (`gh`)** (Optional, for token fallback)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and dependencies using `hatch` or `pip`:
   ```bash
   pip install -e .
   ```
   *(For development tools like `pytest` and `ruff`, run `pip install -e .[dev]`)*

### Environment Variables

Configure the agent by setting environment variables in a `.env` file or defining them in a `config.yaml` file (you can copy `.env.example` to `.env` and `config.example.yaml` to `config.yaml`).

**Core API Keys Required:**
- `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires `repo` scope).
- `MINIMAX_API_KEY`: Your Minimax API Key for core LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.

**Optional Variables:**
- `OPENROUTER_API_KEY`: For the Red Team analysis engine.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated fallback tokens for API rate limit mitigation.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: For system notifications.

## Usage

Farm-Agent provides a comprehensive command-line interface (`farm_agent`) for various operational modes:

- **Target a specific repository directly:**
  ```bash
  farm_agent target https://github.com/owner/repo
  ```

- **Solve open issues in a specific repository:**
  ```bash
  farm_agent solve https://github.com/owner/repo
  ```

- **Run a single auto-discovery and contribution cycle:**
  ```bash
  farm_agent run
  ```

- **Run the aggressive multi-round discovery hunt:**
  ```bash
  farm_agent hunt --rounds 5 --delay 30
  ```

- **Run the 24/7 autonomous human-like daemon (Super Human Mode):**
  ```bash
  farm_agent superhuman
  ```

- **Monitor open PRs and auto-respond to feedback (PR Patrol):**
  ```bash
  farm_agent patrol
  ```

- **Analyze a repository without contributing (dry-run style):**
  ```bash
  farm_agent analyze https://github.com/owner/repo
  ```

- **Review performance and statistics:**
  ```bash
  farm_agent stats
  ```

## Contributing & License

We welcome contributions! Please refer to the standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
