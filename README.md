# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg?logo=pytest)](tests/)

## Overview
Farm-Agent is an autonomous AI agent that discovers open-source GitHub repositories, analyzes their code for real bugs and quality issues, generates fixes, and submits pull requests. It operates under a strict anti-farming filter to block trivial changes and disguises its operational patterns behind realistic human behavioral simulation (Super Human Mode) to avoid spam detection.

## Key Features
- **Multi-Strategy Analysis**: Concurrently runs security, code quality, testing, UI/UX, and performance analyzers against repository file trees.
- **Issue-First Pipeline**: Prioritizes solving open GitHub issues via a deep-solving approach before falling back to static code analysis.
- **Polyglot Sandbox Validation**: Uses ephemeral Docker containers to locally validate code patches across 11 languages (Python, Node.js, TypeScript, Rust, Go, Java, C#, Ruby, PHP, C, C++) *before* a PR is created.
- **X-Ray Vision (RAG)**: Builds a local ChromaDB vector index of the repository using word-frequency embedding models to provide cross-file semantic context during code generation.
- **PR Patrol & Auto-Healing**: Actively monitors open PRs for maintainer comments, auto-generates code fixes for review feedback, answers questions, signs CLAs, and auto-heals failed CI pipeline runs.
- **Anti-Farming Filter**: Implements strict rules and keyword blocking to drop trivial/low-impact findings (e.g., formatting, docs, exploratory tasks).
- **Super Human Mode**: A 24/7 daemon that interleaves hunting and patrolling. It simulates human developers with randomized daily PR quotas, circadian rhythm delays, typing WPM simulation, and probabilistic ghosting.
- **Familiar Grounds (Alumni Sync)**: Prioritizes contributing to VIP repositories where the agent has previously had PRs merged.

## System Architecture (High-Level)
Farm-Agent is orchestrated via a `click`-based CLI and an asynchronous execution pipeline (`asyncio` + `httpx`).
1. **Discovery**: Finds high-star repositories using the GitHub Search API.
2. **Analysis**: Uses an agentic LLM (Minimax, OpenAI, Anthropic, Gemini) to scan the codebase and flag impactful issues.
3. **Generation**: The LLM engine reads files (via tool calling and ChromaDB RAG), generates a fix, applies adversarial self-review, and formats the output as a precise `FileChange` patch.
4. **Validation**: The patch is mounted into a language-specific Docker sandbox. If tests fail, the LLM attempts to self-correct using the error logs.
5. **Submission**: The agent forks the repo, commits the fix with a DCO sign-off, creates a PR, and updates its local SQLite memory (WAL mode).

## Getting Started

### Prerequisites
- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Sandbox Validation)
- **GitHub Personal Access Token:** With `repo` scope
- **LLM API Key:** Minimax, OpenAI, Anthropic, or Gemini

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with dev dependencies:
   ```sh
   make install
   # Or manually: pip install -e .[dev]
   ```

### Environment Variables
Farm-Agent uses a `pydantic-settings` configuration system via `config.yaml`. Copy `config.example.yaml` to `config.yaml` and configure your credentials. The following environment variables can also be used:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID`: Minimax API credentials.
- `GEMINI_API_KEY`: Google Gemini API key.
- `OPENAI_API_KEY`: OpenAI API key.

## Usage

**Run a single hunt round (discover repos, analyze, create PRs):**
```sh
farm_agent hunt --rounds 1 --mode both
```

**Target a specific repository:**
```sh
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```sh
farm_agent solve https://github.com/owner/repo --max-issues 5
```

**Run 24/7 autonomous mode (Super Human):**
```sh
# Start via docker-compose for 24/7 operation:
docker-compose up -d superhuman
# Or via CLI:
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

**Show overall statistics and system status:**
```sh
farm_agent stats
farm_agent system-status
```

## Contributing & License
We welcome contributions! Please see `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

This project is licensed under the MIT License - see the `LICENSE` file for details.