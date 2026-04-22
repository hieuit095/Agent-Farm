# Farm-Agent Architecture & Project Map

This document serves as the canonical architectural blueprint for Farm-Agent. It details the active technologies, repository structure, and core workflows of the system.

## 1. System Overview & Tech Stack

| Component | Technology | Role in System |
|---|---|---|
| **Language** | Python (3.11+) | Core implementation language. |
| **CLI Framework** | Click / Rich | Provides the command-line interface, argument parsing, and rich terminal formatting. |
| **Orchestration** | asyncio | Drives concurrent repository processing and task execution. |
| **API Client** | httpx | Handles asynchronous HTTP requests to GitHub and LLM providers. |
| **Configuration** | Pydantic / PyYAML | Validates configurations loaded from `config.yaml` or `.env`. |
| **LLM Providers** | Minimax / OpenRouter | Powers code generation, PR analysis, and White-Hat Bloodhound audits. |
| **Local RAG Engine**| ChromaDB | Provides an ephemeral, RAM-only retrieval-augmented generation for repository context. |
| **Validation** | Docker SDK | Drives the isolated Polyglot Sandbox execution to validate generated code. |
| **Memory / State** | SQLite (`aiosqlite`) | Maintains persistent state for run logs, analyzed repos, and PR outcomes (`memory.db`). |
| **Build Backend** | Hatchling | Package build and dependency management (`pyproject.toml`). |
| **Linting & Tests** | Ruff / Pytest | Enforces code quality, formatting limits, and test execution. |

## 2. Directory Structure

```text
Farm-Agent/
├── farm_agent/               # Core application package
│   ├── cli/                  # Command-Line Interface module
│   │   └── main.py           # CLI entry points (run, target, superhuman, patrol)
│   ├── core/                 # Core system models and utilities
│   │   ├── config.py         # Pydantic configuration models
│   │   ├── sandbox.py        # Polyglot Sandbox Docker orchestration
│   │   └── middleware.py     # Utilities for requests
│   ├── github/               # GitHub API interactions
│   │   └── client.py         # Asynchronous GitHub API client with token rotation
│   ├── orchestrator/         # Main execution pipelines
│   │   ├── pipeline.py       # ContribPipeline (Discovery -> Gate -> Analysis -> Engine)
│   │   ├── human.py          # SuperHumanLoop (Terminator loop)
│   │   └── memory.py         # SQLite memory database interface
│   ├── analysis/             # Bloodhound Red Team / Vulnerability scanning
│   ├── generator/            # LLM prompt construction and code generation
│   ├── issues/               # Issue classification and solving mechanics
│   │   └── solver.py         # Analyzes and assigns complexity to issues
│   ├── llm/                  # LLM provider routing and clients
│   ├── pr/                   # Pull Request mechanics
│   │   ├── manager.py        # Coordinates forking, branch creation, and PR submission
│   │   └── patrol.py         # PR Patrol for addressing maintainer feedback
│   └── plugins/              # Extensibility hooks
├── tests/                    # Pytest suites
├── scripts/                  # Helper scripts
├── data/                     # Local data (e.g., SQLite memory.db)
├── pyproject.toml            # Project configuration and dependencies
├── config.example.yaml       # Example YAML configuration
├── docker-compose.yml        # Docker composition for 24/7 daemon
└── README.md                 # Project Overview and Getting Started guide
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (main.py)] --> Pipeline[Orchestrator Pipeline]
    CLI --> SuperHuman[SuperHuman Loop]
    CLI --> Patrol[PR Patrol]

    SuperHuman --> Pipeline
    SuperHuman --> Patrol

    Pipeline --> GitHub[GitHub Client]
    Pipeline --> Gate[Anti-Farming Filter]
    Pipeline --> Analysis[Bloodhound Red Team Analysis]
    Pipeline --> Engine[LLM Generator Engine]
    Pipeline --> Sandbox[Polyglot Sandbox]
    Pipeline --> PRManager[PR Manager]

    PRManager --> GitHub
    Patrol --> GitHub
    Patrol --> Engine

    Gate -.-> Memory[(SQLite Memory DB)]
    Analysis -.-> Memory
    PRManager -.-> Memory
```

## 4. Core Execution Loops / Entry Points

The pipeline orchestrates contributions through a rigorous, sequential state machine:

1. **Discovery:** Scrapes GitHub to discover target repositories or processes explicit targets (e.g., via the `target` command or the Circular Target Loop).
2. **Gate:** The Anti-Farming Filter immediately halts execution on the repository if it appears to be a trivial documentation or non-production target.
3. **Analysis:** The Bloodhound Red Team utilizes structural searching (`ast-grep`, `Semgrep`) and White-Hat LLM logic to identify concrete vulnerabilities or flaws.
4. **Engine:** The Generator constructs prompts and communicates with the LLMs to produce patching code or feature enhancements based on analysis.
5. **Sandbox:** The generated code is compiled and executed within a Polyglot Sandbox (Docker). Changes that break the build or tests are rejected.
6. **PR:** The PR Manager forks the repository, pushes the validated patch to a new branch, and creates the Pull Request on GitHub.

## 5. Database/State Schema

Farm-Agent uses `aiosqlite` to manage persistence in `memory.db`. The primary tables include:

- `analyzed_repos`: Tracks repositories that have been processed to prevent duplicate work.
- `submitted_prs`: Logs all Pull Requests created by the agent, enabling tracking and management.
- `pr_outcomes`: Records the final state (merged, closed, etc.) of PRs.
- `findings_cache`: Caches identified vulnerabilities and issues to optimize subsequent runs.
- `run_log`: Historical log of execution runs.
- `blacklisted_repos`: Repositories explicitly ignored by the agent.
- `api_usage_log`: Logs API requests to manage and throttle quotas.
- `knowledge_base`: Stores episodic QA lessons and historical context for the agent.
