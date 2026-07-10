# 🛠️ Agent-Farm (v4.0.0)

**Autonomous AI Agent for Automated GitHub Contributions & Security Research**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is a completely autonomous system that acts as a Principal Software Architect and Security Researcher. It hunts for repositories on GitHub, analyzes their codebase for critical vulnerabilities or bugs, validates findings via dynamic Proof-of-Concept execution in an isolated Docker sandbox, and automatically submits pristine, regression-free pull requests or private security disclosures.

---

## 🔥 Key Features (v4.0.0)

- **Omniscient Context Engine (RAG Codebase Mapping):**
  Utilizes ChromaDB to ingest repository documentation, mapping local AST module dependencies and function linkages to provide LLMs with deep contextual awareness of the entire subsystem architecture.
- **Dynamic Bug Verification:**
  Generates and executes exploit Proof-of-Concept (PoC) scripts dynamically inside a locked-down container sandbox. Findings that fail to trigger the bug are instantly dropped as false positives.
- **Blast Radius & Regression Auditing:**
  Applies the generated patch and validates it in a double-pass process: Efficacy (verifying the PoC no longer triggers) and Regression (running the native test suite, e.g., `pytest`, `npm test`, `cargo test`, to ensure no existing functionality is broken).
- **Anti-Farming Filter (Zero-Garbage PRs):**
  A ruthless two-layer LLM filter (Qwen-3.7-Max appraiser + Gemini-3.5-Flash auditor) strictly blocks typo fixes, documentation-only patches, and low-impact changes. Only CRITICAL/HIGH security vulnerabilities or substantive code fixes proceed.
- **Terminator Mode:**
  A relentless, automated continuous execution loop (`superhuman`) that cycles between hunting targets, discovering flaws, and actively patrolling open PRs to address CI failures and maintainer comments.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm operates through a sequential pipeline driven by a primary orchestrator:
1. **Target Discovery & Initial Recon:** Crawls GitHub for repositories matching specific criteria, clones them, and establishes a testing baseline.
2. **Contextual Analysis:** Chunks repository documentation and maps the AST graph (via Semgrep/Bloodhound rules and RAG memory), allowing the agent to deeply understand the architecture.
3. **Appraisal & Bug Validation:** Candidate vulnerabilities are filtered through a strict Layer-1 Appraiser. Validated bugs are proven dynamically inside an isolated Docker sandbox using an auto-generated Proof-of-Concept (PoC).
4. **DEV-QA Patch Generation:** Fixes are generated and validated using a closed-loop system. The patch is applied and must pass both the PoC efficacy test (bug resolved) and native regression tests within the Sandbox.
5. **Supreme Audit & PR Creation:** A final Layer-2 Auditor reviews the sandbox execution dossier before submitting a PR or routing to private security disclosure channels.

---

## 🛠️ Getting Started (1-Click Docker Launch)

The recommended way to run Agent-Farm is via its robust Docker environment, which correctly handles the execution of isolated Docker-in-Docker sandboxes.

### Prerequisites
- **Docker** >= 7.1 (Docker Desktop)
- **Git** installed on the host
- A valid **GitHub Personal Access Token**
- An **OpenRouter API Key** (or another supported LLM provider)

### Installation & Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Initialize Environment Variables:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   **Required `.env` Variables:**
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with repository permissions.
   - `OPENROUTER_API_KEY`: Your OpenRouter API key to access underlying LLM providers (e.g., DeepSeek, Qwen, Gemini).

   *(Optional variables such as `TELEGRAM_BOT_TOKEN`, `MINIMAX_API_KEY`, and `EXCLUDED_LANGUAGES` can also be configured if using specific notification channels or alternative LLM configurations).*

3. **1-Click Launch (Docker Desktop Quick-Start):**
   * **Windows:** Double-click `start.bat`
   * **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

4. **Attach to the Agent CLI:**
   Once the daemon is running, attach to the container to run commands:
   ```bash
   docker exec -it agent-farm farm_agent superhuman
   ```

---

## ⚙️ Usage & CLI Reference

Agent-Farm provides a comprehensive CLI for managing its various hunting and patrolling modes:

```bash
# Start the Terminator Mode (24/7 relentless target hunting and PR patrolling)
farm_agent superhuman

# Target a specific repository directly
farm_agent target <https://github.com/owner/repo>

# Solve open issues in a specific repository
farm_agent solve <https://github.com/owner/repo>

# Hunt Mode: discover random high-value repos and contribute aggressively
farm_agent hunt --rounds 5 --mode both

# Circular Target Loop: run deterministic hunting from target_repo.json
farm_agent hunt-circular

# PR Patrol: review comments on open PRs and auto-fix CI failures
farm_agent patrol

# Show overall runtime statistics and OpenRouter usage
farm_agent stats

# Display the status of all submitted pull requests
farm_agent status
```

---

## 📜 Contributing & License

Contributions are welcome! Please ensure you have read the architecture documentation (`PROJECT_MAP.md`) and run the test suite (`make test`) before submitting PRs.

This project is licensed under the [MIT License](LICENSE).
