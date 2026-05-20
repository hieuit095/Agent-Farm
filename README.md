# Farm-Agent

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Farm-Agent is an autonomous system that automatically discovers, analyzes, and contributes to open-source projects on GitHub. It operates as an end-to-end intelligent developer agent that hunts for target repositories, evaluates codebase vulnerabilities, runs deep static and LLM-assisted analysis, and subsequently generates high-quality, fully tested Pull Requests or GitHub Issues.

## Key Features

- **Polyglot Sandbox Validation:** All generated code patches are rigorously validated inside an isolated Docker sandbox. The pipeline guarantees that no code is submitted unless it successfully compiles and passes tests.
- **DEV-QA Bounty Loop:** Employs a multi-cycle evaluation phase where generated contributions are scored by an AI QA agent against the repository's native style guidelines. Failures result in corrective self-learning loops before submission.
- **PR Patrol & Auto-Healing:** Continuously monitors submitted Pull Requests, automatically responding to maintainer review comments, fixing styling issues, signing CLAs, and auto-healing failed CI pipeline checks.
- **Super Human Mode:** Simulates organic developer behavior by operating in a 24/7 continuous cycle that interleaves active PR generation with periodic review patrolling, using randomized delays to respect API limits.
- **Security-First Architecture:** Implements a Security Disclosure Gate to respect project maintainers' private vulnerability reporting policies (e.g., `SECURITY.md`) before analyzing issues or publishing PRs.
- **White-Hat Bloodhound Audits:** Pre-filters repositories using `Semgrep` to identify structural code vulnerabilities and validates finding impact via advanced contextual intelligence before consuming LLM tokens.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops low-effort, trivial, or documentation-only PRs, ensuring all submissions deliver critical, high, or medium impact value.

## System Architecture (High-Level)

At its core, Farm-Agent functions as a multi-stage data processing pipeline designed using the *DeerFlow* pattern (a custom registry-based agent architecture).
1. **Discovery & Intelligence:** The system uses GitHub APIs to query for active repositories within specific parameters and cross-references them against internal SQLite memory to avoid duplicate work.
2. **Analysis:** The `BloodhoundAnalyzer` runs Semgrep rules and Contextual Intelligence checks to filter out false positives and low-value changes.
3. **Execution Loop:** Based on priority, the system routes findings to the `ContributionGenerator` or `IssueSolver`. Generated patches are automatically verified using a local Docker sandbox.
4. **Maintenance:** Background loops (`PR Patrol` and `Janitor`) track ongoing Pull Requests, automatically answering questions or fixing CI failures until the PR is merged or closed.

## Getting Started

### Prerequisites

- **Python**: `>=3.11`
- **Docker**: Version `7.1` to `<8.0` (required for Polyglot Sandbox Validation)
- **Hatchling**: Used as the build backend

### Installation

Clone the repository and install the project using `pip`:

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Variables

Farm-Agent requires a `.env` file at the root of the project to manage API keys and configurations. You can copy the example file to get started:

```bash
cp .env.example .env
```

Ensure the following exact environment variables are configured (as inferred from the config module):

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token.
- `GITHUB_SECONDARY_TOKENS`: (Optional) Comma-separated list of secondary tokens for API rate limit rotation.
- `MINIMAX_API_KEY`: API key for the primary LLM provider (Minimax).
- `OPENROUTER_API_KEY`: API key for the OpenRouter Red Team LLM provider.
- `TELEGRAM_BOT_TOKEN`: Required for notifications.

You must also configure a `config.yaml` file (copy `config.example.yaml` to `config.yaml`).

## Usage

Farm-Agent is driven entirely through its rich Command-Line Interface (CLI).

### Example Commands

- **Run Standard Pipeline:**
  Automatically discover repositories matching your configuration and create contributions.
  ```bash
  farm_agent run --language python --stars 500-5000
  ```

- **Target a Specific Repository:**
  Analyze and generate contributions for a single repository.
  ```bash
  farm_agent target https://github.com/owner/repo
  ```

- **Start Super Human Mode:**
  Run the agent in a 24/7 continuous loop simulating human coding delays.
  ```bash
  farm_agent superhuman
  ```

- **Analyze Open PRs (Patrol):**
  Check open PRs for maintainer feedback, answer questions, or push fixes.
  ```bash
  farm_agent patrol
  ```

- **System Status:**
  View the overall system health, rate limits, and memory statistics.
  ```bash
  farm_agent system-status
  ```

## Contributing & License

Contributions are welcome! Please follow standard open-source contribution guidelines. This project is licensed under the MIT License.
