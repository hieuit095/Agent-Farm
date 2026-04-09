# 🛠️ Farm-Agent

**Autonomous system that automatically contributes to open source projects on GitHub.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced, autonomous AI agent designed to discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. Operating entirely end-to-end, it integrates directly with the GitHub API, utilizes LLMs (Large Language Models) for intelligent code generation, and safely executes untrusted code within isolated Docker containers to validate fixes before submission.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving existing, open GitHub issues by classifying their solvability before falling back to static code analysis.
- **Polyglot Sandbox Validation:** Uses ephemeral, isolated Docker containers (DooD architecture) to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) ensuring compilation and test success before any PR is created.
- **X-Ray Context Vision (Local RAG):** Builds a local, ephemeral ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files and understand repository architecture.
- **Multi-Strategy Analysis:** Employs concurrent analyzers (like the "Bloodhound" AST-grep scanner) to identify vulnerabilities, code quality issues, and missing documentation.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" command can sweep and delete any PRs classified as low-impact.
- **Super Human Mode:** A 24/7 autonomous daemon that operates on a stochastic daily schedule, complete with simulated human delays (typing time, breaks) and randomized PR quotas to mimic a real developer's workflow.
- **Adversarial Self-Correction Loop:** Employs an independent "Reviewer" agent to critique generated code against security and style guidelines, forcing rewrites if the patch fails strict checks.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Rich-powered CLI (`farm_agent`).
The core engine (`ContribPipeline` / `SuperHumanLoop`) interacts with an LLM Provider (primarily optimized for Minimax ABAB models, with support for OpenAI and Gemini) and the GitHub REST API.
State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

When generating code, the engine pulls repository context via the local ChromaDB RAG index. Crucially, before submission, the generated code patch is validated inside a Polyglot Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop, prompting the LLM with the error logs to fix the issue before finally submitting the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **Git**

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

- `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires `repo` scope).
- `MINIMAX_API_KEY`: Your Minimax API Key for LLM access (or `OPENAI_API_KEY` / `GEMINI_API_KEY` depending on provider).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID (if using Minimax).

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Auto-discover repositories and contribute (Hunt mode):**
```bash
farm_agent hunt --rounds 5 --mode both
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 5
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

**View overall performance statistics:**
```bash
farm_agent stats
```

## Contributing & License

We welcome contributions! Please follow standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
