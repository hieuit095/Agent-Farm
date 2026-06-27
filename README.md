# 🛠️ Agent-Farm

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic)](https://docs.pydantic.dev/)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem that continuously crawls GitHub to discover vulnerabilities, generates precise patches, and dynamically validates fixes in an isolated Docker sandbox. Equipped with a strict multi-layered validation process and maintainer vibe analysis, it safely submits zero-regression pull requests or private disclosures directly to open-source maintainers.

---

## 🔥 Key Features

- **Omniscient Context Engine:** Uses ChromaDB RAG to semantically index repository documentation (`.md`, `.txt`, `.rst`) and maps AST-based dependencies (Python, Go, Rust, TypeScript) to inject deep contextual awareness into the LLM logic.
- **Dynamic Bug Verification & Sandboxing:** Generates self-contained Proof-of-Concept (PoC) scripts to verify vulnerabilities inside a secure DockerSandbox. Automatically drops unverified false positives.
- **Blast Radius & Regression Auditing:** Runs a double-pass check on patches to guarantee efficacy (the bug is resolved) and regression-free integrity (native test suite passes).
- **Anti-Farming & Zero-Garbage Gatekeepers:** Employs a strict multi-layered LLM filtering system (e.g., Qwen and Gemini) to ban trivial documentation updates and immediately veto low-quality changes.
- **Continuous Execution Loops:** Features a Terminator "Super Human" mode for relentless 24/7 scanning, patching, and PR patrolling (auto-replying to maintainer comments and fixing CI failures).
- **Security Disclosure Gate:** Automatically detects projects requiring private security disclosures and securely writes findings instead of creating public PRs.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm operates using a robust asynchronous pipeline orchestrator (`FarmAgentPipeline`). Target repositories are recursively analyzed using the `BloodhoundAnalyzer` and `RepoMapper`. Discovered vulnerabilities are validated through an Expert Appraiser filter (`Qwen`), after which fixes are drafted by `deepseek-v4-pro`. The fixes and generated PoCs are evaluated within a local containerized sandbox (`DockerSandbox`) for both efficacy and regression. Once patches clear the Supreme Auditor (`Gemini`), they are submitted via the `GitHubClient` and tracked in persistent SQLite memory (`Memory`).

---

## 🛠️ Getting Started

### Prerequisites

- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Docker Desktop must be running with socket accessible)
- **Git:** Installed on the host machine.
- **Credentials:** GitHub Personal Access Token (with `repo` scope) and an OpenRouter API Key.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   - **Windows:** Double-click `start.bat` or run `start.bat` in CMD.
   - **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   *(This initializes `.env`, builds the Docker image, and launches the daemon in the background.)*

3. **Manual Development Install (Optional):**
   ```bash
   python -m venv venv
   source venv/bin/activate
   make install
   ```

### Environment Variables

Configure your `.env` file (copied from `.env.example` during setup):

```env
GITHUB_TOKEN=your_github_pat_here
OPENROUTER_API_KEY=your_openrouter_key_here
TELEGRAM_BOT_TOKEN=optional_telegram_bot_token
MINIMAX_API_KEY=optional_minimax_key
```

---

## 💻 Usage

Agent-Farm is operated via a comprehensive CLI (`farm_agent`):

```bash
# Attach to the running Docker agent and launch the 24/7 Super Human loop
docker exec -it agent-farm farm_agent superhuman

# Alternatively, run CLI commands directly if installed locally:

# Discover targets and run the full pipeline
farm_agent run

# Target a specific repository directly for bug-hunting
farm_agent target <repo_url>

# Solve open GitHub issues on a specific repository
farm_agent solve <repo_url>

# Check open PRs for reviewer feedback and auto-push CI fixes
farm_agent patrol

# View system state and PR statistics
farm_agent status
farm_agent stats
```

---

## 🤝 Contributing

We welcome contributions from white-hat security researchers and AI engineers. Please ensure you use standard conventional commits. Run the local validation suites (`make lint` and `make test`) before opening a pull request.

## 📜 License

Licensed under the [MIT License](LICENSE).
