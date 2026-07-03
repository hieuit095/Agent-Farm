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
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Zero-Garbage PR Gatekeepers
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Layer 1: The Appraiser (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Layer 2: Supreme Auditor (Gemini-3.5-Flash):** Final gate before a report or patch is deployed, ensuring the root cause analysis makes sense and the sandbox logs are completely clean.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox (`DockerSandbox`). If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

### 🩸 Bloodhound Red Team
Runs an initial Semgrep pre-scan before expensive LLM analysis to identify vulnerabilities reliably.

### 🤖 Terminator Mode
A relentless 24/7 continuous execution loop (`farm_agent superhuman`) that automatically pulls targets exclusively from the SQLite `target_repos` table, interleaving Hunt mode and PR Patrol without artificial delays.

### 💬 Issue-First Pipeline & PR Patrol
For non-critical findings, the agent opens a polite GitHub Issue first instead of a PR (`farm_agent solve`). The `PR Patrol` scans open PRs for maintainer review feedback and auto-responds or pushes fix updates.

---

## 🏗️ System Architecture (High-Level)

The main `FarmAgentPipeline` coordinates the entire contribution flow:
1. **Discovery**: Searches GitHub for high-star, active repositories that match given criteria (e.g., using `DatabaseTargetDiscovery`).
2. **Analysis**: Uses the `BloodhoundAnalyzer` and `CodeAnalyzer` to find vulnerabilities, while checking repo policies, fetching `CONTRIBUTING.md`, and assessing maintainer vibe.
3. **Validation & PoC**: Verifies the vulnerability via `DockerSandbox` with a generated PoC. Validates with Layer 1 Appraiser.
4. **Generation & DEV-QA Loop**: Uses `ContributionGenerator` to write patches, evaluated by the `QAHardcoreScorer` in a 3-cycle loop.
5. **Sandbox Regression Audit**: Clones the repo, applies the patch, checks efficacy, and runs native tests inside `DockerSandbox`.
6. **PR / Issue Creation**: The `PRManager` submits a pull request (if critical) or an issue proposal, after a final check by the Layer 2 Supreme Auditor and the Security Disclosure Gate.

---

## 🛠️ Getting Started

### Prerequisites
* **Python**: 3.11+
* **Docker**: 7.1+ (Docker Desktop running on the host machine)
* **Git**: Installed
* **GitHub Personal Access Token (PAT)** with `repo` scope.
* **OpenRouter API Key** configured with credits (used for DeepSeek, Qwen, and Gemini models).

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **1-Click Docker Launch:**
   * **Windows:** Double-click `start.bat` or run:
     ```cmd
     start.bat
     ```
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   * *Note: The script will automatically pull the codebase, initialize your `.env` configuration file from `.env.example`, build the Docker image, and launch the daemon in the background.*

### Environment Variables

Configure your `.env` file (or `config.yaml`) with required tokens:
```env
GITHUB_TOKEN=your_github_pat_here
OPENROUTER_API_KEY=your_openrouter_key_here
TELEGRAM_BOT_TOKEN=optional_telegram_token
```

---

## 💻 Usage

Agent-Farm provides a comprehensive suite of Click-based CLI utilities:

```bash
# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target https://github.com/owner/repo

# Solve open issues in a specific repository
farm_agent solve https://github.com/owner/repo

# Run in Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt --rounds 5 --mode both

# Run Terminator Mode: relentless 24/7 continuous execution loop
farm_agent superhuman

# Patrol: check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Query current PR queue, runtime statistics, and configurations
farm_agent status
farm_agent stats
farm_agent config
farm_agent leaderboard

# Run with thorough, standard, or quick presets
farm_agent profile <profile_name>

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
farm_agent gc --days 90

# View Alumni Sync + Full Friendly Repo List
farm_agent vips
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
