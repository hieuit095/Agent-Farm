# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced system designed to autonomously discover open-source GitHub repositories, identify real bugs or quality issues, generate precise fixes, and submit pull requests. It operates behind a sophisticated architecture, leveraging Red Team analysis and rigorous QA gates, to ensure all contributions provide genuine value to maintainers.

## Key Features

- **Bloodhound Red Team Protocol:** Utilizes a dual-radar system (`ast-grep` and Semgrep) to pinpoint exact buggy snippets as a pre-filter, followed by OpenRouter White-Hat validation, ensuring high-accuracy patches and minimizing false positives.
- **DEV-QA Bounty Loop:** Employs a 10-cycle adversarial quality gate. The Developer Agent uses Chain-of-Thought planning to solve issues, while the QA Hardcore Scorer evaluates patches (on Logic, Architecture, Security, etc.) requiring a strict 9.0/10.0 score to pass.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers (Docker-outside-of-Docker / DooD architecture) to execute and validate generated patches (across Python, Node.js, Rust, Go, etc.) before any Pull Request is created.
- **Circular Target Loop:** Features a deterministic round-robin targeting system (`target_repo.json`) that continuously loops through repos, using crash-safe rotation and persistent tracking.
- **Terminator Execution Loop:** A relentless continuous operation daemon that interleaves hunting and PR patrol with automated Knowledge Base garbage collection, dropping simulated human delays in favor of pure efficiency.
- **Multi-Token Rotation:** Distributes GitHub API load across a pool of secondary tokens for read operations, avoiding rate limits.
- **PR Patrol & Janitor:** Autonomously monitors open PRs for maintainer feedback to push auto-fixes, answer questions, and sign CLAs. The "Janitor" sweeps and deletes any PRs classified as low-quality or garbage.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops trivial findings (e.g., typos, formatting) and blocks documentation-only PRs to prevent spamming maintainers.

## System Architecture (High-Level)

Farm-Agent orchestrates its pipeline via a Click-based CLI (`farm_agent`). The core orchestrator (`ContribPipeline` / `SuperHumanLoop`) interacts with LLM Providers (primarily utilizing Minimax ABAB models, with OpenRouter for Red Team audits) and the GitHub REST/GraphQL API. State is persistently managed in an SQLite database using WAL mode (`aiosqlite`).

The execution flows from target discovery (or circular JSON targeting), leading to the Bloodhound Red Team performing deep vulnerability scans. Detected issues enter the DEV-QA Bounty Loop, where fixes are iteratively generated using RAG via ChromaDB for cross-file context. Crucially, before submission, patches are validated inside an ephemeral Docker Sandbox. If the patch fails tests or linters, the agent enters a self-correction loop before attempting to submit the PR.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope
- **LLM API Keys:**
  - Minimax API key (`MINIMAX_API_KEY`) and Group ID (`MINIMAX_GROUP_ID`) for primary LLM access.
  - (Optional) OpenRouter API key (`OPENROUTER_API_KEY`) for Red Team validation.

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

Configure the agent using `config.yaml` or set the following environment variables (defined in `.env`):

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: Comma-separated secondary tokens for load distribution.
- `MINIMAX_API_KEY`: Your Minimax API Key.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.
- `OPENROUTER_API_KEY`: Your OpenRouter API Key for Red Team audits.

Alternatively, copy `config.example.yaml` to `config.yaml` and fill in your details.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Circular Target Loop (bounty loop targeting via target_repo.json):**
```bash
farm_agent hunt-circular
```

**Run the relentless continuous daemon (Terminator Mode):**
```bash
farm_agent superhuman
```

**Run a single hunt round (discover, analyze, create PRs):**
```bash
farm_agent hunt
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
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
