# Farm-Agent v3.0.0

![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-7.1%2B-blue.svg)

## Overview

Farm-Agent is a highly autonomous AI agent that manages the full open-source contribution lifecycle. Operating strictly 24/7 without delays or organic lunch breaks, it autonomously discovers repositories, analyzes code for vulnerabilities and issues, generates high-quality fixes, and submits Pull Requests via the GitHub API. It leverages advanced Large Language Models (Minimax ABAB as primary, OpenRouter for Red Team auditing) alongside rigid code validation protocols to guarantee functional contributions.

## Key Features

- **Autonomous Contribution Pipeline:** Discovers high-star, active repositories and seamlessly analyzes, generates, and submits Pull Requests.
- **Super Human Mode:** A relentlessly operating background daemon orchestrated via `docker-compose`, engaging in a 'Terminator execution loop' maximizing PR throughput up to daily API caps.
- **Polyglot Sandbox (Guillotine Protocol):** Validates all generated code via a Docker-based sandbox prior to submitting PRs to prevent broken code from being pushed to untrusted repositories.
- **Bloodhound Red Team Analysis:** Incorporates sophisticated code analysis engines including ast-grep and Semgrep patterns to pre-filter repositories before deploying deep LLM-based vulnerability scans.
- **DEV-QA Bounty Loop:** An iterative 3-cycle fin-ops feedback loop where code is generated, critically scored by a rigorous QA model, and refined recursively prior to submission.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops low-impact or exploratory PRs (such as typos, simple formatting, or README fixes).
- **PR Patrol Module:** Autonomously monitors open Farm-Agent PRs, analyzes maintainer review comments, generates code fixes based on feedback, and pushes updates directly.

## System Architecture (High-Level)

The application employs a highly modular and asynchronous architecture orchestrated using Python 3.11+. The core engine (`farm_agent/orchestrator/pipeline.py`) uses `asyncio` for executing parallel contributions. Farm-Agent utilizes a SQLite database (via `aiosqlite` with WAL mode) for state persistence and a Local Retrieval-Augmented Generation (RAG) engine powered by ChromaDB.

For security and isolation, the framework deploys a **DooD (Docker-outside-of-Docker)** architecture. The agent container mounts the host's Docker socket, empowering the Polyglot Sandbox Guillotine to spawn sibling ephemeral containers for untrusted patch validation.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker 7.1+
- GitHub Personal Access Token (with repo access)
- Supported LLM API Key (e.g., `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`)

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **Install Dependencies:**
   Install the package along with development dependencies:
   ```bash
   pip install -e .[dev]
   ```

3. **Environment Setup:**
   Create an `.env` file in the root directory based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Add your required keys to `.env`:
   ```env
   GITHUB_TOKEN=your_github_token
   MINIMAX_API_KEY=your_minimax_key
   OPENROUTER_API_KEY=your_openrouter_key  # Optional, for White-Hat Auditing
   ```

4. **Configuration:**
   Set up your project config by copying `config.example.yaml`:
   ```bash
   cp config.example.yaml config.yaml
   ```

## Usage

Farm-Agent is predominantly operated via its powerful Rich-powered CLI (`farm_agent`).

### Core Commands

- **Run Full Pipeline:** Auto-discover repositories and contribute:
  ```bash
  farm_agent run --language python --stars 100-5000
  ```

- **Target Specific Repository:** Deeply analyze and generate PRs for a single project:
  ```bash
  farm_agent target https://github.com/owner/repo
  ```

- **Solve Existing Issues:** Autonomously fetch, analyze, and resolve open issues in a target repository:
  ```bash
  farm_agent solve https://github.com/owner/repo
  ```

- **Super Human Mode:** Start the 24/7 autonomous engine:
  ```bash
  farm_agent superhuman
  ```
  *(Alternatively, deploy via Docker Compose for production runs: `docker compose up -d`)*

- **Analyze Only:** Perform a dry-run analysis identifying vulnerabilities without submitting a PR:
  ```bash
  farm_agent analyze https://github.com/owner/repo
  ```

- **Project Status and Stats:**
  ```bash
  farm_agent status
  farm_agent stats
  ```

## Contributing

We welcome pull requests! Since Farm-Agent is itself an AI tool that creates pull requests, make sure your human-crafted PRs maintain the codebase standards.
- Ensure to lint the code using `make lint`.
- Add unit tests within the `tests/unit/` directory.
- Verify everything works using `make test`.

## License

This project is licensed under the MIT License - see the `pyproject.toml` for details.