# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. Operating via a relentless 24/7 autonomous engine, it leverages a sophisticated multi-strategy analysis pipeline and polyglot sandbox validation to maximize value for maintainers.

## Key Features

- **Bloodhound Red Team Auditing:** Employs aggressive AST-grep and Semgrep scans in tandem with a multi-model routing pipeline (leveraging OpenRouter and Minimax) to detect deep-seated vulnerabilities.
- **Circular Target Loop:** A continuous cycle of targeting repositories mapped from a persistent database, maximizing exploration while adhering strictly to Git and LLM rate-limit parameters.
- **DEV-QA Bounty Loop:** Dynamically resolves high-impact issues utilizing an advanced internal mechanism that scores the quality of modifications against a project's style guidelines.
- **Token Pool Rotation:** Intelligently rotates GitHub secondary tokens to distribute load and gracefully mitigate strict secondary rate-limits on read-heavy operations.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **PR Patrol:** Autonomously monitors open PRs to field maintainer feedback. It uses LLM classification to comprehend comments and deterministically push code fixes or surrender gracefully when an interaction limit is hit.
- **Terminator Execution Loop:** Orchestrates a 24/7 background process using Docker Compose that relentlessly processes tasks maximizing daily PR quotas without legacy simulated delays.

## System Architecture (High-Level)

The core execution loop operates sequentially across several key stages:
**Discovery** $\rightarrow$ **Gate** $\rightarrow$ **Analysis** $\rightarrow$ **Engine** $\rightarrow$ **Sandbox** $\rightarrow$ **PR**.

Farm-Agent runs entirely on a fast CLI foundation powered by Click. Upon locating a repository, an ephemeral ChromaDB RAG index scopes the environment. The Bloodhound and CodeAnalyzer modules assess the target before dispatching tasks to the Minimax ABAB-powered generative engine. Code variations are tested securely in the isolated Polyglot Sandbox Docker container. Finally, if valid, PRManager forks the repository, commits the validated patch, and pushes the Pull Request.

## Getting Started

### Prerequisites

- **Python:** $\ge$ 3.11
- **Docker:** $\ge$ 7.1 (Required for the Polyglot Sandbox isolated runtime)
- **GitHub PAT:** A valid Personal Access Token with repository permissions
- **LLM API Key:** Minimax (default provider) or an alternative configured via `.env`

### Installation

1. Clone the project:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the necessary development dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configure the agent using `config.yaml` or set the following key environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: Additional GitHub tokens for GET request rotation (comma-separated).
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: API key for OpenRouter, used by the Bloodhound Red Team pipeline.
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications.
- `TELEGRAM_CHAT_ID`: Telegram chat ID for notifications.

Alternatively, copy `config.example.yaml` to `config.yaml` and fill in your details.

## Usage

Interact with Farm-Agent exclusively using the `farm_agent` CLI tool:

**Analyze and discover vulnerabilities directly without generating PRs:**
```bash
farm_agent analyze <url>
```

**Launch an aggressive multi-round discovery and PR campaign:**
```bash
farm_agent hunt --rounds 5
```

**Initiate the 24/7 Terminator execution loop:**
```bash
farm_agent superhuman
```

**Command PR Patrol to address maintainer feedback across open Pull Requests:**
```bash
farm_agent patrol
```

**Target a specific GitHub repository with PRs:**
```bash
farm_agent target https://github.com/owner/repo
```

**Target a specific repository issue for an autonomous fix:**
```bash
farm_agent solve https://github.com/owner/repo
```

## Contributing & License

Farm-Agent is distributed under the [MIT License](LICENSE).
Contributions and improvements are heavily encouraged. To run local checks against your modifications, make sure you execute the suite with:
```bash
python -m pytest tests/unit/
```
