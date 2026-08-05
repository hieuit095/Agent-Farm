# 🛠️ Agent-Farm

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor**

[![Python Version](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous system that automatically contributes to open-source projects on GitHub. Operating as a tireless security researcher and developer, it crawls GitHub for active repositories, pinpoints real vulnerabilities or code flaws using static analysis and LLM appraisal, verifies bugs dynamically via local sandboxes, and autonomously generates regression-free patches and Pull Requests.

---

## 🔥 Key Features

* **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It indexes internal documentation and constructs AST-based call graphs to inject precise module dependency links directly into LLM context.
* **Dynamic Bug Verification (PoC Execution):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down Docker container. Findings that fail this trigger are marked as false positives and dropped.
* **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check. It verifies the fix's efficacy by running the PoC again and audits for regressions by executing the project's native test suite.
* **Anti-Farming Filter:** A zero-tolerance gatekeeper that drops low-effort, trivial PRs such as typo fixes, style formatting, or documentation tweaks (which are strictly banned).
* **Multi-Layer Supreme Audit:** Utilizes Qwen (Layer 1 Appraiser) to rigorously debunk and filter Red Team bug claims, followed by Gemini (Layer 2 Supreme Auditor) to veto incomplete patches or sandbox regressions before PR deployment.
* **Terminator Mode & PR Patrol:** A continuous 24/7 execution loop (`superhuman`) that tirelessly hunts targets and solves issues, combined with `patrol` mode which checks open PRs for maintainer feedback and autonomously pushes code fixes or conversational replies.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm's orchestration relies on the `FarmAgentPipeline`, which pipelines operations through several distinct components.
1. **Target Discovery:** Evaluates target repositories retrieved from GitHub or local deterministic queues using the SQLite `Memory` module.
2. **Analysis & Appraisal:** A dual-layer scan pairs `BloodhoundAnalyzer` (Semgrep) with a Qwen Layer 1 LLM Appraiser to evaluate repository security posture.
3. **Verification & Fix Generation:** Valid findings are sent to the 3-cycle DEV-QA loop (`ContributionGenerator` and `QAHardcoreScorer`), leveraging DeepSeek models. Bug triggers and patches are locally executed and validated against native test suites within `DockerSandbox`.
4. **Final Gate & Dispatch:** Gemini functions as the Layer 2 Supreme Auditor. Approved patches are funneled through the `PRManager` to issue Pull Requests or private security disclosures via the GitHub API.

All persistent states, from PR outcomes to knowledge base lessons, are maintained resiliently via a WAL-enabled SQLite database.

---

## 🚀 Getting Started

### Prerequisites

* **Python:** `>= 3.11`
* **Docker:** `>= 7.1`
* **Git** installed on the host machine.
* OpenRouter and Minimax API Keys.
* A GitHub Personal Access Token (PAT) with `repo` scope.

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```

2. **1-Click Docker Launch**
   Agent-Farm provides pre-configured launch scripts to seamlessly bring up the Docker environment alongside network bridging.
   * **Windows:**
     ```cmd
     start.bat
     ```
   * **Unix (macOS/Linux):**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

3. **Local Installation (Development)**
   If setting up outside of Docker, install the package and its dev dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   make install
   ```

### Environment Variables

Configure your API keys by copying `.env.example` to `.env`. The exact required and optional keys are:

```env
# Core Authentication
GITHUB_TOKEN=your_github_pat
OPENROUTER_API_KEY=your_openrouter_api_key

# Additional Options
GITHUB_SECONDARY_TOKENS=comma_separated_tokens
EXCLUDED_LANGUAGES=javascript,typescript
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_GROUP_ID=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
```

---

## 💻 Usage (CLI)

The `farm_agent` CLI is the main interface. When running via Docker, prefix these commands with `docker exec -it agent-farm`.

**Run standard pipeline (Discovery -> Analyze -> Generate PR):**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Analyze without creating PRs (Dry run analysis):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Solve open issues on a repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Continuous Terminator Mode (Super Human):**
```bash
farm_agent superhuman
```

**Patrol open PRs and auto-respond/fix:**
```bash
farm_agent patrol
```

---

## 📜 Contributing & License

We welcome open-source contributions to make the autonomous agent even smarter. Ensure tests pass before pushing (`make test`).

Licensed under the [MIT License](LICENSE).
