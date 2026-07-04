# 🛠️ Agent-Farm (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to systematically crawl GitHub, pinpoint security vulnerabilities and code flaws, and automatically contribute to open-source projects. Operating with human-like precision, it implements an advanced, self-correcting DEV-QA loop that validates proposed fixes dynamically in an isolated sandbox, ensuring every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

- **Omniscient Context Engine**: Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
- **Dynamic Bug Verification**: Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down Docker sandbox.
- **Blast Radius & Regression Auditing**: Validates generated patches in isolated Docker sandboxes via a double-pass check: ensuring the PoC vulnerability is resolved, and executing the project's native test suite to ensure downstream dependent modules are not broken.
- **Zero-Garbage PR Gatekeepers**: Enforces strict filtering using a two-layer AI filter. Layer 1 Appraisal (via `qwen3.7-max`) and Layer 2 Supreme Audit (via `gemini-3.5-flash`) strictly block typo-fixes, formatting tweaks, and documentation-only PRs while vetoing patches against dead code.
- **Terminator Mode**: A relentless continuous execution loop without artificial delays that patrols PRs, handles interactions, and hunts new targets exclusively from the SQLite `target_repos` table.

---

## 🏗️ System Architecture

Agent-Farm orchestrates an autonomous DEV-QA loop through an integrated pipeline. The system clones target repositories and parses the code through its **CodeAnalyzer**, while the **Omniscient Context Engine** extracts deep architectural insights and dependencies. The **ContributionGenerator** then drafts a fix. Critically, the pipeline isolates testing using the **DockerSandbox**, where a dynamically created PoC executes to prove the exploit, followed by testing the generated patch. Only after a rigorous Blast Radius & Regression Auditing pass is the verified patch finalized and submitted as a pull request by the **PR Manager**.

---

## 🛠️ Getting Started

### Prerequisites

- **Python** >= 3.11
- **Docker** >= 7.1
- **Git**
- A GitHub Personal Access Token (PAT) with `repo` scope.
- An OpenRouter API Key configured with credits.

### 1-Click Installation & Launch

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **Run the Quick-Start Script:**
   The repository includes automated scripts that handle `.env` initialization, pull the latest code, build the Docker images, and launch the daemon in the background via Docker Desktop.

   - **Windows:** Double-click `start.bat` or run:
     ```cmd
     start.bat
     ```
   - **Unix (Linux/macOS):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

### Environment Variables

Your `.env` file must be configured with at least the following primary keys to function correctly:
- `GITHUB_TOKEN`
- `OPENROUTER_API_KEY`
- `TELEGRAM_BOT_TOKEN` (optional, for notifications)

---

## ⚙️ Usage

Once the daemon is running, you can interface directly with the agent inside the container:

```bash
# Attach to the container and start the relentless continuous execution loop (Terminator Mode)
docker exec -it agent-farm farm_agent superhuman

# Start the full automated discovery, analysis, and contribution pipeline
docker exec -it agent-farm farm_agent run

# Target a specific repository to discover and solve issues
docker exec -it agent-farm farm_agent target <repo_url>
docker exec -it agent-farm farm_agent solve <repo_url>

# Check open PRs for maintainer comments and push CI auto-fixes
docker exec -it agent-farm farm_agent patrol

# Show system status, memory metrics, and API quotas
docker exec -it agent-farm farm_agent system-status
docker exec -it agent-farm farm_agent stats
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute. Please follow conventional commit formats and ensure your patches are verified.

Licensed under the [MIT License](LICENSE).
