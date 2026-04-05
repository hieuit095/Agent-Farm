# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview
Farm-Agent is a fully autonomous AI agent designed to independently discover open-source GitHub repositories, analyze their codebase for real bugs or performance issues, and submit high-quality pull requests. It operates under a strict anti-farming filter that blocks trivial changes (e.g., typos, formatting) and disguises its operational footprint with human-like behavioral simulations, such as delayed typing emulation and circadian rhythm scheduling.

## Key Features
- **Issue-First Pipeline:** Prioritizes resolving actual maintainer-reported open GitHub issues using deep issue-solving heuristics before falling back to generalized static code analysis.
- **Polyglot Sandbox Validation:** Patches are validated securely inside isolated, ephemeral Docker containers (supporting Python, Node.js, Rust, Go, Java, C#, Ruby, PHP, C, and C++) before any PR is generated to guarantee they do not break tests or compilation.
- **Strict Anti-Farming Filter:** A comprehensive keyword and semantic gatekeeper that drops trivial, low-impact findings or purely cosmetic documentation fixes to prevent spam and maintain a high-value contribution profile.
- **PR Patrol:** Autonomously monitors open PRs to read maintainer comments, dynamically generate code fixes, answer technical questions, and address style feedback.
- **Superhuman Mode:** A 24/7 autonomous background daemon simulating a real developer's stochastic schedule, injecting human-like delays, enforcing daily PR quotas, and prioritizing "friendly" repositories.
- **Hybrid Contribution Protocol:** Can intelligently choose to open a polite GitHub Issue proposing a change rather than forcefully submitting a massive PR for sweeping refactors.

## System Architecture (High-Level)
Farm-Agent is orchestrated via a Rich-enhanced Click CLI `farm_agent/cli/main.py`. The primary execution engine (`ContribPipeline` and `SuperHumanLoop`) interacts seamlessly with an LLM Provider (multi-model, default Minimax) to guide the discovery and code generation processes. It leverages a persistent SQLite database acting as a WAL-mode memory buffer to store interaction history and contribution outcomes. The engine employs a localized RAG system built on ChromaDB to trace complex file trees and contextualize patches, validating the final artifacts through the `DockerSandbox`.

## Getting Started

### Prerequisites
- **Python 3.11 or higher**
- **Docker 7.1 or higher** (Mandatory for Sandbox Validation features)
- **GitHub Personal Access Token** (Requires `repo` permissions)
- **LLM API Key** (e.g., Minimax, Gemini, OpenAI)

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package using standard pip (Hatchling is configured as the build backend):
   ```sh
   pip install -e .[dev]
   ```
   *(Or alternatively, if `make` is preferred on your system, use `make install`)*

### Environment Variables
Configure the system by creating a `config.yaml` from the `config.example.yaml` file, or explicitly set the required `.env` variables:
- `GITHUB_TOKEN`: Your valid GitHub Personal Access Token.
- `GEMINI_API_KEY` or `MINIMAX_API_KEY`: Depending on your chosen LLM provider in the config.

## Usage

**Run a Single Pipeline Round:**
Discover, analyze, and generate PRs (append `--dry-run` to preview without submission).
```sh
farm_agent run --dry-run
```

**Target a Specific Repository:**
```sh
farm_agent target https://github.com/owner/repo
```

**Hunt Mode (Multi-Round Aggressive Discovery):**
```sh
farm_agent hunt --rounds 5 --delay 30
```

**Solve Active Open Issues:**
```sh
farm_agent solve https://github.com/owner/repo --max-issues 3
```

**Run Superhuman 24/7 Mode:**
```sh
farm_agent superhuman
```
*Note: Also easily deployable as a background worker via `docker-compose up -d superhuman`.*

**Patrol Open PRs & Janitor Cleanup:**
Auto-respond to reviews or silently eliminate garbage PRs.
```sh
farm_agent patrol
farm_agent janitor
```

**View Overall Leaderboard and Stats:**
```sh
farm_agent stats
farm_agent leaderboard
```

## Contributing & License
We welcome contributions! See the `CONTRIBUTING.md` guidelines for development standards and code of conduct.

This project is open-sourced under the **MIT License**. See the [LICENSE](LICENSE) file for the full legal text.
