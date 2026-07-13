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
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.

### 🛡️ Anti-Farming Filter
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a strict two-layer filtering system:
* **Gate 1: Layer 1 Appraisal (Qwen):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: Layer 2 Supreme Audit (Gemini):** Conducts a high-level review to verify real-world value and vetoes patches targeting dead or deprecated code blocks.

### 🧪 Dynamic Bug Verification
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down container sandbox (`DockerSandbox`). If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm orchestrates an advanced `FarmAgentPipeline` composed of several critical stages:
1. **Discovery & Reconnaissance:** Iterates through target repositories (or hunts dynamically), cloning them into a temporary space, extracting guidelines, and identifying core files.
2. **Analysis & Contextualization:** Uses the `CodeAnalyzer` alongside the **Omniscient Context Engine** to perform deep static analysis, finding security issues and bugs.
3. **Generation & Proof-of-Concept:** The `ContributionGenerator` writes fixes, but first verifies them dynamically using isolated Docker execution to avoid regressions.
4. **Peer Review & Auditing:** The `ReviewerAgent` audits the generated changes, validating blast radius and style guide adherence.
5. **Submission:** Finally, the `PRManager` submits a heavily scrutinized pull request.
6. **Continuous Patrol:** A relentless execution loop ("Terminator Mode") continually checks open PRs for maintainer comments, auto-heals CI errors, and hunts new targets without artificial delays.

---

## 🛠️ Getting Started

Agent-Farm utilizes a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites
* **Docker Desktop** (version >= 7.1) installed and running.
* **Git** installed on the host machine.
* **Python** (version >= 3.11).
* A GitHub Personal Access Token (PAT) with `repo` scope.
* An OpenRouter API Key configured with credits.

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

You must configure the `.env` file (created automatically by the Quick-Start scripts from `.env.example`). The exact core variables required are:

* `GITHUB_TOKEN`: Your Personal Access Token with repo, read:org, and workflow scopes.
* `OPENROUTER_API_KEY`: API key for OpenRouter, used to route LLM queries and Bloodhound White-Hat audits.
* `TELEGRAM_BOT_TOKEN` (Optional): Bot token for push notifications (merge, close, run complete).
* `TELEGRAM_CHAT_ID` (Optional): The destination chat ID for notifications.

---

## ⚙️ Usage & CLI Commands

To execute commands within the running container environment, attach to the running `agent-farm` instance:

```bash
# Attach to the Agent CLI and execute Terminator Mode (relentless 24/7 continuous loop)
docker exec -it agent-farm farm_agent superhuman
```

### Core CLI Reference

The `farm_agent` CLI tool supports the following core commands:

* `farm_agent run`: Start the standard automated discovery, analysis, and contribution pipeline.
* `farm_agent target <repo_url>`: Target a specific repository directly.
* `farm_agent solve <repo_url>`: Solve open issues in a specific repository (Issue-First Pipeline).
* `farm_agent hunt`: Aggressively discover repos and solve issues/bugs.
* `farm_agent hunt-circular`: Continuously loop over targets for hunting.
* `farm_agent superhuman`: Run "Terminator Mode" — a relentless continuous execution loop without delays.
* `farm_agent patrol`: Check open PRs for maintainer comments and push CI auto-fixes ("PR Patrol").
* `farm_agent analyze`: Run static code analysis against a given repository.
* `farm_agent vips`: View Alumni Sync + Full Friendly Repo List.
* `farm_agent status`: Query current PR queue and execution status.
* `farm_agent stats`: Show total findings and pipeline statistics.
* `farm_agent system-status`: Display system memory, PR outcomes, and rate limits.
* `farm_agent models`: List available multi-model configurations.
* `farm_agent leaderboard`: View the contribution leaderboard and success rates.
* `farm_agent profile <profile_name>`: Run with thorough, standard, or quick presets.
* `farm_agent templates`: Manage generation templates.
* `farm_agent config`: View and adjust system configurations.
* `farm_agent notify-test`: Send a test notification.
* `farm_agent cleanup`: Clean up closed/merged forks.
* `farm_agent gc`: Run garbage collection to purge stale knowledge base entries.
* `farm_agent reset-db`: Clear run logs and start with a fresh queue.

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
