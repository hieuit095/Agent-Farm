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

* **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
* **Terminator Mode (`superhuman`):** A relentless, continuous 24/7 execution loop without artificial delays, pulling targets exclusively from the SQLite target queue, solving issues, and submitting PRs autonomously.
* **Anti-Farming Filter:** Strict filtering mechanism (Zero-Garbage PR Gatekeepers) with zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs. Enforces Layer 1 (Qwen Appraisal) and Layer 2 (Gemini Supreme Audit) to veto low-effort spam before generation begins.
* **Dynamic Bug Verification:** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using DeepSeek models to dynamically trigger the vulnerability inside a locked-down container sandbox.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check. Pass 1 applies the patch and re-runs the PoC. Pass 2 executes the project's native test suite to ensure the patch does not break existing functionality or downstream dependencies.

---

## 🏛️ System Architecture (High-Level)

Agent-Farm orchestrates an autonomous pipeline structured around core agentic loops:

1. **Target Discovery & Bloodhound Red Team:** The `pipeline.py` orchestrator utilizes Semgrep (AST-grep) as a radar to scan targets, feeding potential vulnerabilities to an LLM-based White-Hat auditor.
2. **Issue-First Pipeline & DEV-QA Bounty Loop:** When targeting specific repositories, the agent leverages the `issues/solver.py` module to analyze issues, map code dependencies, and propose multi-file patches.
3. **Execution Sandbox:** The `sandbox.py` module provisions a secure Docker container (`sandbox_isolated` network) where PoCs and native unit tests (`pytest`, `npm test`) are executed to validate fixes.
4. **Persistent Memory State:** A SQLite-backed `memory.py` layer continuously tracks API usage, target repo status, cached findings, submitted PRs, and PR outcomes (merge rates) to avoid duplicate work and enforce API quotas.
5. **PR Patrol & Maintainer Sync:** The `pr/patrol.py` module monitors submitted PRs, fetching CI logs or maintainer comments, and recursively triggers follow-up auto-heal commits if tests fail on the target repository.

---

## 🛠️ Getting Started

### Prerequisites
* **Python:** `>= 3.11` (configured via Hatchling build backend)
* **Docker:** `>= 7.1` (required for Sandbox validation and 1-Click Launch)
* **Git:** Installed locally on the host machine.

### 1-Click Docker Launch

Agent-Farm provides a robust, pre-configured Docker Desktop setup.

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
   * *The script will initialize `.env`, build the Docker image, and launch the daemon via `docker-compose.yml` on the `internet_access` and `sandbox_isolated` networks.*

### Environment Variables

Configure your `.env` file (copied from `.env.example`) with the following required and optional variables:

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | (Required) Primary Personal Access Token with `repo`, `read:org`, and `workflow` scopes. |
| `MINIMAX_API_KEY` | (Required if using Minimax provider) API key for Minimax LLM. |
| `OPENROUTER_API_KEY` | (Required for Bloodhound) API key for DeepSeek/OpenRouter routing. |
| `TELEGRAM_BOT_TOKEN` | (Optional) Telegram bot token for push notifications. |
| `TELEGRAM_CHAT_ID` | (Optional) Destination chat ID for Telegram. |
| `SLACK_WEBHOOK_URL` | (Optional) Slack incoming webhook URL. |
| `DISCORD_WEBHOOK_URL` | (Optional) Discord incoming webhook URL. |
| `EXCLUDED_LANGUAGES` | (Optional) Comma-separated list of languages to skip (e.g., `javascript,typescript`). |
| `GITHUB_SECONDARY_TOKENS` | (Optional) Comma-separated list of secondary tokens for API rate-limit rotation. |
| `MINIMAX_GROUP_ID` | (Optional) Group ID sent as `X-Minimax-Group-Id` header. |

---

## ⚙️ Usage Reference

Agent-Farm is operated via the `farm_agent` Click CLI (`farm_agent/cli/main.py`).

```bash
# Attach to the running Docker container
docker exec -it agent-farm bash

# Run the Relentless 24/7 Terminator loop (patrols PRs and hunts targets)
farm_agent superhuman

# Start the full automated discovery and contribution pipeline
farm_agent run

# Target a specific repository directly for bug-bounty hunting
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Show contribution leaderboard and success rates
farm_agent leaderboard

# View available LLM models and tier allocations
farm_agent models

# Show overall system status (memory stats, cached findings, limits)
farm_agent system-status
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites (`make test`). Note that all code style must adhere to Ruff limits (100-character lines).

Licensed under the [MIT License](LICENSE).
