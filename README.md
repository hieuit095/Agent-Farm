# Farm-Agent

[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-%3E%3D7.1-blue.svg)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Farm-Agent is an autonomous system that automatically discovers, analyzes, and contributes to open-source projects on GitHub. Leveraging large language models (LLMs) and a polyglot sandboxed validation environment, it relentlessly identifies bugs, security vulnerabilities, and code quality issues, generating validated pull requests without human intervention.

## Key Features

- **Autonomous Pipeline:** Sequential execution loop (Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR).
- **Polyglot Sandbox:** Safe, isolated code validation using Docker before submitting PRs across dual networks (`internet_access` and `sandbox_isolated`).
- **Bloodhound Red Team & Radar:** Deep codebase scanning using `ast-grep`, Semgrep, and White-Hat Auditing via OpenRouter.
- **Terminator Execution Loop ("Super Human Mode"):** A 24/7 daemon designed to maximize PR throughput up to daily API caps.
- **PR Patrol:** Autonomously monitors open PRs, auto-heals CI check failures, and responds to maintainer feedback.
- **Anti-Farming Filter:** Strictly evaluates and blocks low-impact or trivial documentation/cosmetic pull requests.
- **Local Ephemeral RAG Engine:** Built on ChromaDB to securely process codebase embeddings entirely in RAM.
- **Multi-Model Support:** Integrates with Minimax (default), OpenAI, Anthropic, Gemini, and local models via Ollama.

## System Architecture

Farm-Agent operates through a highly structured pipeline:
1. **Discovery & Gate:** Finds repositories matching configured criteria (language, stars) or target lists, evaluating their `CONTRIBUTING.md` policies and friendliness metrics.
2. **Analysis:** The Bloodhound Red Team engine scans for vulnerabilities, architectural flaws, and code issues using SAST tools and LLMs.
3. **Engine:** The core generator creates code patches to address identified findings, ensuring non-trivial impact.
4. **Sandbox:** Proposed changes and tests are validated locally in an isolated Docker environment to ensure functional correctness.
5. **PR & Patrol:** Validated patches are committed to a fork and proposed upstream. The Patrol subsystem monitors the PR, pushing automatic fixes if CI checks fail or maintainers request changes.

*(For detailed architectural breakdown, see [PROJECT_MAP.md](PROJECT_MAP.md))*

## Getting Started

### Prerequisites

- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for the Polyglot Sandbox)

### Installation

1. Clone the canonical repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```
2. Install the project along with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Configuration

Farm-Agent requires environment variables for API authentication and a YAML configuration for operational settings.

1. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
2. Set the required variables in `.env`:
   - `GITHUB_TOKEN`: Your primary GitHub access token (requires `repo`, `read:org`, and `workflow` scopes).
   - `MINIMAX_API_KEY`: API key for the default Minimax LLM (or use `GEMINI_API_KEY`, `OPENAI_API_KEY`, etc. based on config).
   - *(Optional)* `GITHUB_SECONDARY_TOKENS`: Comma-separated tokens to distribute GET requests and avoid rate limits.
   - *(Optional)* `OPENROUTER_API_KEY`: API key for routing Bloodhound White-Hat audits.

3. Create the configuration file:
   ```bash
   cp config.example.yaml config.yaml
   ```

## Usage

Farm-Agent provides a rich CLI interface.

**Targeting a Specific Repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Running the Autonomous Pipeline (Discovery Mode):**
```bash
farm_agent run
```

**Analyzing a Repository without Contributing (Dry Run):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Solving Open Issues:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Starting the 24/7 Super Human Daemon:**
```bash
farm_agent superhuman
```

**System Commands:**
- `farm_agent status` - Show status of submitted PRs
- `farm_agent stats` - Show overall system statistics
- `farm_agent config` - Display the current configuration
- `farm_agent models` - List available models and capabilities
- `farm_agent leaderboard` - Show contribution leaderboard and success rates
- `farm_agent system-status` - Display comprehensive memory, PR, and rate limit metrics

## Contributing & License

Farm-Agent is distributed under the [MIT License](LICENSE).
All contributions must adhere to the standard open-source boilerplate process: fork the repository, create a branch, submit your feature or fix, and ensure all tests pass (`make test` and `make lint-check`).
