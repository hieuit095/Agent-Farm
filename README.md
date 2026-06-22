# 🛠️ Agent-Farm

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-%3E%3D7.1-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features (v4.0.0)

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Zero-Garbage PR Gatekeepers
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using deepseek-v4-pro to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm operates around a resilient orchestrator pipeline (`FarmAgentPipeline`) and a relentless autonomous loop (`SuperHumanLoop`).

1. **Discovery**: Scans GitHub for targeted repositories or solves specific issues.
2. **Context Engine (RAG & Dependency Graphing)**: Indexes repo documentation via ChromaDB and parses module logic (AST) to build context.
3. **Appraisal & Gatekeeping**: Findings are rigorously vetted by layered LLMs (e.g. Qwen, Gemini) to drop false positives.
4. **Validation Pipeline**: Generates an exploit/trigger script, runs it in an isolated `DockerSandbox`, drafts a patch using a coding model (DeepSeek), and re-verifies via the project's native test suite.
5. **PR Submission & Patrol**: Commits fixes to GitHub, records state to a local SQLite database (`memory.db`), and actively monitors PRs to answer maintainer comments or fix CI failures.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** >= 3.11 (if running directly/developing)
* **Docker** >= 7.1 (for sandboxing and container execution)
* **Git** installed on the host machine.

### Environment Variables

Agent-Farm requires the following environment variables in a `.env` file at the repository root:

```env
GITHUB_TOKEN=your_github_pat_here
OPENROUTER_API_KEY=your_openrouter_key_here

# Optional: Required for the PR Janitor (disabled by default) and specific fallback modules.
MINIMAX_API_KEY=your_minimax_key_here

# Optional: Required for sending system alerts.
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### 1-Click Launch (Docker)

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

3. **Configure Settings:**
   Open the newly created `.env` file and configure your API tokens.

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

### Manual Installation (Development)

Alternatively, you can install Agent-Farm using Hatchling and `make`:

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package and development dependencies
make install
```

---

## ⚙️ CLI Command Reference

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

### Pipeline Execution Commands
```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: process targets sequentially from target_repo.json
farm_agent hunt-circular

# Run the Relentless 24/7 Super Human loop (Terminator Mode)
farm_agent superhuman

# Analyze a repository without creating contributions
farm_agent analyze <url>

# Run pipeline with a named profile (e.g. standard, quick, thorough)
farm_agent profile <profile_name>
```

### Management & Status Commands
```bash
# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries (default 90 days)
farm_agent gc --days 90

# Query current PR queue, runtime statistics, system status, and LLM allocations
farm_agent status
farm_agent stats
farm_agent system-status

# View the VIP Roster (Friendly Repositories where you have merged PRs)
farm_agent vips

# View the contribution leaderboard and success rates
farm_agent leaderboard
```

### Configuration & Tooling
```bash
# Show current configuration
farm_agent config

# List available models and their capabilities
farm_agent models

# List available contribution templates
farm_agent templates

# Send a test notification to configured channels (Telegram, Slack, Discord)
farm_agent notify-test
```

*(Note: In Agent-Farm v4.0+, the legacy `janitor` module is disabled.)*

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites (e.g., `make test` or `pytest tests/`).

Agent-Farm strictly enforces Ruff formatting (`make lint`). Always lint your code before opening a PR!

Licensed under the [MIT License](LICENSE).
