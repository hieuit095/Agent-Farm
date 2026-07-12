# 🛠️ Agent-Farm

**Autonomous Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

*   **Omniscient Context Engine:** Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links directly into the prompt context.
*   **Anti-Farming Filter:** Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
    *   **Layer 1 Expert Appraisal (Qwen):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
    *   **Layer 2 Supreme Audit (Gemini):** Evaluates the complete incident dossier, fix, and sandbox logs before finalizing PR creation.
*   **Dynamic Bug Verification (PoC Execution):** Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script to dynamically trigger the vulnerability inside a locked-down DockerSandbox. If the PoC fails to trigger the bug, the finding is classified as a False Positive and dropped.
*   **Blast Radius & Regression Auditing:** Validates generated patches in isolated Docker sandboxes through a double-pass check:
    *   **Efficacy Validation:** Applies the patch and re-runs the PoC to ensure the vulnerability is completely resolved.
    *   **Regression Auditing:** Executes the project's native test suite to ensure the patch does not break any existing functionality or downstream dependent modules.
*   **Terminator Mode:** A relentless continuous execution loop without artificial delays, pulling targets exclusively from the SQLite `target_repos` table.
*   **DEV-QA Bounty Loop:** A multi-agent feedback circuit where patches are evaluated by a strict QA Scorer; failures generate lessons and automatically trigger LLM self-correction with error traceback data.

---

## 🏗️ System Architecture (High-Level)

Agent-Farm operates as a multi-stage orchestration pipeline connected to external GitHub resources and local tooling:
1.  **Target Discovery & Intelligence:** The pipeline locates repositories matching specific criteria or retrieves them from a local queue. The `BloodhoundAnalyzer` scans for patterns using `ast-grep` and `Semgrep`, while the `RepoIndexer` maps codebase structure and documentation.
2.  **Appraisal & Triage:** Findings undergo a strict verification checklist (Devil's Advocate Gate) and the Layer 1 Expert Appraisal to eliminate hallucinations or unexploitable edge cases.
3.  **DEV-QA Loop & Verification:** A PoC is built and executed inside an isolated Docker container. A patch is then generated, injected with context, and evaluated by the QA module.
4.  **Sandbox Validation:** The patched code is run through the DockerSandbox to evaluate efficacy and regressional safety.
5.  **Supreme Audit & Execution:** A Layer 2 Supreme Auditor analyzes all logs. On approval, the system submits a PR or initiates a private security disclosure if required by the target repository's policies.

---

## 🛠️ Getting Started

Agent-Farm utilizes a robust, pre-configured Docker setup that mounts the Docker socket from the host to spawn sibling containers for isolated PoC and test execution.

### Prerequisites

*   **Docker Desktop** (>= 7.1) running on the host machine.
*   **Python** (>= 3.11)
*   **Git** installed.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hieuit095/Agent-Farm.git
    cd Agent-Farm
    ```

2.  **Run the Quick-Start Script (1-Click Docker Launch):**
    *   **Windows:** Double-click `start.bat` or run:
        ```cmd
        start.bat
        ```
    *   **Unix (Linux/macOS):**
        ```bash
        chmod +x start.sh
        ./start.sh
        ```
    *Note: The script will pull the latest codebase, initialize your `.env` configuration file from `.env.example`, build the Docker image, and launch the daemon.*

3.  **Local Installation:**
    If you prefer to install locally, use the provided Make target to install the package along with its development dependencies.
    ```bash
    make install
    ```

### Environment Variables

Configure the following exact `.env` variables required to run the project. These should be populated in the `.env` file in the project root:

*   `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with `repo` scope.
*   `MINIMAX_API_KEY`: API Key for Janitor.
*   `OPENROUTER_API_KEY`: Your primary API Key for routing requests to LLMs (DeepSeek, Qwen, Gemini).
*   `TELEGRAM_BOT_TOKEN`: (Optional) Your Telegram Bot Token for operational notifications.

---

## ⚙️ Usage

Agent-Farm provides a comprehensive suite of Click-based CLI utilities. You can execute these inside the running Docker container or directly if installed locally.

**Core CLI Commands:**

*   `farm_agent run`: Auto-discover repositories and run the full contribution pipeline.
*   `farm_agent target <url>`: Process a specific target repository directly.
*   `farm_agent hunt`: Hunt mode for multi-round target discovery and aggressive analysis.
*   `farm_agent hunt-circular`: Deterministic round-robin execution loop from the local `target_repo.json`.
*   `farm_agent superhuman`: Runs Terminator Mode—a relentless 24/7 continuous operational loop.
*   `farm_agent patrol`: Checks open PRs for review feedback, replies to questions, and auto-fixes CI failures.
*   `farm_agent solve <url>`: Focuses specifically on solving open issues within a repository.
*   `farm_agent analyze <url>`: Perform a code analysis pass only; do not generate contributions.
*   `farm_agent status`: Show status of submitted PRs.
*   `farm_agent stats`: Show overall Agent-Farm statistics.

*Example - Enter the container and run superhuman mode:*
```bash
docker exec -it agent-farm farm_agent superhuman
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

Licensed under the [MIT License](LICENSE).
