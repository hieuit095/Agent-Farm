# Farm-Agent v3.0.0

![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Docker](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview
Farm-Agent is a highly autonomous, open-source AI agent designed to discover, analyze, and contribute to open-source projects on GitHub. Operating as a tireless "Super Human" developer, it autonomously hunts for vulnerabilities, identifies code quality issues, solves reported GitHub issues, validates fixes in an isolated polyglot sandbox, and creates well-formed Pull Requests.

## Key Features
- **Auto-Discovery & Hunt Mode:** Systematically discovers high-impact repositories based on star counts, activity, and language profiles to find optimal contribution targets.
- **Red Team Auditing (Bloodhound & Sentinel Radar):** Utilizes `ast-grep` and `Semgrep` to actively scan target repositories for security vulnerabilities and logical flaws before engaging the primary LLMs for resolution.
- **Polyglot Sandbox Validation:** Validates generated patches safely inside language-specific, internet-isolated Docker containers (Node, Python, Rust, Go, Java, etc.) to ensure tests pass and code compiles before a PR is opened.
- **PR Patrol (Auto-Response):** Continuously monitors its open Pull Requests for maintainer feedback, autonomously generating fixes, answering questions, or updating formatting to drive PRs to completion.
- **Terminator Execution Loop (Super Human Mode):** A relentless 24/7 background daemon orchestrating discovery, solving, and patrolling with a strict quota management system, removing legacy human-delay simulations.
- **Anti-Farming Filter:** A stringent zero-tolerance filter that strictly blocks trivial, formatting, and README-only pull requests, ensuring only high-impact code changes are proposed.
- **Multi-Model Routing:** Dynamically routes tasks to optimal LLMs (Minimax, Anthropic, OpenRouter) based on the task's complexity, balancing performance and economy.

## System Architecture (High-Level)
Farm-Agent operates on a sophisticated linear pipeline within a larger autonomous loop:
1. **Discovery:** Scours GitHub for candidate repositories using flexible criteria.
2. **Analysis / Gate:** Pulls down codebases, runs security and quality scanners, checks contributor limits, and applies the Anti-Farming gatekeeper.
3. **Engine:** Leverages multi-model LLMs to craft elegant code fixes or solve specific open issues.
4. **Sandbox:** Safely applies changes and runs project test suites in strict Docker isolation.
5. **PR:** Pushes verified branches and manages PR creation. The Janitor and Patrol sub-systems maintain hygiene on open PRs.

## Getting Started

### Prerequisites
- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for polyglot sandbox environment)
- **Git:** Standard git client

### Installation
Clone the repository and install the project in development mode:
```bash
git clone https://github.com/hieuit095/Agent-Farm.git
cd farm-agent
pip install -e .[dev]
```

### Environment Variables
Farm-Agent uses environment variables and/or a configuration file. Copy the example templates to get started:
```bash
cp config.example.yaml config.yaml
cp .env.example .env
```
Ensure the following variables are set in your `.env` file:
- `GITHUB_TOKEN` - Your primary GitHub personal access token (with `repo` access).
- `MINIMAX_API_KEY` - Your Minimax API Key (primary code generation model).
- `OPENROUTER_API_KEY` - Used for Bloodhound White-Hat audits (optional, falls back to Minimax).
- `GITHUB_SECONDARY_TOKENS` - (Optional) Comma-separated list of secondary tokens for API rate-limit rotation.

## Usage

Farm-Agent provides a rich CLI interface. Below are a few common operational commands.

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Run an aggressive "Hunt" across the GitHub ecosystem:**
```bash
farm_agent hunt --mode both --rounds 5 --delay 30
```

**Analyze a repository without contributing (Dry Run):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Solve open issues for a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 5
```

**Run the 24/7 Super Human Mode daemon:**
```bash
farm_agent superhuman
```

**Check PR submission status:**
```bash
farm_agent status
```

## Contributing & License
Contributions are welcome! Please ensure that you check the project's tests and follow the formatting standards (Ruff is heavily enforced).

This project is licensed under the MIT License - see the `LICENSE` file for details.
