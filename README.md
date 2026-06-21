# Farm-Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%3E%3D7.1-blue.svg)](https://www.docker.com/)

**Farm-Agent** is an autonomous system that automatically contributes to open source projects on GitHub. It discovers repositories, analyzes the codebase for vulnerabilities and issues, generates high-quality fixes, validates them in an isolated sandbox, and submits pull requests, all while managing PR feedback iteratively like a senior engineer.

## Overview

Farm-Agent operates a multi-stage execution pipeline orchestrating an autonomous GitHub contribution lifecycle. It searches for eligible repositories based on configurable discovery rules and processes target repositories through static analysis (e.g., via the Semgrep-powered Bloodhound Analyzer) to identify security vulnerabilities, bugs, or performance issues. Fixes are then generated using deep codebase context (via RAG mappings) and rigorously validated using a Dynamic Bug Verification system within a Docker sandbox, ensuring no regressions. Finally, the agent manages pull request lifecycles (PR Patrol) by automatically responding to maintainer feedback, applying style changes, and answering questions.

## Key Features

- **Autonomous Contribution Pipeline:** Seamlessly discovers, analyzes, patches, validates, and creates PRs for open source repositories.
- **Deep Codebase Reconnaissance & RAG Mapping:** Constructs precise dependency graphs and indexes repository subsystem documentation using ChromaDB to contextually anchor AI code generation.
- **Dynamic Bug Verification (Docker Sandbox):** Generates Proof-of-Concept (PoC) exploits and validates patches locally in isolated Docker environments to ensure efficacy and prevent regressions before submitting a PR.
- **DEV-QA Bounty Loop:** Employs a multi-cycle (DEV and QA) feedback loop where generated patches are critically evaluated and iteratively refined using lessons learned from prior failures.
- **Advanced Threat & Vibe Check Systems:** Includes an Anti-Farming Filter that strictly blocks trivial/documentation changes and a "Maintainer Vibe Check" to avoid repositories with historically toxic interactions.
- **PR Patrol & Auto-Healing:** Continuously monitors open PRs to respond to maintainer comments and automatically fix failing CI checks without human intervention.
- **Terminator Mode / Super Human Mode:** Mimics organic human contribution patterns with randomized delays and daily quotas to sustain long-term operations on GitHub.
- **Security Disclosure Gate:** Scans repository meta-files for private disclosure requirements and redirects sensitive vulnerability reports away from public PRs.

## High-Level System Architecture

Farm-Agent relies on the "DeerFlow" pattern—a custom registry-based agent and middleware pipeline architecture.
1. **Discovery Engine:** Sources target repositories via GitHub API searches or from a persistent SQLite database (`target_repos`).
2. **Analysis Module:** Employs rule-based engines (`BloodhoundAnalyzer`) to identify codebase issues.
3. **Generation Engine:** Uses deep LLM context generation (supported by `RepoMapper` and local ChromaDB `RepoIndexer`) to craft minimal, effective patches.
4. **Validation Sandbox:** Deploys generated patches in an isolated `DockerSandbox`, confirming the bug is fixed and native tests pass.
5. **Orchestrator & Memory:** Governs execution loops (`SuperHumanLoop`) and stores run history, API quotas, and persistent learning data in an SQLite database.
6. **PR Manager & Patrol:** Submits fixes to GitHub and handles subsequent review comments iteratively.

## Getting Started

### Prerequisites

Ensure you have the following software installed:
- Python >= 3.11
- Docker >= 7.1

### Installation

Clone the repository and run the `Makefile` installation target to install the package and its development dependencies in an isolated virtual environment (recommended):

```bash
git clone https://github.com/hieuit095/Agent-Farm.git
cd Agent-Farm
python3 -m venv venv
source venv/bin/activate
make install
```

For docker setups:
```bash
make docker
```

### Environment Variables

Copy `.env.example` to `.env` and set up your essential tokens. Key variables include:

```env
GITHUB_TOKEN=your_github_token
MINIMAX_API_KEY=your_minimax_key
OPENROUTER_API_KEY=your_openrouter_key
TELEGRAM_BOT_TOKEN=your_telegram_token
```

### Usage

Farm-Agent provides a rich CLI to drive its various operations. Start by verifying your configuration:

```bash
farm_agent config
```

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Hunt mode (Aggressive Discovery & Contribution):**
```bash
farm_agent hunt --rounds 5 --mode both
```

**Circular Target Loop (Processes queued repos continuously):**
```bash
farm_agent hunt-circular
```

**Monitor and patrol open PRs:**
```bash
farm_agent patrol
```

**Super Human Mode (24/7 Organic Execution):**
```bash
farm_agent superhuman
```

## Contributing

Contributions are welcome! Please ensure that you test your changes locally using the test suite.

To run the test suite:
```bash
make test
```

To run formatting and linting:
```bash
make lint
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
