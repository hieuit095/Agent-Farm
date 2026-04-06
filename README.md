# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen?logo=pytest)](tests/)

## Overview
Farm-Agent is an autonomous AI agent that manages the full contribution lifecycle for open-source GitHub repositories. It discovers repositories, analyzes their codebases for real bugs and quality issues, generates context-aware fixes, validates them in a polyglot sandbox, and submits pull requests. It operates under a strict anti-farming filter to block trivial changes and disguises its operational patterns behind realistic human behavioral simulation.

## Key Features
- **Issue-First Pipeline:** Solves open GitHub issues before falling back to static analysis, prioritizing what maintainers actually want fixed.
- **Polyglot Sandbox Validation:** Uses isolated Docker containers to validate patches for Python, Node.js, TypeScript, Rust, Go, Java, C#, Ruby, PHP, C, and C++ before any PR is created.
- **X-Ray Vision (RAG):** Builds a local ChromaDB vector index of the repository using a word-frequency embedding model to ensure patches are contextually accurate and do not break downstream code.
- **PR Patrol:** Monitors open PRs for maintainer comments, auto-generates code fixes, answers questions, re-signs CLAs, and addresses style feedback.
- **Anti-Farming Filter:** Drops trivial/low-impact findings and filters out any finding where the title or description contains farming keywords.
- **Superhuman Mode:** Operates on a stochastic daily schedule with randomized wake times, typing WPM simulation, probabilistic ghosting, and circadian rhythm simulation.
- **Familiar Grounds (Alumni Repo Prioritization):** Scores and prioritizes repositories the user has previously contributed to, syncing merged PR history from GitHub.

## System Architecture (High-Level)
Farm-Agent is built with a Click-based CLI orchestrating the agent pipeline (`ContribPipeline` and `SuperHumanLoop`). It interacts with an agentic LLM Engine (supporting Minimax, Gemini, and others), a persistent SQLite Memory (with WAL mode) for tracking progress and learned outcomes, and the GitHub API for operations. The Code Generation Engine utilizes an ephemeral RAG system (ChromaDB) to gain cross-file context, validates fixes using a Polyglot Sandbox (Docker), and employs an event-driven architecture routed through middlewares (RateLimit, DCO, QualityGate) to ensure high-quality and safe PRs.

## Getting Started

### Prerequisites
- Python 3.11 or higher
- Docker 7.1 or higher (for Sandbox Validation and Superhuman daemon)
- GitHub Personal Access Token (with `repo` scope)
- LLM API Key (Minimax API key or Gemini API key required by default)

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with dependencies:
   ```sh
   make install
   ```

### Environment Variables
Farm-Agent uses a configuration system backed by `config.yaml` with `.env` fallbacks. Key environment variables include:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY` (or `GEMINI_API_KEY`): Your LLM API Key.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID (if applicable).
- `TZ`: Set time zone for Superhuman mode (e.g., `Asia/Ho_Chi_Minh` in docker-compose).

*Alternatively, copy `config.example.yaml` to `config.yaml` and configure your credentials.*

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

**Run 24/7 autonomous mode (Superhuman):**
```sh
docker compose up -d superhuman
```
*(Or manually via `farm_agent superhuman`)*

**Monitor open PRs and auto-respond to feedback (PR Patrol):**
```sh
farm_agent patrol
```

**Scan and auto-close garbage PRs via LLM (Janitor):**
```sh
farm_agent janitor
```

**Show overall statistics and system status:**
```sh
farm_agent stats
farm_agent system-status
```

## Contributing
We welcome contributions! Please refer to the standard open-source boilerplate in `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
