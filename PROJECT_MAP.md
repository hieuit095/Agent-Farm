# Farm-Agent Project Blueprint

This document serves as an architectural guide for the Farm-Agent project, detailing the system overview, directory structure, module dependencies, execution loops, and database schema.

## 1. System Overview & Tech Stack

| Technology | Role |
| :--- | :--- |
| **Python 3.11+** | Core programming language. |
| **Docker (DooD)** | "Polyglot Sandbox" validation; containerized execution of generated patches. |
| **SQLite (aiosqlite)** | Persistent state management (WAL mode) via `memory.db`. |
| **ChromaDB** | Ephemeral, local Retrieval-Augmented Generation (RAG) index for cross-file context. |
| **Hatchling** | Python build backend specified in `pyproject.toml`. |
| **Click & Rich** | Rich command-line interface and terminal output. |
| **Pytest** | Testing framework (with `pytest-asyncio` for async tests). |
| **Minimax (ABAB)** | Primary Large Language Model (LLM) provider for code generation and analysis. |
| **GitHub API (httpx)** | Integration with GitHub for repository discovery, issue tracking, and PR submission. |

## 2. Directory Structure

```text
farm_agent/
├── __init__.py
├── agents/             # Pluggable agent interfaces
│   └── registry.py
├── analysis/           # Code analysis and issue discovery
│   ├── analyzer.py
│   ├── language_rules.py
│   ├── mapper.py       # Repo mapping for architectural context
│   ├── skills.py
│   └── strategies.py   # Multi-strategy analysis logic
├── cli/                # Command-line interface
│   ├── main.py         # Entry point for CLI commands
│   └── tui.py
├── core/               # Core framework utilities
│   ├── config.py       # Configuration management
│   ├── exceptions.py   # Custom exception hierarchy
│   ├── leaderboard.py
│   ├── logger.py
│   ├── models.py       # Pydantic data models
│   ├── rag.py          # RAG indexing via ChromaDB
│   └── sandbox.py      # Polyglot Docker Sandbox implementation
├── generator/          # Code generation and review
│   ├── engine.py       # Main generation engine
│   ├── reviewer.py     # Adversarial review agent
│   └── scorer.py       # Quality scoring for generated code
├── github/             # GitHub API integration
│   ├── client.py       # Async HTTP client for GitHub API
│   ├── discovery.py    # Repository discovery
│   └── guidelines.py
├── issues/             # Issue solving logic
│   └── solver.py       # Issue categorization and solving
├── llm/                # LLM provider abstractions
│   ├── agents.py
│   ├── context.py
│   ├── models.py
│   ├── provider.py     # Base LLM provider interface
│   └── router.py
├── notifications/      # External notifications (Slack, Discord, Telegram)
│   └── notifier.py
├── orchestrator/       # High-level execution coordination
│   ├── human.py        # Super Human Mode daemon
│   ├── memory.py       # SQLite database interactions
│   └── pipeline.py     # Main contribution pipeline orchestrator
├── plugins/            # Extensible plugin system
│   └── base.py
├── pr/                 # Pull Request management
│   ├── janitor.py.DISABLED
│   ├── manager.py      # Forking, committing, and PR creation
│   └── patrol.py       # Monitoring and auto-responding to open PRs
├── templates/          # Contribution templates
│   ├── builtin/
│   └── registry.py
└── tools/              # Agent tools and protocols
    └── protocol.py
tests/                  # Test suite
├── unit/               # Unit tests for various modules
└── test_async_io_pipeline.py
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent/cli/main.py)] --> Orchestrator[Orchestrator (Pipeline/SuperHuman)]
    Orchestrator --> GitHub[GitHub Client]
    Orchestrator --> Memory[SQLite Memory]
    Orchestrator --> LLM[LLM Provider]

    Orchestrator --> Analyzer[Analysis Engine]
    Analyzer --> GitHub
    Analyzer --> RAG[ChromaDB (RAG)]

    Orchestrator --> Generator[Code Generation Engine]
    Generator --> LLM
    Generator --> RAG
    Generator --> Sandbox[Docker Sandbox]

    Orchestrator --> PRManager[PR Manager]
    PRManager --> GitHub

    Orchestrator --> Patrol[PR Patrol & Janitor]
    Patrol --> GitHub
    Patrol --> LLM
```

## 4. Core Execution Loops / Entry Points

1. **CLI Invocation:** The user executes a command (e.g., `farm_agent hunt`, `farm_agent solve`) via the Click CLI (`farm_agent/cli/main.py`).
2. **Orchestration Setup:** The CLI parses arguments, initializes the configuration (`farm_agent/core/config.py`), and instantiates the `ContribPipeline` or `SuperHumanLoop`.
3. **Discovery/Targeting:** The orchestrator fetches repository details via the `GitHubClient`. In `hunt` mode, it uses search criteria to find suitable repositories.
4. **Analysis & Issue Finding:** The `analyzer` module scans the repository. It might use issue fetching (`solver.py`) or static analysis ("Bloodhound"). Relevant files are indexed into ChromaDB (`rag.py`) for semantic search.
5. **Code Generation:** The `generator/engine.py` builds context-aware prompts (incorporating QA lessons and repo preferences from `Memory`) and queries the LLM. It includes a multi-cycle retry loop with an adversarial reviewer.
6. **Sandbox Validation:** The generated patch is executed within an isolated Docker container (`core/sandbox.py`). If tests fail, the error logs are fed back to the LLM for self-correction.
7. **PR Submission:** Upon successful validation, the `PRManager` (`pr/manager.py`) forks the repository, creates a branch, commits the changes, and opens a Pull Request via the GitHub API.
8. **State Update:** The outcome is logged to the SQLite `Memory` database (`orchestrator/memory.py`).

## 5. Database/State Schema

Farm-Agent utilizes an asynchronous SQLite database (`memory.db`) with Write-Ahead Logging (WAL) enabled.

### Key Tables

| Table Name | Description |
| :--- | :--- |
| `analyzed_repos` | Tracks repositories that have been analyzed to prevent redundant processing. |
| `submitted_prs` | Core table recording all created Pull Requests and their current status (open/merged/closed). |
| `findings_cache` | Caches identified issues from static analysis to save on LLM token costs across runs. |
| `run_log` | High-level audit trail of execution runs, including start/end times and total PRs created. |
| `pr_outcomes` | Logs the specific outcome of each PR (e.g., merged, rejected) for learning and feedback. |
| `repo_preferences` | Stores learned behavioral traits of repositories (e.g., preferred contribution types). |
| `blacklisted_repos` | Repositories explicitly ignored (e.g., due to AI policies or maintainer requests). |
| `api_usage_log` | Tracks LLM and GitHub API requests to support rate-limiting mechanisms. |
| `task_schedule` | Key-value store for scheduling background tasks (like garbage collection). |
| `knowledge_base` | Stores QA lessons and audit history, used to inform future code generation. |

### Key Data Models (from `core/models.py`)

- `TargetRepoEntry`: Represents a target repository, used in the circular target loop.
- `Finding`: An identified issue, detailing severity, file path, and description.
- `Contribution`: The generated patch containing the changes, commit message, and branch name.
- `RepoContext`: Comprehensive context for a repository, including file tree and guidelines, used during LLM prompting.
