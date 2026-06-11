# PROJECT_MAP.md (Architecture Blueprint)

## 1. System Overview & Tech Stack

Farm-Agent is built on a modern Python stack (v3.11+), utilizing asynchronous operations and custom orchestration patterns for scalable, intelligent open-source contributions.

| Technology / Library | Role in System |
| --- | --- |
| **Python 3.11+** | Core programming language. |
| **Hatchling** | Build backend and project management (`pyproject.toml`). |
| **Pydantic** & **pydantic-settings** | Strict type validation, configuration parsing (`config.py`), and schema definitions. |
| **aiosqlite** | Asynchronous persistent storage for the orchestrator (`memory.db`), managing PR states and agent memory. |
| **ChromaDB** | Local vector database used by the Omniscient Context Engine (`rag.py`) for semantic codebase search. |
| **Docker** | Provides the `DockerSandbox` for isolated dynamic bug verification and PoC execution. |
| **OpenRouter / Minimax** | Core LLM providers used for code generation, Layer 1/2 Auditing, and the Bloodhound Red Team pipeline. |
| **GitPython** | Programmatic git operations for branching, committing, and analyzing local repositories. |
| **httpx** | Async HTTP client used extensively in the `GitHubClient` and various API integrations. |
| **pytest** & **pytest-asyncio** | Testing framework for unit and integration testing. |

## 2. Directory Structure

This structure represents the active codebase. (Note: `pr/janitor.py.DISABLED` is intentionally omitted).

```text
farm_agent/
├── __init__.py
├── agents/             # Registry and definitions for specialized sub-agents
│   └── registry.py
├── analysis/           # Static analysis tools
│   ├── analyzer.py     # Code parsing and abstract syntax tree (AST) evaluation
│   └── mapper.py       # Codebase mapping utilities
├── cli/                # Command Line Interface entry points
│   └── main.py         # Defines all CLI commands (e.g., superhuman, target, hunt)
├── core/               # System-wide utilities and configurations
│   ├── config.py       # Pydantic configuration resolution and AppConfig
│   ├── exceptions.py   # Custom exception classes
│   ├── logger.py       # Logging setup and formatting
│   ├── memory.py       # Persistent state definitions (sqlite3 schema)
│   ├── rag.py          # Omniscient Context Engine using ChromaDB
│   └── sandbox.py      # DockerSandbox for isolated PoC execution
├── generator/          # Code generation and review engines
│   ├── engine.py       # Main generation engine (enforces AI Gag Order)
│   ├── poc.py          # Proof of Concept generation for dynamic verification
│   ├── reviewer.py     # Layered LLM auditing logic
│   └── scorer.py       # PR impact scoring
├── github/             # GitHub API interaction and management
│   ├── client.py       # Async HTTP client for GitHub API
│   ├── discovery.py    # Repository targeting logic
│   ├── guidelines.py   # Parses repository contributing guidelines
│   └── security_gate.py# Pre-flight checks to avoid disclosing vulnerabilities
├── issues/             # Issue processing
│   └── solver.py       # Issue-First Pipeline and complexity heuristics
├── llm/                # LLM provider integration
│   ├── context.py      # Prompt context building
│   ├── provider.py     # Base interfaces for LLMs
│   └── router.py       # Routes requests to models (e.g., Qwen, Gemini)
├── orchestrator/       # Core execution management
│   ├── human.py        # Super Human Mode delays and scheduling
│   ├── memory.py       # aiosqlite persistent memory management
│   └── pipeline.py     # FarmAgentPipeline orchestrator (DeerFlow)
├── pr/                 # Pull Request lifecycle
│   ├── manager.py      # PR creation and state management
│   └── patrol.py       # PR Patrol for tracking and updating open PRs
├── templates/          # Contribution templates
│   └── registry.py
└── tools/              # External tool definitions
    └── protocol.py     # Tool protocol interfaces
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (cli/main.py)] --> Orchestrator[Orchestrator (pipeline.py)]
    CLI --> HumanMode[Super Human Mode (human.py)]

    Orchestrator --> Memory[(Memory (memory.py / sqlite3))]
    Orchestrator --> GitHubClient[GitHub API (client.py)]
    Orchestrator --> IssueSolver[Issue Solver (solver.py)]
    Orchestrator --> RAG[Omniscient Context Engine (rag.py)]
    Orchestrator --> Sandbox[DockerSandbox (sandbox.py)]
    Orchestrator --> Generator[Code Generator (engine.py)]
    Orchestrator --> PRManager[PR Manager (manager.py)]

    Generator --> LLMRouter[LLM Router (router.py)]
    IssueSolver --> RAG
    Sandbox --> Generator
```

## 4. Core Execution Loops / Entry Points

The system has several primary execution paths driven by `farm_agent.cli.main`:

1.  **Super Human Mode (`farm_agent superhuman`)**:
    *   **Start**: The main entry point for the 24/7 daemon.
    *   **Loop**: It enters a continuous `while True` loop managed by `orchestrator/human.py`.
    *   **Targeting**: Discovers repositories (`github/discovery.py`) or uses predefined targets.
    *   **Execution**: Triggers `FarmAgentPipeline` to process the repository (Issue-First pipeline or Red Team audit).
    *   **Delay**: Uses simulated delays (randomized sleep intervals) to mimic organic human coding activity and avoid API bans.
2.  **Target Loop (`farm_agent target <url>`)**:
    *   Directly invokes `FarmAgentPipeline` on a specific URL.
    *   Downloads repository files via concurrent fetching (`pipeline.py`).
    *   Analyzes the codebase using AST-grep/Semgrep (`analysis/analyzer.py`).
    *   Generates a fix (`generator/engine.py`), verifies it (`sandbox.py`), and creates a PR (`pr/manager.py`).
3.  **PR Patrol (`farm_agent patrol`)**:
    *   Scans existing open Pull Requests tracked in `memory.db`.
    *   Reads reviewer comments and CI/CD status.
    *   Generates response patches or comments to actively maintain the PR until merge.

## 5. Database/State Schema

The system uses `aiosqlite` mapped in `farm_agent/orchestrator/memory.py` to maintain persistent, idempotent state across restarts. Key tables include:

*   **`analyzed_repos`**: Tracks repositories that have been processed to prevent redundant work. (Columns: `full_name`, `language`, `stars`, `analyzed_at`, `findings`).
*   **`submitted_prs`**: Maintains the lifecycle state of generated Pull Requests. Used heavily by PR Patrol.
*   **`run_log`**: Records execution events for statistics and leaderboard tracking.
*   **`knowledge_base`**: Stores meta-information learned during RAG processing.
*   **`target_repos`** & **`blacklisted_repos`**: Manages the dynamic targeting queues and blocks invalid repositories.

All DDL operations in `memory.py` use `IF NOT EXISTS` and ignore operational errors to ensure safe schema migrations during runtime.
