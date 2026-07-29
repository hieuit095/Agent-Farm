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

- **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. Recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and builds AST-based call graphs for precise module dependency links directly injected into the prompt context.
- **Anti-Farming Filter:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned).
- **Two-Layer Gatekeeper System:**
  - **Layer 1 (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
  - **Layer 2 (Gemini-3.5-Flash):** Supreme Audit of incident dossiers, sandbox logs, and proposed patches.
- **Dynamic Bug Verification (PoC Execution):** Generates self-contained Proof-of-Concept (PoC) scripts to dynamically trigger the vulnerability inside a locked-down container sandbox before writing a fix.
- **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check (Pass 1: Efficacy, Pass 2: Regression using native test suites).
- **Terminator Mode:** A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite queue, integrating both hunting and PR patrolling.
- **Hybrid Contribution Router:** Routes critical/high security vulnerabilities via Direct PR, and issues polite proposals for performance/refactor tasks via the Issue-First Protocol.

---

## 🏛️ System Architecture (High-Level)

The system is orchestrated by a central pipeline that operates through multiple intelligence layers:
1. **Target Discovery:** Uses GitHub search and local queues to find high-value repositories.
2. **Analysis & Context Injection:** The **Omniscient Context Engine** gathers repo documentation (via RAG) and maps the codebase structure via AST/Regex. The Red Team (Bloodhound) runs Semgrep and LLM-based scans to identify issues.
3. **Rigorous Filtering:** Findings pass through the **Anti-Farming Filter** and the **Layer 1 Appraiser (Qwen)** to eliminate noise and false positives.
4. **DEV-QA Execution Loop:** For validated findings, the system writes a patch, validates it via **Dynamic Bug Verification** inside a strictly isolated **Docker Sandbox**, runs native tests to detect regressions, and enters a self-correction cycle if tests fail.
5. **Final Audit & Submission:** The **Layer 2 Supreme Auditor (Gemini)** gives final approval, and if cleared (and not requiring private disclosure), the PR is automatically crafted and submitted using the `GitHubClient`.

---

## 🛠️ Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher (Docker Desktop required for isolated sandbox validation)
- **Git:** Required for cloning and patching local repositories.

### Environment Variables

You must define these core environment variables in a `.env` file at the root of the project to run Agent-Farm:

- `GITHUB_TOKEN`: Your Personal Access Token (PAT) with `repo`, `read:org`, and workflow scopes (Required).
- `OPENROUTER_API_KEY`: API key for OpenRouter, used to access LLMs like `deepseek-v4-pro`, `qwen3.7-max`, and `gemini-3.5-flash` (Required for full pipeline functionality).
- `MINIMAX_API_KEY`: Minimax API key, primarily used if you rely on Minimax LLMs (Optional/Required based on config).
- `MINIMAX_GROUP_ID`: Your Minimax Group ID (Optional).
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (comma-separated, Optional).
- `EXCLUDED_LANGUAGES`: Comma-separated list of languages to ignore to save budget (e.g., `javascript,typescript`, Optional).
- `TELEGRAM_BOT_TOKEN`: Token for Telegram push notifications (Optional).
- `TELEGRAM_CHAT_ID`: Destination chat ID for Telegram messages (Optional).
- `SLACK_WEBHOOK_URL`: URL for Slack push notifications (Optional).
- `DISCORD_WEBHOOK_URL`: URL for Discord push notifications (Optional).

### 1-Click Launch (Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

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
   *(The script will automatically pull the latest codebase, initialize your `.env` configuration file from `.env.example`, build the Docker image, and launch the daemon in the background.)*

3. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## 🚀 Usage

The `farm_agent` CLI offers various operations. Run them directly in your environment or via `docker exec -it agent-farm <command>`.

- **Run standard pipeline:** (Auto-discover and contribute)
  ```bash
  farm_agent run
  ```
- **Target a specific repository:**
  ```bash
  farm_agent target <repo_url>
  ```
- **Solve open issues in a repository:**
  ```bash
  farm_agent solve <repo_url>
  ```
- **Hunt Mode:** (Aggressive discovery and contribution loop)
  ```bash
  farm_agent hunt --rounds 5 --mode both
  ```
- **Terminator Mode:** (Relentless 24/7 autonomous operation)
  ```bash
  farm_agent superhuman
  ```
- **PR Patrol:** (Check pending PRs and fix CI errors)
  ```bash
  farm_agent patrol
  ```
- **View runtime stats and leaderboards:**
  ```bash
  farm_agent stats
  farm_agent leaderboard
  ```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).