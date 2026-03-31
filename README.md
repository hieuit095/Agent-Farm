# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen?logo=pytest)](tests/)

## Overview
Farm-Agent is an autonomous AI agent that discovers open-source GitHub repositories, analyzes their code for real bugs and quality issues, generates fixes, and submits pull requests. It operates under a strict anti-farming filter to block trivial changes and disguised its operational patterns behind realistic human behavioral simulation to avoid spam detection.

## Key Features
- **Multi-strategy analysis**: Runs security, code quality, performance, and UI/UX analyzers concurrently against repository file trees.
- **Issue-first pipeline**: Solves open GitHub issues before falling back to static analysis, prioritizing what maintainers actually want fixed.
- **Polyglot Sandbox Validation**: Uses isolated Docker containers to validate patches for Python, Node.js, TypeScript, Rust, Go, Java, C#, Ruby, PHP, C, and C++ before any PR is created.
- **X-Ray Vision**: Builds a local ChromaDB vector index of the repository using a word-frequency embedding model to ensure patches are contextually accurate and don't break downstream code.
- **PR Patrol**: Monitors open PRs for maintainer comments, auto-generates code fixes, answers questions, re-signs CLAs, and addresses style feedback.
- **Anti-Farming Filter**: Drops trivial/low-impact findings and filters out any finding where the title or description contains farming keywords.
- **Super Human Mode**: Operates on a stochastic daily schedule with randomized wake times, typing WPM simulation, probabilistic ghosting, and circadian rhythm simulation.
- **Familiar Grounds (Alumni Repo Prioritization)**: Scores and prioritizes repositories the user has previously contributed to, syncing merged PR history from GitHub.

## System Architecture (High-Level)
Farm-Agent features a Click-based CLI that orchestrates the entire agent pipeline. The main orchestrator (`ContribPipeline` and `SuperHumanLoop`) interacts with an agentic LLM Engine (primarily using Minimax models), a persistent SQLite Memory (with WAL mode), and the GitHub API to discover repositories, fetch code, and submit PRs. The Code Generation Engine utilizes an ephemeral RAG system (ChromaDB) to gain cross-file context and uses Docker to validate patches in a polyglot sandbox environment. An event-driven architecture routes findings through a series of middlewares (RateLimit, DCO, QualityGate) to ensure high-quality and safe contributions.

## Getting Started

### Prerequisites
- Python 3.11 or higher
- Docker 7.1 or higher (for Sandbox Validation)
- GitHub Personal Access Token (with `repo` scope)
- LLM API Key (Minimax API key required by default)

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with dev dependencies:
   ```sh
   make install
   ```

### Environment Variables
Farm-Agent uses a Pydantic-based configuration system `config.yaml` with the following key environment variables as fallbacks:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.

Alternatively, copy `config.example.yaml` to `config.yaml` and configure your credentials.

## Usage

**Run a single hunt round (discover repos, analyze, create PRs):**
```sh
farm_agent hunt --rounds 1 --dry-run
```

**Target a specific repository:**
```sh
farm_agent target https://github.com/owner/repo --dry-run
```

**Solve open issues in a repository:**
```sh
farm_agent solve https://github.com/owner/repo
```

**Run 24/7 autonomous mode (Super Human):**
```sh
farm_agent superhuman
```

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```sh
farm_agent patrol
```

**Scan and auto-close garbage PRs via LLM (Janitor):**
```sh
farm_agent janitor
```

**Show overall statistics:**
```sh
farm_agent stats
```

## Contributing & License
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
