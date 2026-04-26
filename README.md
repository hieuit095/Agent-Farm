# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous system designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It leverages a rigorous execution loop to ensure all code contributions are functionally correct and provide genuine value to maintainers.

## Key Features

- **Polyglot Sandbox Validation:** Uses isolated Docker containers to execute and validate generated patches (across Python, Node.js, Rust, Go, Java, Ruby, PHP, C, C++, C# and more) before any Pull Request is created.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.
- **Multi-Strategy Analysis:** Concurrently runs security, code quality, documentation, and UI/UX analyzers against repository file trees. Features a Bloodhound Red Team pipeline using OpenRouter/Minimax for White-Hat audits and Semgrep for vulnerability discovery.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.
- **Super Human Mode:** A 24/7 autonomous daemon that operates relentless Terminator execution loops to maximize PR throughput, incorporating token pool rotation and API limit handling.
- **Circular Target Loop:** Processes curated targets in a crash-safe rotation loop for continuous discovery and contribution.
- **Familiar Grounds (VIP Roster):** Learns from past merged PRs to prioritize repositories where the agent is already a trusted contributor.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with an LLM Provider (Minimax ABAB models, with fallbacks to other providers like OpenRouter) and the GitHub REST/GraphQL API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When analyzing code or solving issues, the Code Generation Engine uses an ephemeral ChromaDB vector store for context retrieval. Crucially, before submission, the generated code patch is validated inside an ephemeral Docker Sandbox operating on isolated networks. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** 7.1+ (Required for Polyglot Sandbox Validation and network isolation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Key:** Minimax API key (default) or other supported providers (Gemini, OpenAI, Anthropic, Ollama, OpenRouter).

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

### Configuration

Configure the agent using `config.yaml` or set the following key environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary tokens for GET request rotation.
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access.
- `OPENROUTER_API_KEY`: OpenRouter API Key for Bloodhound White-Hat audits.

Alternatively, copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` and fill in your details.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Auto-discover repositories and contribute:**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target <url>
```

**Analyze a repo without contributing:**
```bash
farm_agent analyze <url>
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve <url>
```

**Hunt mode (auto-discover and run full pipeline aggressively):**
```bash
farm_agent hunt --rounds 5
```

**Circular Target Loop (continuous rotation of specified targets):**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Show overall statistics or status:**
```bash
farm_agent stats
farm_agent status
```

**View your VIP Roster (Alumni sync):**
```bash
farm_agent vips
```

## Contributing & License

We welcome contributions! Please refer to the `CONTRIBUTING.md` file (if available) or standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `pyproject.toml` or `LICENSE` file for details.
