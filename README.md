# 🛠️ Agent-Farm (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![ChromaDB RAG](https://img.shields.io/badge/ChromaDB-RAG-FF6F00?logo=chroma&logoColor=white)](https://www.trychroma.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features (v4.0.0 Upgrades)

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🤖 Terminator Mode (SuperHumanLoop)
A relentless 24/7 operational loop cycling through deterministic circular target hunting and PR patrol operations.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm utilizes an orchestrator pattern (`FarmAgentPipeline`) that drives repositories through a rigorous, multi-stage process:
1. **Discovery & Intelligence:** Uses `DatabaseTargetDiscovery` or `RepoDiscovery` to fetch repositories. Employs `RepoIndexer` (ChromaDB) to digest documentation and `RepoMapper` to construct AST dependency graphs.
2. **Analysis:** The `BloodhoundAnalyzer` (Semgrep) and `CodeAnalyzer` scan the codebase, strictly evaluated by the Anti-Farming filter.
3. **Validation (DEV-QA Loop):** Findings undergo Layer 1 appraisal (Qwen). Valid issues route to code generation. A PoC is generated and executed in a locked-down `DockerSandbox`.
4. **Generation & Verification:** The LLM generates patches, which are repeatedly tested in the sandbox. Layer 2 audit (Gemini) verifies the entire incident dossier.
5. **Submission & Patrol:** A PR is opened (or private disclosure made). The `PRPatrol` daemon then monitors active PRs, responding to comments and auto-fixing CI failures.

All state (analyzed repos, PR statuses, API usage, AI lessons) is persisted in a local WAL-mode SQLite database (`memory.db`).

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker** >= 7.1 (Docker Desktop recommended).
* **Python** >= 3.11 (if running locally without Docker).
* **Git** installed on the host machine.

### 1-Click Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   * **Windows:** Double-click `start.bat` or run:
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   * *Note: The script will automatically pull the latest codebase, initialize your `.env` configuration file from `.env.example` if missing, build the Docker image, and launch the daemon in the background.*

### Environment Variables

Configure the following variables in your `.env` file (copied from `.env.example`):

* `GITHUB_TOKEN` (Required): Personal access token with repo, read:org, and workflow scopes.
* `GITHUB_SECONDARY_TOKENS` (Optional): Comma-separated secondary tokens for load balancing GET requests.
* `EXCLUDED_LANGUAGES` (Optional): Comma-separated list of languages to ignore (e.g., `javascript,typescript`).
* `MINIMAX_API_KEY` (Required if provider="minimax"): Minimax API key.
* `MINIMAX_GROUP_ID` (Optional): Minimax group ID.
* `OPENROUTER_API_KEY` (Required for Bloodhound/OpenRouter routing): OpenRouter API key.
* `TELEGRAM_BOT_TOKEN` (Optional): Bot token for push notifications.
* `TELEGRAM_CHAT_ID` (Optional): Destination chat for Telegram notifications.
* `SLACK_WEBHOOK_URL` (Optional): Incoming webhook URL for Slack.
* `DISCORD_WEBHOOK_URL` (Optional): Incoming webhook URL for Discord.

---

## ⚙️ Usage (CLI Command Reference)

Attach to the agent CLI via Docker (or run locally via `farm_agent`):

```bash
# Attach to the running Docker container
docker exec -it agent-farm farm_agent <command>
```

**Core Commands:**

* `farm_agent run`: Start the full automated discovery, analysis, and contribution pipeline.
* `farm_agent target <repo_url>`: Target a specific repository directly.
* `farm_agent solve <repo_url>`: Solve open issues in a specific repository.
* `farm_agent hunt [--rounds N] [--mode analysis|issues|both]`: Run in Hunt Mode: aggressively discover repos and solve issues/bugs.
* `farm_agent hunt-circular`: Process a target from `target_repo.json` in a circular loop.
* `farm_agent superhuman`: Run the Relentless 24/7 Terminator loop (patrols PRs and hunts targets continuously).
* `farm_agent patrol`: Check open PRs for maintainer comments, answer queries, and push CI auto-fixes.
* `farm_agent cleanup`: Clean up forks where all PRs are closed or merged.
* `farm_agent status`: Show status of submitted PRs.
* `farm_agent stats`: Show overall statistics (runs, repos analyzed, PRs submitted/merged).
* `farm_agent system-status`: Show memory DB stats and GitHub rate limit.
* `farm_agent models`: List available models and routing mappings.
* `farm_agent leaderboard`: Show contribution leaderboard and success rates.
* `farm_agent profile <profile_name>`: Run with thorough, standard, or quick presets.
* `farm_agent config`: Show current configuration.
* `farm_agent reset-db`: Safely clear run logs and start with a fresh pipeline queue (preserves PRs).
* `farm_agent gc --days 90`: Run garbage collection to purge stale knowledge base entries.
* `farm_agent vips`: Trigger Alumni Sync and show Friendly Repo List.
* `farm_agent templates`: List available contribution templates.

---

## 🤝 Contributing

We welcome white-hat security researchers and AI engineers to contribute!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Ensure all patches are validated locally using our test suites (`make test`).
5. Push to the Branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
