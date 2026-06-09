# 🛠️ Agent-Farm (Farm-Agent)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-%3E%3D7.1-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

* **Omniscient Context Engine:** Uses Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and builds AST-based call graphs to inject precise module dependency links ("imports", "calls", "dependents") into the prompt context.
* **Dynamic Bug Verification (PoC Execution):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down Docker sandbox.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated sandboxes through a double-pass check. Pass 1 applies the patch and re-runs the PoC. Pass 2 executes the project's native test suite to ensure no regressions are introduced.
* **Zero-Garbage PR Gatekeepers:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs. Enforces a two-layer filter system using Qwen-3.7-Max (Expert Appraisal) and Gemini-3.5-Flash (Real-World Value Check) to drop theoretical issues or patches for deprecated code.
* **Super Human Mode:** A relentless 24/7 autonomous execution loop (`farm_agent superhuman`) that cycles through target hunting and PR patrol operations with simulated human coding delays.
* **PR Patrol & Issue Solver:** Actively monitors open PRs to auto-reply to maintainer comments and self-correct CI failures (`farm_agent patrol`), or proactively solves existing repository issues (`farm_agent solve`).

---

## 🏗️ System Architecture (High-Level)

Agent-Farm relies on a custom registry-based 'DeerFlow' agent architecture. It discovers targets and begins a complex, multi-phase contribution pipeline. It evaluates the project by fetching guidelines, cloning the repository, mapping the structural dependencies, and indexing documentation. Then, utilizing the Bloodhound Red Team pipeline (powered by Semgrep and DeepSeek models), it hunts for high-severity issues. All findings go through stringent QA gates and multi-model verification (Qwen, Gemini). Code changes and PoCs are dynamically run in an isolated Docker sandbox. Validated changes proceed to either create a public Pull Request or file a private security disclosure. State and history are stored persistently using a WAL-mode SQLite database (`memory.db`).

---

## 🛠️ Getting Started

### Prerequisites

* **Python:** 3.11, 3.12, or 3.13
* **Docker Engine:** v7.1 or higher (required for isolated sandbox environment)
* **Git:** Installed and available in PATH

### Installation

**Option 1: 1-Click Docker Quick-Start**

Clone the repository and launch the containerized environment. This automatically mounts the host Docker socket for spawning isolated PoC and test execution containers.

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent

# On Windows:
start.bat

# On Unix (Linux/macOS):
chmod +x start.sh
./start.sh
```

**Option 2: Local Development Setup**

Set up the project locally using pip and the provided Makefile.

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent

# Install the package and development dependencies
make install
# Alternatively: pip install -e '.[dev]'
```

### Environment Variables

Agent-Farm requires specific environment variables to function correctly. Copy `.env.example` to `.env` and configure the following:

* `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with `repo`, `read:org`, and `workflow` scopes. (Falls back to `gh auth token` CLI if left empty).
* `OPENROUTER_API_KEY`: API key for OpenRouter, required for routing LLM calls through DeepSeek, Qwen, and Gemini models.
* `MINIMAX_API_KEY`: Optional; required only if setting Minimax as the provider in `config.yaml`.
* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: Optional; for receiving push notifications regarding merged PRs, closed issues, and runs.

---

## 💻 Usage

Agent-Farm is operated via a robust Click-based CLI application. Below are some of the primary commands:

```bash
# Run the relentless 24/7 Super Human loop (patrols PRs and hunts targets)
farm_agent superhuman

# Start the full automated discovery, analysis, and contribution pipeline
farm_agent run

# Target a specific repository directly
farm_agent target <url>

# Solve open issues in a specific repository
farm_agent solve <url>

# Analyze a repository without submitting any contributions
farm_agent analyze <url>

# Hunt Mode: aggressively discover repos and solve issues/bugs
farm_agent hunt --rounds 5

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
farm_agent patrol

# Show current PR queue status, runtime statistics, or loaded configuration
farm_agent status
farm_agent stats
farm_agent config

# Scan and close low-quality/garbage PRs submitted on GitHub
farm_agent janitor
```

---

## 🤝 Contributing

We welcome contributions from white-hat security researchers and AI engineers! Please ensure all code changes align with the existing architectural patterns and strictly enforce the `Ruff` styling conventions. Before opening a PR, always run:

```bash
make lint
make test
```

## 📄 License

Agent-Farm is licensed under the [MIT License](LICENSE).
