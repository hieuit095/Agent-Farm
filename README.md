# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Real Bugs, Real Code, Real Value.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is an advanced, autonomous system designed to automatically discover open-source GitHub repositories, identify vulnerabilities or bugs via static analysis and semantic parsing, generate precise code patches, validate them in isolated execution environments, and submit high-quality Pull Requests or Issues.

## Key Features

- **Bloodhound Red Team Analysis:** Performs vulnerability discovery using integrated tools like Semgrep and LLM-powered White-Hat auditing (via OpenRouter/Minimax).
- **Polyglot Sandbox Validation:** Validates generated code patches within heavily restricted, ephemeral Docker containers (supporting multiple languages like Python, JavaScript, Go, Rust, etc.) before submitting any PR.
- **Circular Target Loop:** Prioritizes continuous discovery and cyclical patching, integrating a QA feedback loop that records and rectifies failures directly into a local knowledge base.
- **PR Patrol:** Autonomously monitors open Pull Requests for maintainer feedback, correctly classifies comments, and generates appropriate follow-up commits to resolve PR review suggestions.
- **Strict Anti-Farming & Governance Gates:** Enforces zero-tolerance policies against trivial PRs (e.g., typos, pure documentation changes). It strictly ignores meta-files (like `.github/workflows`, `package.json`), respects AI bans (`AI_POLICY.md`), and handles private security disclosures.
- **X-Ray Context Vision:** Leverages an ephemeral ChromaDB-backed Retrieval-Augmented Generation (RAG) index to ensure contextual accuracy across files while fixing bugs.

## System Architecture (High-Level)

The system orchestrates operations via a robust Click-based CLI (`farm_agent`), routing commands into a core orchestration engine (`ContribPipeline`).

1. **Discovery:** Scans repositories (or targets specific ones) and evaluates them against internal compliance gates (Maintainer Vibe, Contributor restrictions).
2. **Analysis:** Runs code through `CodeAnalyzer` and `BloodhoundAnalyzer` to find actionable, high-impact bugs.
3. **Generation:** An LLM routing layer dynamically assigns tasks to capable models (e.g., MiniMax ABAB, OpenRouter models) to generate code patches.
4. **Validation:** The `DockerSandbox` runs the patched code. If it fails tests or linting, the agent self-corrects based on error output.
5. **Submission:** Successful patches are submitted as PRs or Issues via `GitHubClient`. State and history are persistently saved to an SQLite database (`data/memory.db`).

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Strict requirement for the execution sandbox)
- **GitHub PAT:** A Personal Access Token with at least `repo` and `read:org` scopes.

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

Configure the agent via `config.yaml` or by setting `.env` variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token (Required).
- `MINIMAX_API_KEY`: Your Minimax API Key for standard LLM access (Required if using Minimax).
- `OPENROUTER_API_KEY`: OpenRouter API Key for Red Team White-Hat audits (Optional).

*(See `.env.example` and `config.example.yaml` for more details.)*

## Usage

Farm-Agent is driven by CLI commands:

**Run a single pipeline pass on discovered repos:**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Run an aggressive multi-round discovery and contribution session:**
```bash
farm_agent hunt --rounds 3
```

**Solve open issues in a targeted repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Monitor open PRs and auto-respond to code review feedback:**
```bash
farm_agent patrol
```

**Run the 24/7 relentless Super Human loop:**
```bash
farm_agent superhuman
```

**View leaderboard and performance metrics:**
```bash
farm_agent leaderboard
```

## Contributing & License

Standard open-source pull request workflows apply. Refer to the project's internal development guidelines.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
