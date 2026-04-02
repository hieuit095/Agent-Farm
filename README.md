# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen?logo=pytest)](tests/)

## Overview
Farm-Agent is an autonomous AI agent that discovers open-source GitHub repositories, analyzes their code for bugs and quality issues, generates fixes, and submits pull requests. It operates under an anti-farming filter to block trivial changes and uses human behavioral simulation to avoid spam detection.

## Key Features
- **Anti-Farming Filter**: Evaluates impact levels and screens both titles and descriptions for farming keywords, ensuring only medium-to-critical issues receive PRs while aggressively blocking trivial or cosmetic fixes.
- **Super Human Mode**: A 24/7 autonomous background daemon orchestrated via `farm_agent superhuman` or `docker compose up -d` that mimics human developer schedules by injecting unpredictable delays and dynamic daily PR limits.
- **RAG ChromaDB Integration**: Employs an ephemeral (RAM-only) ChromaDB vector index to perform local Retrieval-Augmented Generation (RAG) during code generation, providing cross-file context for more accurate fixes.

## System Architecture (High-Level)
Farm-Agent utilizes a Click-based CLI acting as the main interface. Its orchestrator (`ContribPipeline` and `SuperHumanLoop`) interacts tightly with:
- An **LLM Engine** (primarily supporting the Minimax models, with fallbacks configured).
- A persistent **Memory** backed by SQLite in Write-Ahead Logging (WAL) mode for safely tracking state.
- The **GitHub API** for discovering repositories, fetching code trees, and submitting Pull Requests.

## Getting Started

### Prerequisites
- Python 3.11 or higher
- Docker 7.1 or higher
- GitHub Personal Access Token (with `repo` scope)
- LLM API Key (Minimax API key used by default)

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
Farm-Agent leverages a Pydantic-based configuration system `config.yaml` with the following key environment variables as fallbacks:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: Your Minimax API Key.
- `MINIMAX_GROUP_ID`: Your Minimax Group ID.

Alternatively, copy `config.example.yaml` to `config.yaml` and configure your credentials.

## Usage

**Run auto-discovery and contribute to matched repos:**
```sh
farm_agent run --dry-run
```

**Target a specific repository:**
```sh
farm_agent target https://github.com/owner/repo --dry-run
```

**Analyze a repository without generating PRs:**
```sh
farm_agent analyze https://github.com/owner/repo
```

**Solve open issues in a repository:**
```sh
farm_agent solve https://github.com/owner/repo
```

**Show status of submitted pull requests:**
```sh
farm_agent status
```

**Show overall statistics:**
```sh
farm_agent stats
```

**Show current configuration:**
```sh
farm_agent config
```

## Contributing & License
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
