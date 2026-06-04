# Farm-Agent

![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![Docker](https://img.shields.io/badge/docker-supported-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Build Backend](https://img.shields.io/badge/build-hatchling-yellow)

## Overview

Farm-Agent is an autonomous system that automatically contributes to open source projects on GitHub. It operates as a 24/7 autonomous bounty-hunting security researcher and open source contributor, actively discovering repositories, analyzing codebases, solving issues, and submitting verified pull requests.

## Key Features

- **Autonomous Hunting (`hunt` / `hunt-circular`):** Automatically discovers active GitHub repositories matching criteria (stars, language) and attempts contributions.
- **Super Human Mode:** Mimics a human developer by setting daily PR quotas, injecting unpredictable simulated delays, interleaving exploration and patrol, and maintaining organic 24/7 operational loops.
- **Issue-First Pipeline:** Scans open GitHub issues, estimates their complexity, and selectively targets solvable issues to generate targeted fixes.
- **PR Patrol:** Constantly monitors open PRs submitted by the agent, auto-replies to maintainer questions, signs CLAs, and generates code changes based on review feedback.
- **Local RAG & Codebase Mapping:** Leverages ChromaDB for precise, context-aware codebase modifications and fixes.
- **Isolated Docker Sandbox:** Executes generated Proof of Concepts (PoCs) and unit tests in a securely isolated Docker environment before finalizing pull requests, significantly reducing regressions.
- **Bloodhound Red Team & Semgrep Radar:** Built-in White-Hat audits using Semgrep rulesets (e.g., `p/security-audit`, `p/cwe-top-25`) paired with Bloodhound evaluation for security-focused PRs.

## System Architecture (High-Level)

The agent operates through a rigorous execution pipeline:
**Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**

1. **Discovery:** Finds targets using the GitHub API or a predefined `target_repo.json`.
2. **Gate:** Ensures the repository is open to contributions (e.g., Security Disclosure Gate checks for private disclosure requirements).
3. **Analysis:** Deeply scans code patterns using AST parsing, Semgrep, and RAG.
4. **Engine:** The LLM generator dynamically writes fixes or new features based on the analysis or specific GitHub issues.
5. **Sandbox:** Verifies the generated code by running tests within an isolated environment.
6. **PR:** Submits a clean, documented Pull Request and hands it over to the PR Patrol for ongoing maintenance.

## Getting Started

### Prerequisites

- **Python** `>= 3.11`
- **Docker** `>= 7.1` (Required for Sandbox test execution and Red Team operations)
- **Git**

### Installation

Clone the repository and install the package with development dependencies using the provided Makefile:

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
make install
```

Alternatively, you can install it using pip:

```bash
pip install -e '.[dev]'
```

### Environment Setup

Farm-Agent requires several environment variables for authentication and configuration. Copy the example configuration files and fill them in:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

**Key Environment Variables in `.env`:**
- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated fallback tokens for GET request rotation.
- `OPENROUTER_API_KEY`: API key for the OpenRouter provider (used by default).
- `TELEGRAM_BOT_TOKEN`: (Optional) Token for notifications.

**`config.yaml` Customization:**
Adjust operational parameters such as `max_prs_per_day`, enabled analyzers, target languages, and more.

## Usage

Farm-Agent is driven by a rich command-line interface. Use the `farm_agent` CLI tool to interact with the system.

```bash
# Run a specific targeted contribution pipeline
farm_agent target https://github.com/owner/repo

# Start the continuous autonomous hunting loop
farm_agent hunt --rounds 5 --mode both

# Launch Super Human Mode (24/7 background worker with simulated delays)
farm_agent superhuman

# Patrol existing open PRs to reply to maintainers or fix issues
farm_agent patrol

# View system status and statistics
farm_agent system-status
farm_agent stats
```

## Contributing & License

Contributions are welcome. Please ensure that tests pass (`make test`) and that the code passes linting (`make lint`) before submitting a pull request.

This project is licensed under the MIT License - see the LICENSE file for details.
