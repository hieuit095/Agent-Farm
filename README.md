# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Relentless, precise, and verified.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is an autonomous AI system that actively scans open-source GitHub repositories for bugs, security vulnerabilities, and quality issues. It then uses LLMs to generate patches, validates those patches within isolated Docker sandboxes, and autonomously opens PRs. It's built for maximum throughput and precision to contribute high-quality code at scale.

## Key Features

- **Polyglot Sandbox Validation:** All generated patches are executed and verified inside an isolated Docker container (supporting Python, Node.js, Rust, Go, etc.) before any Pull Request is submitted.
- **Bloodhound Red Team:** Utilizes `ast-grep` and `Semgrep` to pre-scan targets for vulnerabilities, orchestrating deep White-Hat audits with OpenRouter.
- **Circular Target Loop & DEV-QA Bounty Loop:** Iterates through high-value targets, iterating code patches against a strict QA scoring engine until the patch achieves an acceptable quality bar.
- **Terminator Execution Loop:** A 24/7 relentless orchestration mode designed to maximize PR throughput up to daily API quotas.
- **Token Pool Rotation:** Built-in rotation of secondary GitHub API tokens (`GITHUB_SECONDARY_TOKENS`) to circumvent rate limits and maintain high concurrent operation.
- **Local RAG via ChromaDB:** Creates contextual embeddings of codebases using ChromaDB, allowing the LLM generation engine to retrieve highly accurate multi-file context.
- **Anti-Farming Filter:** A strict, zero-tolerance gatekeeper that rejects trivial patches (like simple typos) and aggressively drops documentation-only PRs to prevent maintainer spam.
- **PR Patrol:** Autonomously monitors open PRs to field maintainer feedback, address review comments, and push auto-fixes.

## System Architecture (High-Level)

Farm-Agent is driven by a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline`) directs a multi-stage flow:
1. **Discovery:** Finding high-value repos or pulling from `target_repo.json`.
2. **Analysis:** Deep static scanning with Semgrep/ast-grep.
3. **Engine:** Contextual patch generation with Minimax or OpenRouter models.
4. **Sandbox:** Rigorous Docker-based compilation and testing.
5. **PR:** Final GitHub submission and state persistence via an `aiosqlite` WAL-mode database.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)

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

Configure the agent using `config.yaml` or set the following key environment variables in a `.env` file:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (PAT).
- `GITHUB_SECONDARY_TOKENS`: A comma-separated list of fallback PATs for API rotation.
- `OPENROUTER_API_KEY`: Your OpenRouter API key for the Bloodhound Red Team models.
- `MINIMAX_API_KEY` (Optional): Key for Minimax models, if you intend to use them.

You can start by copying the example configs:
```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

## Usage

Farm-Agent provides several core commands:

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```bash
farm_agent patrol
```

**Run the relentless 24/7 execution loop:**
```bash
farm_agent superhuman
```

**View overall performance statistics and database health:**
```bash
farm_agent stats
# OR
farm_agent system-status
```

## Contributing & License

We welcome contributions via standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
