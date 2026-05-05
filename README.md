# 🛠️ Farm-Agent

**Autonomous System that Automatically Contributes to Open Source Projects on GitHub**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Build System: Hatchling](https://img.shields.io/badge/build%20system-hatchling-000000)](https://hatch.pypa.io/)

## Overview

Farm-Agent is a highly advanced, autonomous agent system designed to analyze open-source GitHub repositories and contribute code directly. It orchestrates a sophisticated pipeline utilizing Large Language Models (LLMs) and a polyglot sandbox to ensure code quality and accuracy. Operating in a relentless "Terminator execution loop", Farm-Agent can discover repositories, run static analysis to find issues, solve existing GitHub issues, generate patches, validate them in a secure sandbox, and submit fully formed Pull Requests.

## Key Features

- **Hunt Mode (`hunt`):** Automatically searches GitHub for active repositories, clones them, analyzes code for bugs, and creates PRs.
- **Direct Targeting (`target`):** Aim the pipeline directly at a specific repository for immediate code contributions.
- **Issue Solver (`solve`):** Identifies open issues on a target repository, classifies them, and automatically generates and submits solutions.
- **Super Human Mode (`superhuman`):** Runs the pipeline 24/7 as an organic daemon loop, relentlessly maximizing PR throughput while navigating rate limits.
- **PR Patrol (`patrol`):** Monitors open Farm-Agent PRs for maintainer feedback, generating and pushing code fixes autonomously.
- **Bloodhound Red Team Analysis:** Routes code scanning through advanced Red Team LLM models (e.g., via OpenRouter) and Semgrep rulesets for deep security discovery.
- **Polyglot Sandbox Validation:** Validates generated patches securely in isolated Docker environments to ensure no PRs break tests or linters.
- **Token Pool Rotation:** Utilizes multiple secondary GitHub tokens to manage GET request rate limits across the pipeline.

## System Architecture

Farm-Agent is driven by the **`farm_agent`** CLI, coordinating the execution of the main **`ContribPipeline`** orchestrator. The central pipeline logic operates sequentially:

**Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**

1. **Discovery:** Finds targets using the GitHub API (with token rotation) or reads specific targets.
2. **Gate:** Checks quotas, blacklists, and security disclosure policies.
3. **Analysis:** Deeply scans code using the primary LLM provider (like Minimax) or Bloodhound.
4. **Engine:** The Generator synthesizes fixes or features for the identified issues.
5. **Sandbox:** Generates code is safely executed and tested in isolated Docker environments.
6. **PR:** Commits are pushed, and Pull Requests are generated using Git.

State is kept consistently and persistently via a local **SQLite database** (`memory.db`).

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** 7.1+ (Required for Polyglot Sandbox Validation)
- **GitHub PAT:** A Personal Access Token with `repo` scope.
- **LLM API Key:** Minimax API key (default) or other supported providers.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

Configure the agent via `config.yaml` or set required variables in `.env`:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (for write access).
- `MINIMAX_API_KEY`: Your LLM access key (if using the default minimax provider).
- `GITHUB_SECONDARY_TOKENS`: Comma-separated list of secondary tokens to rotate read API usage.

Alternatively, copy `.env.example` to `.env` and `config.example.yaml` to `config.yaml`.

## Usage

Here are some core CLI commands you can run via `farm_agent`:

**Run a Hunt round (discover, analyze, create PRs):**
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

**Run the 24/7 continuous daemon loop:**
```bash
farm_agent superhuman
```

**Check open PRs for review feedback and auto-respond:**
```bash
farm_agent patrol
```

**Show statistics of submitted PRs:**
```bash
farm_agent stats
```

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
