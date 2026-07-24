# Agent-Farm

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-7.1+-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

**Agent-Farm** (`farm_agent`) is an autonomous system that automatically contributes to open-source projects on GitHub. It discovers repositories, analyzes code for bugs or improvements, writes code, verifies patches in a sandboxed environment, and submits Pull Requests.

## Key Features

- **Omniscient Context Engine:** Analyzes full repository structure and dependencies using advanced RAG and codebase mapping to understand deep context before generating code.
- **Dynamic Bug Verification (Docker Sandbox):** Before a PR is submitted, Agent-Farm automatically generates Proof-of-Concept (PoC) scripts and runs native test suites in an isolated Polyglot Docker Sandbox to verify that vulnerabilities are triggered and patches successfully resolve them without introducing regressions.
- **Bloodhound Red Team:** An initial AST/Semgrep-powered security scanning phase that identifies exploitable vulnerabilities to prioritize high-value targets.
- **DEV-QA Bounty Loop:** A strict 3-cycle generation and evaluation loop where an internal QA agent scores patches and provides critiques, ensuring high-quality, maintainer-ready contributions.
- **Terminator Mode (`farm_agent superhuman`):** A relentless, continuous execution loop that mimics an organic developer without artificial delays, aggressively pulling targets for analysis and issue solving.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that strictly blocks trivial, low-impact, or documentation-only PRs to prevent maintainer spam.
- **PR Patrol:** Automatically monitors open PRs to answer maintainer questions, fix CI failures, address style feedback, and sign CLAs.

## System Architecture (High-Level)

At a high level, Agent-Farm operates through a pipeline of interconnected intelligence layers:
1. **Target Acquisition:** Discovers repos dynamically (via GitHub API) or continuously from a predefined database (Circular Target Loop).
2. **Analysis & Red Teaming:** Uses lightweight scanners (Bloodhound) and deep LLM analysis (Layer 1 Appraiser) to find and filter genuine code issues or security vulnerabilities.
3. **Contextual Generation:** Generates code fixes by indexing subsystem documentation and constructing dependency graphs.
4. **Sandboxed Verification:** Clones the repository locally into a Docker container, applies the generated patch, and runs native tests and PoCs to verify efficacy and check for regressions.
5. **Supreme Audit & Submission:** A final Layer 2 Supreme Auditor reviews the full dossier (including sandbox logs) before the PR Manager pushes the branch and creates the Pull Request on GitHub.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Required for Sandbox Verification)
- **Git**

### Installation

Agent-Farm provides a 1-Click Docker Desktop Quick-Start. This is the primary and recommended method for launching the agent.

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. Configure environment variables (see below). The start script will automatically create a `.env` file from `.env.example` if one doesn't exist.

3. Launch via Docker:
   - **Unix/macOS:**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   - **Windows:**
     ```cmd
     start.bat
     ```

### Environment Variables

Agent-Farm requires specific environment variables loaded via a `.env` file to function. **Never commit your `.env` file.**

**Core APIs:**
- `GITHUB_TOKEN` (Required): Your primary GitHub Personal Access Token (requires `repo`, `read:org`, and `workflow` scopes) for creating PRs and issues.
- `GITHUB_SECONDARY_TOKENS` (Optional): Comma-separated list of additional GitHub tokens to distribute read-only API load.
- `MINIMAX_API_KEY` (Required): API key for the primary Minimax LLM.
- `MINIMAX_GROUP_ID` (Optional): Required by some Minimax plans.
- `OPENROUTER_API_KEY` (Optional): API key for OpenRouter, used for the Bloodhound Red Team pipeline, Layer 1 Appraiser (Qwen), and Layer 2 Supreme Auditor (Gemini).

**Configuration:**
- `EXCLUDED_LANGUAGES`: Comma-separated list of languages to ignore (e.g., `javascript,typescript`).

**Notifications (Optional):**
- `TELEGRAM_BOT_TOKEN`: Bot token for push notifications.
- `TELEGRAM_CHAT_ID`: Destination chat ID for notifications.
- `SLACK_WEBHOOK_URL`: Slack incoming webhook URL.
- `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL.

## Usage

Agent-Farm is operated via a Rich command-line interface. When running via Docker, you can attach to the running container:

```bash
# Attach to the CLI to run the agent continuously in Terminator mode
docker exec -it agent-farm farm_agent superhuman

# Target a specific repository
docker exec -it agent-farm farm_agent target https://github.com/owner/repo

# Auto-discover and aggressively process repositories
docker exec -it agent-farm farm_agent hunt

# Solve open issues in a specific repository
docker exec -it agent-farm farm_agent solve https://github.com/owner/repo

# Check on open PRs and auto-respond to maintainer feedback
docker exec -it agent-farm farm_agent patrol

# Show overall system statistics
docker exec -it agent-farm farm_agent stats

# Display alumni friendly repos (VIP Roster)
docker exec -it agent-farm farm_agent vips
```

## Contributing & License

Contributions are welcome! Please feel free to submit a Pull Request.

This project is licensed under the MIT License - see the `LICENSE` file for details.
