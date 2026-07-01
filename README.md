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

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Zero-Garbage PR Gatekeepers
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Layer 1: EXPERT APPRAISAL (Qwen 3.7 Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Layer 2: SUPREME AUDITOR (Gemini 3.5 Flash):** Vetoes patches targeting dead or deprecated code blocks and checks the entire incident dossier (including sandbox logs) to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🤖 Terminator Mode (Relentless Execution Loop)
A relentless 24/7 continuous operational loop (`superhuman` command) that cycles through hunting for new targets (Circular Target Loop) and patrolling submitted PRs, pushing fixes without artificial delays.

### 👮 PR Patrol & Alumni Sync (VIP Roster)
Continuously patrols open PRs to auto-reply to maintainer comments and push CI auto-fixes. Maintains an Alumni Sync (via the `vips` command) to keep a friendly roster of repositories where PRs have successfully been merged.

---

## 🏛️ System Architecture (High-Level)

Agent-Farm leverages an **Issue-First Pipeline** and **Hybrid Contribution Router**:
1. **Target Discovery & Bloodhound Scanning:** Discovers repos via GitHub API or deterministic target queue (`target_repo.json`). The **Bloodhound Red Team** runs white-hat Semgrep rules to filter out clean repositories immediately.
2. **Analysis & Contextual Intelligence:** Skips non-production paths. Indexes the repository using `ChromaDB` (Omniscient Context Engine).
3. **DEV-QA Bounty Loop (FinOps Circuit Breaker):** AI iteratively writes code and grades itself using strict criteria up to 3 cycles. Generates and executes PoCs in an isolated `DockerSandbox`.
4. **Validation & Auditing:** Patch efficacy and regression validations are enforced using a dual-pass check in Docker.
5. **PR Submission & Security Gate:** Submits PRs for direct fixes or proposes changes via an Issue-First workflow. A Security Disclosure Gate ensures sensitive vulnerabilities result in private disclosures rather than public PRs.

---

## 🛠️ Getting Started (1-Click Docker Quick-Start)

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Python** >= 3.11
* **Docker** >= 7.1
* **Git** installed on the host machine.

### Installation

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
   *(Alternatively, for local development, you can use `make install` to install the package and dev dependencies).*

3. **Environment Variables (`.env`)**
   Core environment variables required:
   ```env
   GITHUB_TOKEN=your_github_pat_here
   OPENROUTER_API_KEY=your_openrouter_key_here
   MINIMAX_API_KEY=your_minimax_api_key_here
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   ```

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage (CLI Commands)

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: Process a single target from target_repo.json
farm_agent hunt-circular

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Terminator Mode: Relentless 24/7 continuous operational loop
farm_agent superhuman

# Analyze a repository without creating contributions
farm_agent analyze <repo_url>

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Query current PR queue, runtime statistics, and LLM allocations
farm_agent status
farm_agent stats
farm_agent models
farm_agent leaderboard

# VIP Roster: Alumni Sync & Full Friendly Repo List
farm_agent vips

# View available contribution templates
farm_agent templates

# Run with thorough, standard, or quick presets
farm_agent profile <profile_name>

# Send a test notification to configured channels
farm_agent notify-test

# Show Farm-Agent system status (memory, PRs, rate limits)
farm_agent system-status

# Show current configuration
farm_agent config

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).