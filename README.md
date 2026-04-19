# Farm-Agent 🚜🤖

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build System: Hatchling](https://img.shields.io/badge/build-hatchling-orange.svg)](https://hatch.pypa.io/)
[![Docker](https://img.shields.io/badge/docker-7.1%2B-blue.svg)](https://www.docker.com/)

Farm-Agent is a highly autonomous system engineered to discover open-source repositories on GitHub, analyze their code, and automatically submit high-quality Pull Requests. Operating 24/7, it runs a relentless Terminator execution loop to maximize PR throughput, rigorously validating changes in an isolated sandbox before submission.

## Core Features 🌟

*   **Super Human Mode:** A 24/7 autonomous daemon utilizing a relentless Terminator execution loop to maximize PR throughput up to daily API limits. It seamlessly rotates targets and manages quotas without human intervention.
*   **Bloodhound Red Team & Sentinel Radar:** Leverages `ast-grep` and Semgrep to discover vulnerabilities, code quality issues, and performance bottlenecks. White-Hat audits are powered by OpenRouter.
*   **Polyglot Sandbox Verification:** Employs a secure Docker-based execution environment to run test suites and validate generated code across 12 different programming languages before committing. The sandbox enforces strict timeouts and drops capabilities to prevent malicious execution.
*   **PR Patrol & Maintainer Interaction:** Autonomously monitors open PRs, classifies maintainer feedback using an LLM, generates code fixes, answers questions, and automatically handles CLA signing.
*   **Ruthless PR Janitor:** Evaluates active PRs using the Minimax LLM and autonomously closes exploratory, trivial, or low-impact PRs to maintain high contribution quality.
*   **Anti-Farming & Security Gates:** Employs comprehensive filters to strictly block trivial documentation updates, low-impact PRs, and modifications to protected files (`CODEOWNERS`, `package.json`, etc.). It also detects private security disclosure policies and aborts if necessary.
*   **Multi-Model LLM Routing:** Intelligently routes tasks to the optimal LLM provider (Minimax ABAB models, OpenRouter, Gemini, OpenAI, Anthropic, or local Ollama) based on the task type (coding, analysis, etc.).
*   **Local RAG Engine:** Utilizes an ephemeral ChromaDB (RAM-only) Local Retrieval-Augmented Generation engine to leverage past findings and improve contribution accuracy.

## System Architecture (High-Level) 🏗️

Farm-Agent orchestrates a continuous `ContribPipeline`.
1.  **Discovery:** Searches GitHub for repositories matching specific language, star count, and activity criteria. It checks the "Maintainer Vibe" and avoids hostile environments.
2.  **Analysis (Bloodhound):** Clones the repository, enforces security gates (checking for private disclosure policies), and scans the code using Semgrep and static analyzers to generate a list of findings.
3.  **Generation & Review:** An LLM generator crafts code modifications for high-impact findings. A `QualityScorer` reviews the changes, strictly penalizing debug code (`print`, `console.log`) and ensuring formatting compliance.
4.  **Sandbox Validation:** The generated code is injected into the Docker-isolated Polyglot Sandbox, where the project's tests are executed to verify the fix.
5.  **Submission:** The `PRManager` forks the repository, branches the code, commits the validated changes, and opens a Pull Request on GitHub.

## Getting Started 🚀

### Prerequisites

*   **Python:** >= 3.11
*   **Docker:** >= 7.1 (Required for the Polyglot Sandbox)
*   **GitHub Token:** A classic Personal Access Token with `repo` and `workflow` scopes.
*   **LLM API Key:** An API key for your chosen provider (e.g., Minimax, OpenRouter).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hieuit095/Farm-Agent.git
    cd Farm-Agent
    ```

2.  **Install the package with development dependencies:**
    ```bash
    pip install -e .[dev]
    ```

3.  **Configure Environment:**
    Copy the example configuration file:
    ```bash
    cp config.example.yaml config.yaml
    ```
    Create a `.env` file in the root directory:
    ```bash
    GITHUB_TOKEN=your_github_token_here
    MINIMAX_API_KEY=your_minimax_api_key_here
    MINIMAX_GROUP_ID=your_minimax_group_id_here
    OPENROUTER_API_KEY=your_openrouter_api_key_here  # For Bloodhound White-Hat auditing
    ```

### Running with Docker Compose

To run the full Super Human Mode 24/7 daemon using Docker Compose:

```bash
docker-compose up -d
```
The `agent-farm` service connects to an `internet_access` bridge network and a `sandbox_isolated` internal network.

## Usage 🛠️

Farm-Agent provides a rich command-line interface (`farm_agent`):

*   **Target a specific repository:**
    ```bash
    farm_agent target https://github.com/owner/repo
    ```
*   **Analyze a repository without submitting PRs:**
    ```bash
    farm_agent analyze https://github.com/owner/repo
    ```
*   **Solve open issues on a repository:**
    ```bash
    farm_agent solve https://github.com/owner/repo --max-issues 3
    ```
*   **Run PR Patrol (auto-respond to feedback):**
    ```bash
    farm_agent patrol
    ```
*   **Start the Super Human Mode 24/7 Daemon:**
    ```bash
    farm_agent superhuman
    ```
*   **Check system status and PR outcomes:**
    ```bash
    farm_agent system-status
    ```
*   **View global statistics:**
    ```bash
    farm_agent stats
    ```

## Contributing & License 🤝

Contributions are welcome! Please ensure you run `make test` or `make test-quick` to verify changes, and use `ruff check . --fix` for linting.

This project is licensed under the MIT License - see the `LICENSE` file for details.
