# 🛠️ Farm-Agent

**Autonomous, Precision Open Source Contributor for GitHub Ecosystems**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a relentless, autonomous system designed to discover GitHub repositories, analyze them for vulnerabilities or quality issues, generate patches, validate them in a secure polyglot sandbox, and submit fully vetted Pull Requests. Version 3.0+ introduces high-throughput, non-stop operation loops and stringent quality gates.

## Key Features

- **Bloodhound Red Team & DEV-QA Loop:** Utilizes integrated ast-grep and Semgrep pipelines paired with an LLM generator to discover, write, and critique code prior to execution.
- **Polyglot Sandbox Validation:** Uses Docker containers to strictly validate and execute generated code across multiple languages before PR submission, enforcing zero tolerance for regressions.
- **Terminator Execution Loop:** Orchestrated 24/7 autonomous operation that maximizes API rate limits with continuous discovery and PR generation.
- **Anti-Farming Filter:** A strict, non-bypassable gatekeeper that outright rejects trivial formatting, typo fixes, or documentation-only PRs to prevent maintainer spam.
- **PR Patrol:** Autonomously monitors open Farm-Agent PRs for review comments, leverages LLMs to classify the feedback, and automatically pushes follow-up code fixes to the branch.
- **Local RAG Integration:** Employs ChromaDB to build local code embeddings for contextually accurate cross-file fixes.

## System Architecture (High-Level)

The system orchestrator (`ContribPipeline`) drives the core execution flow: **Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**.
Farm-Agent supports multi-model LLM generation (routing to Minimax, OpenRouter, Gemini, OpenAI, Anthropic, or Ollama) using an internal task router. Target code is pulled into an ephemeral, tightly constrained Docker environment where dependencies are installed and test suites executed. Only validated code passes to the PR Manager. State and quotas are tracked securely in a local WAL-enabled SQLite database (`memory.db`).

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (mandatory for Polyglot Sandbox Validation)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies via `pip`:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configuration is driven by `.env` or `config.yaml`. Copy the examples:
```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

**Essential `.env` variables:**
- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (PAT) for PR and Issue creation.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated PATs for GET request load balancing.
- `MINIMAX_API_KEY`: API Key for the default Minimax LLM.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: (Optional) Used for Bloodhound White-Hat auditing routing.

## Usage

Interact with Farm-Agent primarily through its comprehensive CLI.

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Run a complete hunt loop (Discover -> Analyze -> PR):**
```bash
farm_agent hunt
```

**Execute the continuous, relentless Terminator loop:**
```bash
farm_agent hunt-circular
```

**Solve a specific GitHub Issue:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Monitor and respond to PR feedback (PR Patrol):**
```bash
farm_agent patrol
```

**View overall system stats and memory database:**
```bash
farm_agent system-status
```

## Contributing & License

Contributions are welcome! Please ensure you verify your changes and adhere to the project's Ruff formatting guidelines.

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more details.
