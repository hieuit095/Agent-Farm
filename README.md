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

- **Omniscient Context Engine**: Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation, semantically chunks docs by headers, and indexes them. It builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents").
- **Anti-Farming Filter**: Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs. Implements a two-layer filter system: Gate 1 (Layer 1 Appraisal with Qwen-3.7-Max) for strict verdicts on findings, and Gate 2 (Layer 2 Supreme Audit with Gemini-3.5-Flash) for vetoing low-effort spam.
- **Dynamic Bug Verification (PoC Execution)**: Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using DeepSeek models (e.g., `deepseek-v4-pro`) to dynamically trigger the vulnerability inside a locked-down container sandbox.
- **Blast Radius & Regression Auditing**: Validates generated patches in isolated Docker sandboxes through a double-pass check: Pass 1 (Efficacy) and Pass 2 (Regression) against the native test suite.
- **Terminator Mode**: A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite `target_repos` table to relentlessly patrol PRs and hunt targets.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm orchestrates an autonomous contribution pipeline utilizing a modular architecture:
- **Orchestrator (`FarmAgentPipeline`)**: Coordinates the main workflow involving the GitHub client, Memory (SQLite), Code Analyzer, Contribution Generator, and PR Manager.
- **Core Loop**: Operates a circular target loop for DEV-QA bounties with token pool rotation.
- **Execution Environments**: Two secure Docker networks are utilized—an `internet_access` bridge for external communication (APIs, cloning) and a `sandbox_isolated` network where `DockerSandbox` safely executes PoCs and validates blast radius without compromising the host system.

---

## 🛠️ Getting Started

### Prerequisites
- **Docker**: version >= 7.1 (Docker Desktop running on host)
- **Python**: version >= 3.11
- **Git** installed on the host machine.
- Valid API Keys for GitHub and OpenRouter.

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
   *Note: The script will pull the codebase, initialize `.env`, build the Docker image, and launch the daemon in the background.*

### Environment Variables

The project uses a `.env` file for configuration. Based on `.env.example`, configure the following core variables required to run the project via 1-Click Launch:

```env
# GitHub Authentication (Required)
GITHUB_TOKEN=your_github_pat_here

# OpenRouter (Required for Red Team Bloodhound audits & DeepSeek usage)
OPENROUTER_API_KEY=your_openrouter_key_here
```

---

## ⚙️ Usage

Once the Docker environment is running, you can attach to the Agent CLI to execute operations.

### Core CLI Commands

Attach to the running container and use the `farm_agent` CLI:

```bash
docker exec -it agent-farm farm_agent <command>
```

**Available Commands:**
- `farm_agent run`: Start the full automated discovery, analysis, and contribution pipeline.
- `farm_agent target <repo_url>`: Target a specific repository directly.
- `farm_agent solve <repo_url>`: Solve open issues in a specific repository (Issue-First Pipeline).
- `farm_agent hunt [--rounds N] [--mode analysis|issues|both]`: Aggressively discover repos and solve issues/bugs.
- `farm_agent hunt-circular`: Run the circular target loop.
- `farm_agent superhuman`: Run Terminator Mode, a relentless continuous execution loop pulling from the `target_repos` table.
- `farm_agent patrol`: Check open PRs for maintainer comments, answer queries, and push CI auto-fixes (PR Patrol).
- `farm_agent status`: Query current PR queue and run status.
- `farm_agent stats`: View runtime statistics.
- `farm_agent leaderboard`: View leaderboard statistics.
- `farm_agent profile <profile_name>`: Run with thorough, standard, or quick presets.
- `farm_agent vips`: Alumni Sync + Full Friendly Repo List.
- `farm_agent analyze`: Analyze a repository.
- `farm_agent reset-db`: Clear run logs and start with a fresh target pipeline queue.
- `farm_agent config`: View or update configuration.
- `farm_agent models`: Query configured LLM models.
- `farm_agent cleanup`: Clean up forks.
- `farm_agent gc`: Garbage collection to purge stale knowledge base entries.
- `farm_agent templates`: Manage built-in templates.
- `farm_agent notify-test`: Test notification system.
- `farm_agent system-status`: Check overall system status.

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats.

Licensed under the [MIT License](LICENSE).
