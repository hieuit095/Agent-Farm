# Farm-Agent

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Overview
Farm-Agent is a highly autonomous system designed to automatically discover, analyze, and contribute to open-source projects on GitHub. It operates through a relentless execution loop to evaluate repositories, generate accurate fixes or improvements, validate changes in a securely isolated polyglot sandbox, and autonomously submit Pull Requests.

## Key Features
- **Polyglot Sandbox:** A highly secure, network-isolated Docker sandbox that executes and validates generated code for untrusted repositories across up to 12 languages before submitting a PR.
- **Red Team Bloodhound:** Incorporates Semgrep and LLM-driven vulnerability discovery to aggressively find and map security issues and flaws.
- **PR Patrol:** A monitoring agent that watches open PRs for maintainer feedback, autonomously generates follow-up fixes, and pushes changes automatically.
- **Anti-Farming Filters:** Strict gatekeeping mechanisms that block trivial changes (like simple README typo fixes) or low-impact PRs from being submitted.
- **Multi-Model Routing:** Intelligently routes tasks to the best-suited LLM (e.g., Minimax, Anthropic, Gemini, OpenRouter) based on the requirement (coding, analysis, speed, cost).
- **Local RAG Engine:** Uses ChromaDB for contextually precise fix generation by retrieving relevant local knowledge and context.
- **Terminator Execution Loop:** A relentless, 24/7 continuous operation engine orchestrated via Docker Compose to maximize PR throughput up to daily API quotas.

## High-Level System Architecture
Farm-Agent utilizes a decentralized but orchestrated architecture. It continuously fetches candidate repositories via the GitHub client. Each candidate passes through multiple security and value gates. Once a target is approved, the LLM Generator and Red Team analyzers perform deep analysis to identify issues or bugs. The Engine generates a patch, which is immediately pushed into the Polyglot Sandbox. The Sandbox verifies that the code syntax is correct and tests pass. Finally, the PR Manager creates a fork, pushes the branch, and opens the PR, all tracked inside an SQLite persistent memory.

## Getting Started

### Prerequisites
- Python >= 3.11
- Docker >= 7.1 (for the polyglot sandbox)
- Git

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```
2. Install the project dependencies with developer tools:
   ```bash
   pip install -e ".[dev]"
   ```

### Configuration
1. Copy the example configuration files:
   ```bash
   cp config.example.yaml config.yaml
   cp .env.example .env
   ```
2. Fill out the `.env` file with required API keys, for example:
   ```env
   GITHUB_TOKEN=your_github_token
   MINIMAX_API_KEY=your_minimax_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```
3. Adjust behavior settings in `config.yaml` as needed (e.g., rate limits, enabled analyzers).

## Usage
Farm-Agent provides a rich CLI to control its operations.

**Common Commands:**
- `farm_agent run`: Starts the continuous execution pipeline.
- `farm_agent target <repo>`: Analyzes and targets a specific repository.
- `farm_agent patrol`: Runs the PR patrol to check for maintainer feedback and auto-fix.
- `farm_agent system-status`: Shows system status, memory stats, PRs, and rate limits.
- `farm_agent models`: Lists available LLM models and their capabilities.
- `farm_agent leaderboard`: Shows the contribution leaderboard and success rates.

## Contributing
Please refer to the open issues and submit PRs for any improvements. Make sure to run `make test` and `make lint` before submitting.

## License
This project is licensed under the MIT License.
