# 🗺️ Agent-Farm Project Architecture Blueprint (v4.0.0)

Welcome to the internal blueprint for Agent-Farm. This document provides a deep dive into the system architecture, directory structures, and core data models that drive our autonomous AI agent ecosystem.

---

## 1. System Overview & Tech Stack

Agent-Farm leverages a robust, asynchronous technology stack to maximize throughput and stability.

| Component | Technology | Role in Project |
| :--- | :--- | :--- |
| **Core Runtime** | Python 3.11+ | Primary execution environment for all pipeline logic. |
| **Concurrency** | `asyncio` | Manages non-blocking I/O operations (GitHub API, Docker, LLM calls). |
| **Containerization** | Docker (>= 7.1) | Provides locked-down sandboxes for dynamic PoC bug validation and regression testing. |
| **Memory / State** | SQLite (`aiosqlite`) | `memory.db` stores PR queue states, target queues, logs, and learned preferences. |
| **Vector Database** | ChromaDB | Backs the **Omniscient Context Engine** for semantic codebase documentation indexing. |
| **CLI Framework** | Click & Rich | Provides a comprehensive CLI interface and rich terminal outputs. |
| **HTTP Client** | `httpx` | Manages interactions with REST APIs (GitHub, OpenRouter, Provider models). |
| **Code Analysis** | ast-grep / Semgrep | Drives the **Bloodhound Red Team** for static vulnerability discovery. |
| **Validation** | Pydantic (v2) | Core data structuring, configuration loading, and model validation. |
| **LLM Gateway** | OpenRouter | Dynamically routes queries across multiple top-tier models (DeepSeek, Qwen, Gemini). |

---

## 2. Directory Structure

This structure represents the core modules driving the Farm-Agent pipeline, excluding build tools and trivial configurations.

```text
.
├── Dockerfile                  # Multi-stage Docker definitions for runtime environment
├── docker-compose.yml          # Service definition mounting local volumes and Docker socket
├── Makefile                    # Target shortcuts (e.g., `make install`, `make test`, `make lint`)
├── pyproject.toml              # Build metadata and dependency definitions (Hatchling)
├── start.sh / start.bat        # 1-Click wrapper scripts to boot the system
└── farm_agent/                 # Main Python package root
    ├── cli/
    │   └── main.py             # Main entry point for Click CLI commands (`farm_agent run`, etc.)
    ├── core/                   # Shared configurations and system utilities
    │   ├── config.py           # Loads runtime configuration
    │   ├── exceptions.py       # Custom Exception types
    │   ├── models.py           # Core Pydantic data models
    │   ├── rag.py              # Logic for RAG and semantic header-based markdown chunking
    │   └── sandbox.py          # DockerSandbox engine to run verification and tests in isolation
    ├── analysis/               # Code scanning and graph builders
    │   ├── analyzer.py         # CodeAnalyzer and BloodhoundAnalyzer (ast-grep integration)
    │   └── mapper.py           # RepoMapper for AST-based dependency graphing (calls/imports)
    ├── generator/              # LLM logic for bug fixes and patches
    │   ├── engine.py           # ContributionGenerator responsible for drafting fixes
    │   ├── poc.py              # PoCGenerator builds localized scripts to dynamically trigger bugs
    │   ├── reviewer.py         # Blast Radius testing and regression auditing logic
    │   └── scorer.py           # Layer 1 Qwen QA grading system
    ├── github/                 # GitHub interaction modules
    │   ├── client.py           # Async HTTP / GraphQL wrapper for API calls
    │   ├── discovery.py        # Logic for finding new target repos
    │   └── guidelines.py       # Internal subsystem documentation discovery logic
    ├── issues/
    │   └── solver.py           # Dedicated module for addressing GitHub issues via deep planning
    ├── llm/                    # Model routing and context preparation
    │   ├── agents.py           # LLM agent definitions and internal routing
    │   ├── context.py          # Formats context strings for LLM injection
    │   ├── provider.py         # Integration handlers with external APIs (OpenRouter, Minimax)
    │   └── router.py           # Tasks mapping logic
    ├── notifications/
    │   └── notifier.py         # Push alerts to Telegram, Discord, and Slack
    ├── orchestrator/           # High-level execution controllers
    │   ├── memory.py           # SQLite db context and interaction logic
    │   └── pipeline.py         # Main execution pipeline (discover -> analyze -> generate -> PR)
    ├── pr/                     # Branch and Commit management
    │   ├── manager.py          # Manages Git branches, creates patches, and pushes to GitHub
    │   └── patrol.py           # PR Patrol handles CI auto-fixes and answering maintainer queries
    └── tools/
        └── protocol.py         # Definitions for CLI tools
```

---

## 3. Core Module Dependency Graph

The interaction logic follows a distinct pattern from discovery to final verification and submission.

```mermaid
graph TD
    CLI[CLI (main.py)] --> P[Orchestrator Pipeline (pipeline.py)]
    P --> D[GitHub Discovery (discovery.py)]
    P --> GH[GitHub Client (client.py)]

    P --> CA[Code Analyzer (analyzer.py)]
    CA --> BH[Bloodhound Scanner]
    CA --> RM[Repo Mapper]

    P --> CG[Contribution Generator (engine.py)]
    CG --> PoC[PoC Generator (poc.py)]
    CG --> SB[Docker Sandbox (sandbox.py)]

    PoC --> SB
    SB --> Rev[Reviewer (reviewer.py)]

    P --> PR[PR Manager (manager.py)]
    PR --> GH
```

---

## 4. Core Execution Loops / Entry Points

The fundamental entry point to the system is through `farm_agent/cli/main.py`. Commands define which loop gets invoked.

### Pipeline Flow (`farm_agent run` / `farm_agent hunt`)
1. **Invocation:** The CLI triggers `FarmAgentPipeline` located in `farm_agent/orchestrator/pipeline.py`.
2. **Discovery & Intelligence:** The pipeline utilizes `GitHubClient` to search for targets and initializes the **Omniscient Context Engine** (`farm_agent/core/rag.py` and `farm_agent/analysis/mapper.py`) to build an AST graph and chunk internal documentation.
3. **Analysis:** The `CodeAnalyzer` is invoked to identify bugs and apply the **Anti-Farming Filter**. Layer 1 AI (Qwen) appraises the raw findings for actual impact.
4. **Validation:** For discovered bugs, `PoCGenerator` crafts a test script. The script runs inside the isolated `DockerSandbox`.
5. **Generation & Review:** DeepSeek models via `ContributionGenerator` draft a patch. `ReviewerAgent` performs **Blast Radius & Regression Auditing**, running the patched code against the local test suite in the Docker Sandbox.
6. **Submission:** If all tests pass, `PRManager` initiates a fork, commits the changes, and raises a PR via `GitHubClient`.

---

## 5. Database/State Schema (`memory.db`)

Agent-Farm leverages an SQLite database configured for WAL (Write-Ahead Logging) mode, residing at `data/memory.db`. The core schema includes:

* **`analyzed_repos`**: Tracks repositories that have already gone through analysis (`full_name`, `language`, `stars`, `findings`, etc.).
* **`submitted_prs`**: Tracks bot-created PRs, issues, and loop counters. Unique constraint on `(repo, pr_number)`.
* **`findings_cache`**: Temporary cache of detected code findings (`repo`, `type`, `severity`, `file_path`, `status`).
* **`run_log`**: Log of overall runs, metrics, and duration times.
* **`pr_outcomes`**: Stores merged/closed PR states and maintainer review feedback.
* **`repo_preferences`**: Learned project contribution preferences updated dynamically from historical outcomes.
* **`blacklisted_repos`**: Records repositories blocked due to hostile maintainer checks or repeated failures.
* **`api_usage_log`**: Tracks LLM API usage. Features composite indices to optimize provider-level quota checking.
* **`task_schedule`**: Persistent schedule queue for tasks (used for recurring events).
* **`knowledge_base`**: Stores lessons, past critiques, and subsystem architecture contexts for the RAG engine.
* **`target_repos`**: Deterministic circular target queue utilized by Terminator mode (relentless looping).
* **`repo_style_guides`**: Caches contributor templates, code formatting guidelines, and structures.

*Note: The database extensively utilizes composite indexing (like `idx_api_usage`) to remain highly performant over time.*