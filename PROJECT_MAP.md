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

The orchestration pipelines govern execution through rigorous state machines. There are multiple execution paradigms:

### The ContribPipeline (Main Sequence)
1. **Discovery:** Uses `GitHubClient` to find repos or `JsonTargetDiscovery` / `DatabaseTargetDiscovery` for the crash-safe **Circular Target Loop** (updates `scanned_at` timestamp). Fetches `AI_POLICY.md` and `CONTRIBUTING.md` concurrently.
2. **Gate:** The **Anti-Farming Filter** (`security_gate.py`) intercepts targets, dropping non-production code (tests, docs) and preventing low-effort PRs.
3. **Analysis:** The **Bloodhound Red Team** uses `ast-grep` and `Semgrep` combined with OpenRouter White-Hat audit LLMs (falling back to Minimax).
4. **Engine:** `ContributionGenerator` formulates solutions using the **DEV-QA Bounty Loop** (`MAX_DEV_QA_CYCLES = 3`) to refine patches. Raises `GenerationError` on forbidden AI keywords ("as an ai").
5. **Sandbox:** `DockerSandbox` runs patches via the **Polyglot Sandbox**. Enforces a hard killswitch (`sandbox_validation_enabled = True`). Operates across two networks: `internet_access` and `sandbox_isolated`.
6. **PR:** `PRManager` handles forking, patching the branch, committing via GitHub API, and creating the Pull Request.

### The SuperHumanLoop (Terminator Daemon)
Runs a relentless 24/7 autonomous loop maximizing PR throughput up to hard limits (e.g. `max_prs_per_day`), strictly removing simulated delays or breaks. Coordinates interleaved `hunt-circular` and `patrol` commands.

### PR Patrol & Janitor
- **PR Patrol:** Scans open PRs, categorizes maintainer feedback via LLM, generates code/style fixes, and auto-replies. Triggers deterministic ghosting/closure if `MAX_DISCUSSION_REPLIES` is hit.
- **PR Janitor:** Identifies and destroys (closes/deletes branches) for low-value garbage PRs on live GitHub.

## 5. Database/State Schema

Farm-Agent uses `aiosqlite` for state management in `memory.db` with rigorous hardcoded DDL strings (no parameterization for schemas).

| Table | Purpose | Key Guardrails |
|---|---|---|
| `analyzed_repos` | Tracks previously processed repositories. | Prevents redundant operations. |
| `submitted_prs` | Ledger of all created PRs. | Primary source for Alumni Sync and PR Patrol. |
| `pr_outcomes` | Final recorded state (`merged`, `closed`, etc.). | Used to calculate leaderboard and merge rates. |
| `findings_cache` | Caches identified flaws from Bloodhound. | Accelerates repeated targets. |
| `run_log` | High-level tracking of pipeline executions. | Cleared by the `reset-db` CLI command. |
| `blacklisted_repos` | Repositories immune to scanning. | Set defensively by Security Gate or Patrol. |
| `api_usage_log` | Token rate limit expenditure tracking. | Drives rotation logic for `GITHUB_SECONDARY_TOKENS`. |
| `task_schedule` | Persistent tracking of background jobs. | Ensures recovery of delayed operations. |
| `knowledge_base` | Episodic memory and QA lessons. | Pruned via the `gc` CLI (default 90 days). |
