# 🛠️ Agent-Farm (v4.0.0)

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Agent-Farm is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or code flaws, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features (v4.0.0)

*   **Omniscient Context Engine**: Uses Local RAG powered by ChromaDB to index documentation and build AST-based dependency graphs, providing complete semantic and linkage context.
*   **Dynamic Bug Verification**: Generates a self-contained Proof-of-Concept (PoC) to trigger vulnerabilities inside an isolated `DockerSandbox`, dropping findings if unverified.
*   **Zero-Garbage PR Gatekeepers**: Strict, two-layer LLM filter system that blocks trivial/documentation changes and vets fixes for high-impact real-world value.
*   **Blast Radius & Regression Auditing**: Employs double-pass patch validation to confirm efficacy and ensure changes pass the native test suite without breaking downstream modules.
*   **Super Human Loop Engine**: A relentless 24/7 autonomous scheduler (`SuperHumanLoop`) integrating pipeline analysis, PR patrols, and randomized execution delays for stealthy, organic operation.

---

## 🏗️ System Architecture (High-Level)

The application centers around a custom registry-based "DeerFlow" architecture orchestrating a **Circular Target Loop** (`FarmAgentPipeline`). Repositories are fetched via a GitHub client implementing rate-limit and token rotation defenses.

Upon scanning, code is passed to the **Omniscient Context Engine**, feeding `BloodhoundAnalyzer` and `CodeAnalyzer` which detect flaws and validate via isolated PoCs in a `DockerSandbox`. The `ContributionGenerator` works through the DEV-QA bounty loop, while the multi-tiered filter (Qwen-3.7-Max and Gemini-3.5-Flash via `OpenRouterProvider`) drops low-value patches. Validated contributions are pushed through an Issue-First or Direct PR path, tracked within an SQLite-backed WAL persistent memory.

---

## 🛠️ Getting Started

### Prerequisites

*   **Python:** >= 3.11
*   **Docker:** Docker Desktop installed with Daemon running.
*   **Git:** Local installation to manage repository operations.

### Installation & Launch

Agent-Farm provides a pre-configured Docker setup and wrapper scripts for easy deployment.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hieuit095/Farm-Agent.git
    cd Farm-Agent
    ```

2.  **Environment Variables:**
    Copy the example `.env` and fill in required fields:
    ```bash
    cp .env.example .env
    ```
    *Required keys:*
    *   `GITHUB_TOKEN`: Your GitHub PAT.
    *   `MINIMAX_API_KEY`: Key for the primary LLM provider.
    *   `OPENROUTER_API_KEY`: Key for Red Team audits / alternate models.
    *   `TELEGRAM_BOT_TOKEN`: (Optional) For notifications.

3.  **Run the Quick-Start Script:**
    *   **Unix (Linux/macOS):**
        ```bash
        chmod +x start.sh
        ./start.sh
        ```
    *   **Windows:**
        ```cmd
        start.bat
        ```
    This script pulls the image, sets up environments, and launches the daemon in the background via Docker Compose.

---

## 💻 Usage

Attach to the CLI container to interact with the system:

```bash
docker exec -it agent-farm bash
```

**Common CLI Commands:**
```bash
# Run the relentless 24/7 Super Human loop
farm_agent superhuman

# Start automated discovery and contribution pipeline in hunt mode
farm_agent hunt

# Check open PRs for maintainer comments and push CI auto-fixes
farm_agent patrol

# Target a specific repository directly
farm_agent target <repo_url>

# Solve open issues in a specific repository
farm_agent solve <repo_url>

# Query current PR queue and system statistics
farm_agent status
farm_agent stats
farm_agent system-status

# Clean up forks where all PRs are closed or merged
farm_agent cleanup

# Clear run logs and start with a fresh target pipeline queue
farm_agent reset-db
```

---

## 📜 Contributing & License

We welcome white-hat security researchers and AI engineers to contribute! Please ensure all patches are validated locally using our test suites (`make test`).

Licensed under the [MIT License](LICENSE).
