# Farm-Agent 🚜🤖

![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Docker Version](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)
![Hatchling Build](https://img.shields.io/badge/build-hatchling-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

**Farm-Agent** is an autonomous system that automatically contributes to open source projects on GitHub. It operates systematically to discover repositories, identify issues, write code, run verification tests, and open fully-formed Pull Requests without human intervention.

## Key Features

-   **Auto-discovery of Repositories:** Continuously scans GitHub for high-impact target repositories based on configurable parameters (stars, activity, languages).
-   **Automated Issue Solving & Analysis:** Employs static analysis tools and Large Language Models to discover bugs, UI/UX issues, and code quality improvements, or directly solves open issues.
-   **Red-Team Auditing (Bloodhound):** Proactively audits repositories using Bloodhound's white-hat red team pipeline (using OpenRouter/Dolphin-Mistral) for security vulnerabilities and weaknesses.
-   **Sandbox Validation:** Validates generated patches safely inside an isolated Polyglot Docker Sandbox before ever submitting them.
-   **Autonomous PR Generation:** Orchestrates forks, commits, and creates Pull Requests with conventional commits and descriptive write-ups.
-   **Terminator Execution Loop:** A continuous, relentless 24/7 background execution loop designed to maximize PR throughput using all available secondary API limits.
-   **PR Patrol:** Automatically monitors maintainer feedback on created PRs, categorizes comments using LLMs, and pushes real-time code fixes or responses.

## System Architecture (High-Level)

The agent operates through a sequential 6-step core execution loop orchestrated via `farm_agent.orchestrator.pipeline`:

1.  **Discovery:** Searches GitHub for repositories meeting criteria (or picks targets from the Circular Target Loop).
2.  **Gate:** Filters repositories against anti-farming rules and persistent blacklists to prevent trivial/spammy PRs.
3.  **Analysis:** Scans the codebase using Red Team tools (Bloodhound with Sentinel Radar/Semgrep) or reads target issues.
4.  **Engine:** Uses an LLM provider (Minimax, OpenRouter, Gemini, etc.) to generate precise git merge-diff patches to solve the findings.
5.  **Sandbox:** Spins up a polyglot, network-isolated Docker container to apply the patches and verify syntax and unit tests.
6.  **PR:** Forks the repository, pushes the verified commit, signs the CLA (if required), and opens a Pull Request on GitHub.

## Getting Started

### Prerequisites
- Python `>= 3.11`
- Docker `>= 7.1` (Required for Sandbox environments)

### Installation
Clone the canonical repository and install dependencies in development mode:

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Variables
The application requires the following environment variables (defined in a `.env` file):

-   `GITHUB_TOKEN`: Your primary GitHub Personal Access Token.
-   `GITHUB_SECONDARY_TOKENS` (Optional): Comma-separated tokens for rotating read API requests.
-   `MINIMAX_API_KEY` (or other LLM keys e.g., `GEMINI_API_KEY`, `OPENROUTER_API_KEY`): Core AI generation keys.

## Usage

Farm-Agent is driven by a powerful command-line interface.

```bash
# Analyze a specific repository for bugs/quality issues (dry-run, no PR created)
farm_agent analyze <url>

# Solve top open issues in a specific repository
farm_agent solve <url> --max-issues 3

# Run a continuous Hunt targeting specific languages
farm_agent hunt --language python --rounds 5 --mode both

# Start the Super Human Mode (Terminator loop, 24/7 automated PR generation)
farm_agent superhuman

# Patrol open Pull Requests to address code review comments
farm_agent patrol
```

*For more options, run `farm_agent --help`.*

## Contributing

Contributions are welcome! Please submit a Pull Request and follow conventional commit messages.

## License

This project is licensed under the MIT License - see the `pyproject.toml` file for details.