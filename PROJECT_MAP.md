# PROJECT_MAP.md

## 1. System Overview & Tech Stack

Farm-Agent is built on a modern, asynchronous Python stack leveraging advanced LLM orchestration and containerized execution.

| Technology/Library | Role in System |
|---|---|
| **Python 3.11+** | Core runtime environment. |
| **Docker Engine (7.1+)** | Powers the Polyglot Sandbox for isolated, safe code validation. |
| **Pydantic** | Strict data validation and settings management (`farm_agent/core/models.py`). |
| **ChromaDB** | Ephemeral, RAM-only Local Retrieval-Augmented Generation (RAG) engine. |
| **Minimax (ABAB models)** | Primary Large Language Model (LLM) provider for code generation and analysis. |
| **OpenRouter** | Secondary LLM provider used by the Bloodhound Red Team for White-Hat Auditing. |
| **aiosqlite** | Asynchronous database interactions for persistent memory (`memory.db`). |
| **httpx / aiohttp** | Asynchronous HTTP requests, essential for GitHub API communication. |
| **Click / Rich** | Powers the advanced Command-Line Interface (`farm_agent/cli/main.py`). |
| **ast-grep / Semgrep** | Static Analysis Security Testing (SAST) tools utilized by the Bloodhound Red Team. |

## 2. Directory Structure

```ascii
Farm-Agent/
├── farm_agent/             # Core application package
│   ├── agents/             # Task-specific sub-agents (e.g., CodeQA, Docs)
│   ├── analysis/           # Codebase scanning, parsing, and SAST integration (Bloodhound)
│   ├── cli/                # Command-line interface definitions
│   │   └── main.py         # Main entry point for CLI commands
│   ├── core/               # Foundational utilities (config, logger, sandbox, models)
│   │   ├── models.py       # Pydantic schemas (TargetRepoEntry, Contribution, etc.)
│   │   └── sandbox.py      # Docker-based code execution environment
│   ├── generator/          # Code generation engines and prompt construction
│   ├── github/             # GitHub API client and abstractions
│   ├── issues/             # Issue processing and solving logic
│   ├── llm/                # LLM provider integrations (Minimax, OpenRouter, etc.)
│   ├── notifications/      # Webhook alerting (Slack, Discord, Telegram)
│   ├── orchestrator/       # High-level pipeline and state management
│   │   ├── memory.py       # SQLite database interactions and state persistence
│   │   └── pipeline.py     # Main execution loop coordinator
│   ├── plugins/            # Extensible module architecture
│   ├── pr/                 # Pull request creation and lifecycle management
│   │   ├── manager.py      # Handles forks, branches, and PR creation
│   │   └── patrol.py       # Monitors open PRs, auto-heals CI, replies to feedback
│   ├── templates/          # Standardized issue/PR templates
│   └── tools/              # Helper utilities for agents
├── scripts/                # Utility scripts for maintenance and operations
├── tests/                  # Pytest unit and integration test suites
├── config.example.yaml     # Template configuration file
├── docker-compose.yml      # Orchestration for the 'Super Human Mode' daemon
├── pyproject.toml          # Project dependencies and build configuration (Hatchling)
└── requirements.txt        # Locked dependencies
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[farm_agent/cli/main.py] --> Config[farm_agent/core/config.py]
    CLI --> Orchestrator[farm_agent/orchestrator/pipeline.py]

    Orchestrator --> Memory[farm_agent/orchestrator/memory.py]
    Orchestrator --> GitHub[farm_agent/github/client.py]
    Orchestrator --> Analysis[farm_agent/analysis/]
    Orchestrator --> Generator[farm_agent/generator/]
    Orchestrator --> PRManager[farm_agent/pr/manager.py]

    Analysis --> Bloodhound[Bloodhound Red Team (Semgrep/ast-grep)]
    Analysis --> LLMRouter[farm_agent/llm/router.py]

    Generator --> LLMRouter
    Generator --> Sandbox[farm_agent/core/sandbox.py (Docker)]

    PRManager --> GitHub
    PRManager --> PRPatrol[farm_agent/pr/patrol.py]

    LLMRouter --> Providers[Minimax / OpenRouter / Gemini]
```

## 4. Core Execution Loops / Entry Points

The primary execution flow of Farm-Agent follows the **Sequential Pipeline Loop**:

1.  **Discovery:** The system initializes via `farm_agent/cli/main.py` and queries the GitHub API to find repositories matching the criteria defined in `config.yaml` or a target list.
2.  **Gate:** The orchestrator retrieves repository metadata and policies (concurrently fetching `AI_POLICY.md` and `CONTRIBUTING.md`). It evaluates friendliness metrics and drops targets blocking AI contributions.
3.  **Analysis (Bloodhound Red Team):** `farm_agent/analysis/` scans the repository using `ast-grep` and Semgrep. Potential vulnerabilities undergo a White-Hat Audit via OpenRouter to confirm legitimacy.
4.  **Engine:** Validated findings are passed to `farm_agent/generator/`. The LLM formulates a solution and generates patches (FileChange objects). An Anti-Farming Filter ensures changes are non-trivial.
5.  **Sandbox:** The generated code is tested locally. `farm_agent/core/sandbox.py` clones the repo, applies the patches, and runs validations within an isolated Docker container operating on restricted networks.
6.  **PR:** If the sandbox validations pass, `farm_agent/pr/manager.py` forks the repository, creates a new branch, commits the changes, and submits the Pull Request.
7.  **Patrol:** A background process, `farm_agent/pr/patrol.py`, continuously monitors the submitted PR. It classifies maintainer comments, pushes code fixes for CI failures, and manages the PR lifecycle until merged or closed.

**Additional Loops:**
-   **Terminator Execution Loop ("Super Human Mode"):** A relentless, 24/7 daemon process designed to execute the pipeline continuously, maximizing throughput up to daily API quotas.

## 5. Database/State Schema

Farm-Agent uses an asynchronous SQLite database (`memory.db`) managed by `farm_agent/orchestrator/memory.py` to persist state across runs.

Key tables and their schemas:

-   **`analyzed_repos`**: Tracks repositories that have been fully evaluated.
-   **`submitted_prs`**: Logs every PR created by the agent. Includes repo URL, PR number, title, status (`open`, `merged`, `closed`), and type.
-   **`findings_cache`**: Caches identified issues/vulnerabilities to avoid redundant processing.
-   **`run_log`**: Detailed logs of agent pipeline executions.
-   **`pr_outcomes`**: Statistical tracking of PR success/failure rates.
-   **`repo_preferences`**: Cached style guides and developer preferences for specific repositories (used by the Diplomat Protocol).
-   **`blacklisted_repos`**: Repositories flagged to be permanently ignored (e.g., due to AI bans).
-   **`api_usage_log`**: Sliding-window tracking of LLM API requests (e.g., Minimax quotas).
-   **`task_schedule`**: Schedules asynchronous background tasks (like quota cleanups).
-   **`target_repos`**: Schema mapping to `TargetRepoEntry` models. Tracks repositories targeted for action, including their `status`, `bounty_amount`, `ai_policy`, and `priority_score`.