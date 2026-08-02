# 🛠️ Agent-Farm (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

- **Issue-First Pipeline:** Proposes fixes via polite GitHub Issues for non-critical changes (e.g., refactors, performance optimizations) before generating code diffs.
- **Omniscient Context Engine:** Uses Retrieval-Augmented Generation (RAG) powered by ChromaDB to index subsystem documentation and builds AST-based call graphs for precise prompt context.
- **Terminator Mode / Circular Target Loop:** A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite target database for high-throughput hunting.
- **PR Patrol:** Scans open PRs created by Farm-Agent, reads maintainer review comments, generates code fixes (or answers questions), and automatically pushes updates.
- **Bloodhound Red Team & Anti-Farming Filter:** Uses static analysis (ast-grep + Semgrep) for deep bug hunting, while strictly vetoing trivial/documentation changes or theoretical edge cases through rigorous Qwen-powered Layer 1 Appraisals.
- **Dynamic Bug Verification & Blast Radius Auditing:** Generates and executes Proof-of-Concept (PoC) scripts inside isolated Docker sandboxes to guarantee vulnerability existence before patching, then re-runs native test suites to prevent regressions.

---

## 🏛️ System Architecture (High-Level)

Agent-Farm leverages an orchestrated multi-agent pipeline spanning Discovery, Analysis, Generation, QA Validation, and Pull Request Management. The system coordinates interactions across GitHub APIs and LLM providers via a main Pipeline (`FarmAgentPipeline`), storing state persistently in a local SQLite database (`Memory`).

1. **Discovery & Intelligence:** The system queries GitHub for repositories matching specific criteria, then parses repository files and documentation (aided by ChromaDB RAG indexer) to establish a comprehensive context map.
2. **Analysis:** The `CodeAnalyzer` (including the Bloodhound subsystem) pinpoints critical issues, filtering out low-quality/hallucinated findings via Layer 1 Appraisal models (e.g., Qwen-3.7-Max).
3. **Generation & Verification:** A DEV-QA loop continuously generates patches and verifies them in a polyglot Docker Sandbox. Dynamic PoC execution guarantees the vulnerability exists, and a full native test suite execution ensures the patch does not break existing code.
4. **Supreme Audit & Submission:** Finally, a Layer 2 Supreme Auditor (e.g., Gemini-3.5-Flash) conducts a final check against logs and context before PR submission or security disclosure via the `GitHubClient`.

---

## 🛠️ Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1 (for the isolated Polyglot Sandbox validation)
- **Git:** Installed on the host machine.
- Valid API Keys (GitHub, OpenRouter, and Minimax depending on configuration).

### Installation (1-Click Launch)

Agent-Farm provides a robust, pre-configured Docker setup.

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   * **Windows:**
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   *(Note: The script automatically pulls the latest codebase, initializes your `.env` configuration from `.env.example`, builds the Docker image, and launches the daemon.)*

### Environment Variables

To properly run the pipeline, ensure the following core variables are configured in your `.env` file (copied from `.env.example`):

- `GITHUB_TOKEN`: Personal access token with repo, read:org, and workflow scopes.
- `GITHUB_SECONDARY_TOKENS`: Additional GitHub tokens for GET request rotation (comma-separated).
- `MINIMAX_API_KEY`: Minimax API key (default LLM provider).
- `MINIMAX_GROUP_ID`: Minimax group ID (required by some Minimax plans).
- `OPENROUTER_API_KEY`: API key for OpenRouter (used by Bloodhound, PoC Generator, and Auditors).
- `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated).
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for push notifications.
- `TELEGRAM_CHAT_ID`: Telegram chat ID for notifications.
- `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for push notifications.
- `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL for push notifications.

---

## 🚀 Usage (CLI Command Reference)

Agent-Farm operates primarily through its Rich command-line interface.

```bash
# Attach to the running Agent CLI container
docker exec -it agent-farm farm_agent superhuman

# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: deterministic round-robin from target_repo.json
farm_agent hunt-circular

# Run the Relentless continuous operational loop (Terminator Mode)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Query current PR queue, runtime statistics, and LLM allocations
farm_agent status
farm_agent stats
farm_agent models
farm_agent leaderboard

# VIP Roster — Alumni Sync + Full Friendly Repo List
farm_agent vips

# View configuration and templates
farm_agent config
farm_agent templates

# Run with specific configuration profiles
farm_agent profile <profile_name>

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# Send a test notification to configured channels
farm_agent notify-test

# Show system status (memory, PRs, rate limits)
farm_agent system-status
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
