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

- **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
- **Anti-Farming Filter (Zero-Garbage PR Gatekeepers):** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned).
- **Layer 1 Appraiser (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
- **Layer 2 Supreme Auditor (Gemini-3.5-Flash):** Vetoes patches targeting dead or deprecated code blocks, or patches that have hallucinated fixes, before PR generation.
- **Dynamic Bug Verification (PoC Execution):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down container sandbox.
- **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check: Efficacy (applies patch and re-runs PoC) and Regression (executes native test suites to ensure no existing functionality is broken).
- **Bloodhound Red Team (Semgrep):** Runs pre-analysis sweeps to identify critical security flaws using Semgrep rulesets before heavy LLM processing.
- **Terminator Mode (Superhuman Loop):** A relentless 24/7 continuous operational loop that runs issue-first workflows and circular target pipeline without artificial delays.

---

## 🏗️ System Architecture (High-Level)

The Agent-Farm system is orchestrated by `FarmAgentPipeline` (in `farm_agent/orchestrator/pipeline.py`), connecting several major components to form a closed-loop contribution system:
1. **Discovery & Reconnaissance:** Identifies targets and fetches repositories (via `GitHubClient`), gathering subsystem docs and building AST dependencies.
2. **Analysis & Bloodhound Pre-filter:** Uses Semgrep and static analysis tools. Finds potential vulnerabilities.
3. **Layer 1 Filtering:** `qwen3.7-max` evaluates findings to rule out false positives.
4. **Dynamic PoC Verification:** Triggers bug in `DockerSandbox`.
5. **Generator & DEV-QA Loop:** Generates a patch (using `deepseek-v4-pro`) and scores it. If tests fail in the sandbox, self-corrects based on `stderr`.
6. **Layer 2 Audit & Security Gate:** `gemini-3.5-flash` conducts final checks. Determines if public PR or private security disclosure is required.
7. **Submission:** Opens issues (Issue-First) or PRs, tracking the state using SQLite (`Memory`).

---

## 🛠️ Getting Started

### Prerequisites
- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for Sandbox validation)
- **Git** installed on the host machine.

### Installation
You can install the package with its development dependencies:
```bash
make install
# Under the hood this runs: pip install -e '.[dev]'
```

### Environment Variables
To run Agent-Farm, you must configure a `.env` file (copy `.env.example` to `.env`). The exact variables required are:

- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (PAT).
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (comma-separated).
- `EXCLUDED_LANGUAGES`: Filter out verbose/costly languages (comma-separated, e.g. `javascript,typescript`).
- `MINIMAX_API_KEY`: API Key for Minimax provider.
- `MINIMAX_GROUP_ID`: Minimax group ID (if required).
- `OPENROUTER_API_KEY`: API Key for OpenRouter (used by Bloodhound, Gen, Layer 1, Layer 2).
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For Telegram notifications.
- `SLACK_WEBHOOK_URL`: For Slack notifications.
- `DISCORD_WEBHOOK_URL`: For Discord notifications.

### 1-Click Launch (Docker)

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Configure Settings:**
   Copy `.env.example` to `.env` and fill out your configuration (see above).

3. **Run the Quick-Start Script:**
   * **Windows:**
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage (CLI Commands)

Agent-Farm provides a comprehensive suite of CLI utilities accessible via `farm_agent`:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular target loop: process deterministic target from target_repo.json
farm_agent hunt-circular

# Run the Relentless Terminator Mode (24/7 Superhuman loop)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Query current PR queue and runtime statistics
farm_agent status
farm_agent stats
farm_agent system-status

# Display leaderboard of merged/submitted contributions
farm_agent leaderboard

# Manage configurations and profiles
farm_agent config
farm_agent profile <profile_name>
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites (`make test`).

Licensed under the [MIT License](LICENSE).
