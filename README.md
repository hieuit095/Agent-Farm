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

## 🔥 Key Features (v4.0.0 Upgrades)

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Zero-Garbage PR Gatekeepers
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using DeepSeek (e.g., `deepseek-v4-pro`) to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏛️ System Architecture (High-Level)

Agent-Farm utilizes a custom "DeerFlow" registry-based agent architecture to coordinate execution.

1. **Discovery & Targeting**: The system scans GitHub or follows a deterministic round-robin target list (`target_repo.json`), cloning the target repository.
2. **Analysis & Indexing**: Uses Red Team Bloodhound heuristics and code analyzers (integrating Semgrep rules) to find potential vulnerabilities. Source files are mapped into an AST dependency graph, and documentation is vector-indexed in ChromaDB.
3. **Sandbox Generation**: For each finding, the Generator engine spawns a containerized Sandbox. A PoC script is written and executed. If it fails to reproduce the bug, the finding is discarded.
4. **DEV-QA Patching**: The LLM creates a patch. The sandbox runs the patch against the PoC and native test suites. Failing tests trigger an iterative, self-reflective repair loop.
5. **PR Submission**: If the patch passes auditing and gatekeeping, a PR is formed and pushed via the GitHub REST API.

---

## 🛠️ Getting Started

Agent-Farm provides a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker Desktop** installed and running.
* **Python 3.11+** (if running natively).
* **Git** installed on the host machine.
* A GitHub Personal Access Token (PAT) with `repo` scope.
* An OpenRouter API Key configured with credits.

### 1-Click Docker Quick-Start

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
   ```env
   GITHUB_TOKEN=your_github_pat_here
   OPENROUTER_API_KEY=your_openrouter_key_here
   ```

4. **Attach to the Agent CLI:**
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

### Native Installation (Development)

1. Clone the repository and navigate to the directory.
2. Initialize `.env` and `config.yaml`:
   ```bash
   cp .env.example .env
   cp config.example.yaml config.yaml
   ```
3. Use the `Makefile` to install the package and dev dependencies:
   ```bash
   make install
   ```
4. Run tests to verify the installation:
   ```bash
   make test
   ```

---

## ⚙️ CLI Command Reference

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <url>

# Solve open issues in a specific repository
farm_agent solve <url>

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt [--rounds N] [--mode analysis|issues|both]

# Circular Target Loop: deterministic round-robin from target_repo.json
farm_agent hunt-circular

# Run the Relentless 24/7 Super Human loop (patrols PRs and hunts targets)
farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Analyze a repository without generating contributions or PRs
farm_agent analyze <url>

# Query current PR queue, runtime statistics, and LLM allocations
farm_agent status
farm_agent stats
farm_agent models
farm_agent leaderboard

# Run with thorough, standard, or quick presets
farm_agent profile <name>

# View available execution templates
farm_agent templates

# Manage VIP repositories radar list
farm_agent vips

# View the active configuration
farm_agent config

# Send a test notification to configured Telegram/Slack/Discord
farm_agent notify-test

# Check overall system and database status
farm_agent system-status

# Scan and close low-quality/garbage PRs submitted on GitHub
farm_agent janitor

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
