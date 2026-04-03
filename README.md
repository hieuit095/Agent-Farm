# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen?logo=pytest)](tests/)

## Overview
Farm-Agent is an autonomous AI agent that discovers open-source GitHub repositories, analyzes their code for issues, generates patches, and submits pull requests. It leverages multiple LLM providers and semantic context via vector search to write meaningful, tested fixes while using simulated behavior to operate organically.

## Key Features
- **Auto-Discovery & Contribution (`farm_agent run` / `farm_agent hunt`)**: Automatically discovers GitHub repositories matching configured criteria (language, stars) and contributes code fixes.
- **Targeted Solutions (`farm_agent target <url>` / `farm_agent solve <url>`)**: Target specific repositories to analyze for code quality issues or solve existing open GitHub issues.
- **Codebase Analysis (`farm_agent analyze <url>`)**: Perform static analysis and LLM-based issue scanning without submitting PRs.
- **Status & Statistics (`farm_agent status` / `farm_agent stats`)**: Track the merge status of submitted PRs and view overall contribution statistics.
- **Configuration Management (`farm_agent config`)**: Easily view and manage your current configuration and limits.
- **Super Human Mode (`farm_agent superhuman`)**: An organic 24/7 operational loop mimicking a human developer with dynamic PR quotas, circadian rhythm simulation, and random typing delays.

## System Architecture (High-Level)
Farm-Agent is driven by a powerful CLI (`click`, `rich`) orchestrating asynchronous workflows via `httpx` and `aiosqlite`. The application interacts with GitHub's REST API to discover repositories and manage Pull Requests. Code understanding is powered by LLM models (e.g., Minimax, Gemini) and augmented by an ephemeral local RAG engine (`chromadb`) for semantic code search. Code execution and validation occur in isolated Docker containers (`docker`) ensuring patches compile and tests pass before PR submission.

## Getting Started

### Prerequisites
- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (for Sandbox Validation)
- GitHub Personal Access Token (with `repo` scope)
- LLM API Key (e.g., Gemini, Minimax, OpenAI, or Anthropic)

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with developer dependencies:
   ```sh
   make install
   ```

### Environment Variables
Configure the application by creating a `.env` file or directly exporting these variables:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `GEMINI_API_KEY`: Your Gemini API Key (or `MINIMAX_API_KEY`, etc., depending on your chosen LLM).
Alternatively, copy `config.example.yaml` to `config.yaml` to set up your profiles and keys.

## Usage

**Auto-discover repositories and contribute:**
```sh
farm_agent run
```

**Target a specific repository:**
```sh
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a repository:**
```sh
farm_agent solve https://github.com/owner/repo
```

**Analyze a repository without contributing:**
```sh
farm_agent analyze https://github.com/owner/repo
```

**Run 24/7 autonomous mode (Super Human):**
```sh
farm_agent superhuman
```

**Show status of submitted PRs:**
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

## Contributing
We welcome contributions! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for details on our code of conduct and the process for submitting pull requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
