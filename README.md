# Farm-Agent

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Beta-yellow.svg)

## Overview
Farm-Agent is an autonomous AI agent that manages the full contribution lifecycle for open-source projects on GitHub. It discovers repositories, analyzes code for issues, generates fixes using LLMs, validates patches in a polyglot Docker sandbox, and automatically submits high-quality pull requests.

## Key Features
- **Autonomous Discovery & Hunting:** Searches GitHub for high-star, active repositories and prioritizes those that historically merge external PRs.
- **Deep Static Analysis & Issue Solving:** Scans codebases for bugs, performance issues, and code quality improvements, or directly solves open GitHub issues.
- **Polyglot Sandbox Validation:** Clones repositories locally and runs generated patches through a secure Docker sandbox to ensure they pass tests and build pipelines before PR creation.
- **Memory & Outcome Learning:** Uses an SQLite-backed memory system to track analyzed repos, submitted PRs, and learned maintainer preferences to optimize future contributions.
- **PR Patrol & Auto-Heal:** Continuously monitors submitted PRs, replies to maintainer feedback, and pushes self-corrected code fixes based on CI failures or review comments.
- **Superhuman Daemon Mode:** Runs 24/7 as a background worker, mimicking organic human developer behavior with dynamic PR quotas, randomized delays, and interleaved hunting/patrolling.

## System Architecture (High-Level)
Farm-Agent operates through a `Click`-based CLI that orchestrates the `ContribPipeline` and `SuperHumanLoop`.
1. **Discovery:** The agent queries the GitHub API to find candidate repositories based on configurable criteria (stars, language, recent activity).
2. **Analysis:** It clones target repositories and uses static analysis and LLM-powered context building to identify actionable findings.
3. **Generation:** The `ContributionGenerator` uses advanced models (like Minimax or GPT) to draft code patches and commit messages.
4. **Validation:** Patches are securely tested in a local Docker sandbox to verify CI/CD integrity.
5. **Submission & Patrol:** The `PRManager` submits the pull request and the agent monitors its lifecycle, auto-responding to feedback and resolving CI failures.

## Getting Started

### Prerequisites
- **Python**: 3.11 or higher
- **Docker**: Version 7.1+ (required for sandbox validation)
- **GitHub Token**: Classic or Fine-Grained token with `repo` scopes.
- **LLM API Key**: Minimax (default), Gemini, OpenAI, or Anthropic.

### Installation
Clone the repository and install the package with development dependencies:

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Variables
Configure the system by creating a `.env` file or exporting the following variables:

```bash
export GITHUB_TOKEN="ghp_your_github_token_here"
export MINIMAX_API_KEY="your_minimax_api_key"
export MINIMAX_GROUP_ID="your_minimax_group_id"
# Optional:
export GEMINI_API_KEY="your_gemini_api_key"
```

## Usage

Farm-Agent provides a rich CLI interface. Below are common commands:

**Run a single targeted contribution:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 3
```

**Start aggressive discovery and contribution (Hunt Mode):**
```bash
farm_agent hunt --rounds 5 --mode both
```

**Check open PRs for feedback and auto-respond (Patrol Mode):**
```bash
farm_agent patrol
```

**Run as a 24/7 autonomous daemon (Superhuman Mode):**
```bash
farm_agent superhuman
# Or via Docker Compose:
docker compose up -d superhuman
```

**View system status and configuration:**
```bash
farm_agent system-status
farm_agent config
```

## Contributing
Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct, development workflow, and the process for submitting pull requests to Farm-Agent.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
