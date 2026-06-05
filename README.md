# 🛠️ Farm-Agent

**Autonomous Bounty-Hunting Security Researcher & Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 🚀 Overview

Farm-Agent is an autonomous AI agent ecosystem designed to crawl GitHub, pinpoint real security vulnerabilities or open issues, generate high-quality patches, validate fixes dynamically in isolated sandboxes, and submit pull requests or private disclosures. Operating with human-like precision, it implements advanced self-correcting DEV-QA loops and maintainer vibe analysis to ensure every contribution is high-value, precise, and completely regression-free.

---

## 🔥 Key Features

### 🧠 Omniscient Context Engine
Upgraded codebase intelligence using Retrieval-Augmented Generation (RAG) powered by ChromaDB. It recursively discovers internal documentation (`.md`, `.txt`, `.rst`), semantically chunks docs by headers, and indexes them to seed local knowledge. Concurrently, it builds AST-based call graphs (for Python, Rust, Go, TypeScript) to inject precise module dependency links ("imports", "calls", "dependents") directly into the prompt context.

### 🛡️ Zero-Garbage PR Gatekeepers
Zero tolerance for typo-fixes, formatting tweaks, or documentation-only PRs (README/doc contributions are strictly banned). Implements a two-layer filter system:
* **Gate 1: EXPERT APPRAISAL (Qwen-3.7-Max):** Renders strict verdicts on findings to filter out false positives and theoretical edge cases.
* **Gate 2: REAL-WORLD VALUE CHECK:** Vetoes patches targeting dead or deprecated code blocks to avoid sending low-effort spam to maintainers.

### 🧪 Dynamic Bug Verification (PoC Execution)
Before writing a fix, the agent generates a self-contained Proof-of-Concept (PoC) script using `deepseek-v4-pro` to dynamically trigger the vulnerability inside a locked-down container sandbox. If the PoC fails to trigger the bug, the finding is immediately classified as a False Positive and dropped.

### 🔍 Blast Radius & Regression Auditing
Validates generated patches in isolated Docker sandboxes through a double-pass check:
* **Pass 1 (Efficacy):** Applies the patch and re-runs the PoC. The vulnerability must be completely resolved.
* **Pass 2 (Regression):** Executes the project's native test suite to ensure the patch does not break any existing functionality. Also verifies that changes do not break downstream dependent modules.

---

## 🏗️ System Architecture (High-Level)

Farm-Agent acts as an end-to-end pipeline ("DeerFlow" pattern) running in a relentless 24/7 autonomous loop:
1.  **Discovery:** Crawls GitHub or takes target URLs to identify target projects.
2.  **Gate:** Scans for private security disclosure phrases to avoid public leaks and stops processing if found.
3.  **Analysis:** Performs static code analysis using ASTs and regex (Bloodhound/Semgrep) to locate vulnerabilities and map module dependencies.
4.  **Engine:** Uses an AI appraisal system (Qwen) to validate findings. If valid, generates an executable PoC using DeepSeek.
5.  **Sandbox:** Executes the PoC and test suites in isolated Docker environments to ensure efficacy and lack of regressions.
6.  **PR/Submission:** Submits validated patches as GitHub Pull Requests, learning from PR comments and CI results to self-correct in subsequent loops.

---

## 🛠️ Getting Started

### Prerequisites
*   **Docker Desktop** installed and running (for sandbox isolation).
*   **Git** installed on the host machine.
*   **Python >= 3.11**.
*   A GitHub Personal Access Token (PAT) with `repo` scope.
*   An OpenRouter API Key configured with credits.

### Environment Variables
These environment variables can be provided via a `.env` file or exported to the shell session. These exact variables are read by `farm_agent/core/config.py`.
- `GITHUB_TOKEN`: Your GitHub Personal Access Token used for accessing repositories and committing code.
- `OPENROUTER_API_KEY`: API key for OpenRouter to use supported DeepSeek and Qwen models.
- `GITHUB_SECONDARY_TOKENS` (Optional): Comma-separated list of extra GitHub tokens for API rate-limit rotation.
- `EXCLUDED_LANGUAGES` (Optional): Comma-separated list of languages to exclude from analysis.

### Installation Steps
Farm-Agent can be deployed via a 1-click Docker quick-start script.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hieuit095/Farm-Agent.git
    cd Farm-Agent
    ```

2.  **Configure Settings:**
    Create a `.env` file using the example template:
    ```bash
    cp .env.example .env
    ```
    Open the newly created `.env` file and configure your tokens as listed in the Environment Variables section above.

3.  **Run the Quick-Start Script:**
    *   **Windows:** Double-click `start.bat` or run:
        ```cmd
        start.bat
        ```
    *   **Unix (Linux/macOS):**
        ```bash
        chmod +x start.sh
        ./start.sh
        ```
    *Note: The script will automatically pull the latest codebase, initialize your `.env` configuration file from `.env.example` if missing, build the Docker image, and launch the daemon in the background.*

---

## ⚙️ Usage

Once Farm-Agent is running in Docker, you can interact with it using its CLI via `docker exec`. Here are a few examples:

```bash
# Attach to the Agent CLI
docker exec -it agent-farm farm_agent superhuman

# Start the full automated discovery, analysis, and contribution pipeline
docker exec -it agent-farm farm_agent run

# Target a specific repository directly
docker exec -it agent-farm farm_agent target <repo_url>

# Solve open issues in a specific repository
docker exec -it agent-farm farm_agent solve <repo_url>

# Run in Hunt Mode: agressively discover repos and solve issues/bugs
docker exec -it agent-farm farm_agent hunt --rounds 5 --mode both

# Run the Relentless 24/7 Super Human loop (patrols PRs and hunts targets)
docker exec -it agent-farm farm_agent superhuman

# Check open PRs for maintainer comments, answer queries, and push CI auto-fixes
docker exec -it agent-farm farm_agent patrol

# Scan and close low-quality/garbage PRs submitted on GitHub
docker exec -it agent-farm farm_agent janitor

# Clean up forks where all PRs are closed or merged
docker exec -it agent-farm farm_agent cleanup

# Query current PR queue, runtime statistics, and LLM allocations
docker exec -it agent-farm farm_agent status
docker exec -it agent-farm farm_agent stats
docker exec -it agent-farm farm_agent models
docker exec -it agent-farm farm_agent leaderboard

# Clear run logs and start with a fresh target pipeline queue
docker exec -it agent-farm farm_agent reset-db

# Run garbage collection to purge stale knowledge base entries
docker exec -it agent-farm farm_agent gc --days 90

# Test the configured notification channels
docker exec -it agent-farm farm_agent notify-test

# Show Farm-Agent system status
docker exec -it agent-farm farm_agent system-status
```

---

## 📜 Contributing & License

We welcome white-hat security researchers, AI engineers, and open-source enthusiasts to contribute to Farm-Agent!

### How to Contribute
1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes following conventional commit formats (`git commit -m 'feat: add amazing feature'`).
4.  Ensure all patches are validated locally using our test suites (`make test`).
5.  Push to the branch (`git push origin feature/amazing-feature`).
6.  Open a Pull Request.

### License
This project is licensed under the [MIT License](LICENSE).
