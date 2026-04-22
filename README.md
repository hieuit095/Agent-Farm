# Farm-Agent

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Requirement](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)](https://www.docker.com/)

## Overview
Farm-Agent is an advanced, fully autonomous system that continuously searches for, analyzes, and contributes to open-source projects on GitHub. By leveraging state-of-the-art Large Language Models and strict validation mechanisms, it identifies bugs, solves issues, and submits high-quality Pull Requests without human intervention.

## Key Features
- **Super Human Mode (Terminator Execution Loop):** A 24/7 daemon operating via `docker-compose` that relentlessly maximizes PR throughput up to daily API caps. No simulated human delays or lunch breaks.
- **Polyglot Sandbox:** Before proposing changes, generated code is rigorously tested within isolated Docker containers (networks: `internet_access`, `sandbox_isolated`) ensuring only valid, functional code is submitted.
- **Bloodhound Red Team Auditing:** Uses `ast-grep` and `Semgrep` combined with OpenRouter White-Hat audit LLMs to unearth and patch complex security and quality flaws.
- **Anti-Farming Filter:** A strict, zero-tolerance gateway that outright blocks trivial, formatting, or pure documentation PRs.
- **PR Patrol & Janitor:** Autonomously monitors open PRs, processes maintainer feedback, generates push-ready code fixes, signs CLAs, and prunes stale or garbage pull requests.
- **Circular Target Loop:** Safely rotates through target repositories guaranteeing crash-safe continuous operation.
- **Token Pool Rotation:** Intelligently balances GitHub GET request limits across `secondary_tokens` while executing write operations under the primary token.

## System Architecture (High-Level)
Farm-Agent follows a strict sequential pipeline:
1. **Discovery:** Scrapes GitHub for active repositories matching defined criteria (language, stars) or targets explicit repositories.
2. **Gate:** The Anti-Farming Filter screens repositories and blocks low-effort PR generation.
3. **Analysis:** The Bloodhound Red Team scans source code for vulnerabilities and structural issues.
4. **Engine:** The Generator utilizes LLMs (Minimax, OpenRouter) to write targeted fixes and feature implementations.
5. **Sandbox:** The Polyglot Sandbox securely builds, runs, and validates the generated code in isolated Docker networks.
6. **PR / Issue Solving:** Finally, the PR Manager forks the repo, commits the verified patches, and opens a comprehensive Pull Request.

## Getting Started

### Prerequisites
- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for the Polyglot Sandbox)
- **Git:** `>= 2.0`

### Installation
Clone the repository and install it in development mode:
```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Variables
Copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` and fill in your keys. NEVER commit your `.env` file to version control.
```ini
# GitHub Authentication (Required)
GITHUB_TOKEN=your_github_personal_access_token

# Secondary GitHub tokens for GET request rotation (Optional, comma-separated)
GITHUB_SECONDARY_TOKENS=token1,token2

# Pipeline & Targeting Options (Optional)
EXCLUDED_LANGUAGES=javascript,typescript

# LLM Provider Keys
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_GROUP_ID=your_minimax_group_id

# OpenRouter (Optional - for Red Team Bloodhound audits)
OPENROUTER_API_KEY=your_openrouter_api_key

# Notifications (Optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
```

## Usage

Farm-Agent provides a rich command-line interface.

**Run the pipeline for auto-discovery:**
```bash
farm_agent run
```

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve specific issues in a repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Start the 24/7 Super Human loop:**
```bash
farm_agent superhuman
```

**Run PR Patrol to respond to maintainer comments:**
```bash
farm_agent patrol
```

*For more commands including `hunt`, `analyze`, `janitor`, `status`, and `system-status`, run:*
```bash
farm_agent --help
```

## Contributing
Contributions are welcome. When submitting a pull request, please ensure that you pass all pre-commit checks and tests. Note the `CONTRIBUTING.md` (if available) for further guidelines.

## License
This project is licensed under the MIT License - see the [pyproject.toml](pyproject.toml) file for details.