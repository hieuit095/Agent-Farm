# 🗺️ Agent-Farm PROJECT_MAP

This document serves as a deep-dive architectural guide for new developers, mapping out the core components, execution flows, and data structures of the Agent-Farm project.

## 1. System Overview & Tech Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Core implementation language. |
| **Packaging/Build** | Hatchling (`pyproject.toml`) | Project build backend. |
| **HTTP Client** | `httpx` | Async requests to GitHub REST and GraphQL APIs. |
| **Data Validation** | `pydantic`, `pydantic-settings` | Schema validation, type enforcement, and configuration management. |
| **CLI Framework** | `click`, `rich` | Terminal interfaces, progress bars, and stylized outputs. |
| **Git Operations** | `GitPython` | Local repository cloning, patching, branching, and committing. |
| **Database/State** | `aiosqlite` (SQLite) | Asynchronous persistence for memory, queue, stats, and run logs (WAL mode). |
| **LLM Interfaces** | `google-genai`, `openai`, `anthropic`, `httpx` | Integrates with OpenRouter (DeepSeek, etc.), Qwen, and Gemini. |
| **Containerization** | `docker` | Orchestration and execution of isolated sandboxes for PoC and testing. |
| **Vector Database** | `chromadb` | Local knowledge base for RAG-powered context discovery. |
| **Job Scheduling** | `apscheduler` | Managing periodic tasks within the `SuperHumanLoop`. |

## 2. Directory Structure

```text
.
├── docker-compose.yml        # Docker service configuration defining 'internet_access' and 'sandbox_isolated' networks
├── Dockerfile                # Multi-stage Docker build for the application
├── pyproject.toml            # Project metadata and dependencies (Hatchling)
├── README.md                 # Main project documentation
├── start.bat                 # Windows quick-start script
├── start.sh                  # Unix quick-start script
└── farm_agent/               # Main Application Package
    ├── __init__.py
    ├── agents/               # LLM agent configurations and prompt definitions
    │   └── registry.py
    ├── analysis/             # Codebase scanning, AST analysis, and RAG discovery
    │   ├── analyzer.py       # CodeAnalyzer & BloodhoundAnalyzer (Red Team loop)
    │   └── mapper.py         # RepoMapper for AST/regex dependency graphing
    ├── cli/                  # Command-line interface definitions
    │   └── main.py
    ├── core/                 # Shared core utilities and configuration
    │   ├── config.py         # Pydantic configuration loader
    │   ├── daily_log.py      # Formats daily markdown activity logs
    │   ├── exceptions.py     # Custom exception hierarchy
    │   ├── leaderboard.py    # Stat collections for leaderboard
    │   ├── logger.py         # Rotating file logging system
    │   ├── middleware.py     # Context middleware layers
    │   ├── models.py         # Shared Pydantic data structures
    │   ├── notifier.py       # Notification integrations (Telegram, Discord, Slack)
    │   ├── profiles.py       # Run profile configurations (thorough, quick, standard)
    │   ├── quotas.py         # LLM API usage tracking and quota management
    │   ├── rag.py            # ChromaDB integrations for RAG-based context
    │   ├── retry.py          # Retry decorators
    │   └── sandbox.py        # DockerSandbox for isolated PoC/test execution
    ├── generator/            # Content generation (patches, PoCs, and fixes)
    │   ├── engine.py         # ContributionGenerator (Patch and file correction)
    │   ├── poc.py            # PoCGenerator (Generates dynamic test scripts)
    │   ├── reviewer.py       # ReviewerAgent (Self-reflective code auditor)
    │   └── scorer.py         # QAHardcoreScorer (Gate 1 - Qwen-based QA grader)
    ├── github/               # GitHub API interactions
    │   ├── client.py         # Async REST and GraphQL client
    │   ├── discovery.py      # Target discovery and crawling
    │   ├── guidelines.py     # Discovers project guidelines and RAG docs
    │   └── security_gate.py  # Checks for private security disclosure protocols
    ├── issues/               # Issue resolution logic
    │   └── solver.py         # IssueSolver (Issue-First Pipeline)
    ├── llm/                  # Low-level LLM provider logic
    │   ├── agents.py
    │   ├── context.py
    │   ├── models.py
    │   ├── provider.py       # OpenRouter, Minimax integration
    │   └── router.py         # Task-based LLM routing
    ├── notifications/
    │   └── notifier.py
    ├── orchestrator/         # Main system execution loops
    │   ├── human.py          # SuperHumanLoop (Terminator Mode relentless loop)
    │   ├── memory.py         # Database memory management (`aiosqlite`)
    │   └── pipeline.py       # FarmAgentPipeline (Main orchestration logic)
    ├── plugins/
    ├── pr/                   # Pull Request management and interaction
    │   ├── manager.py        # PRManager (Forking, branching, pushing, submitting)
    │   └── patrol.py         # PR Patrol (Checking CI, answering comments)
    ├── templates/            # Built-in contribution templates
    │   ├── builtin/
    │   └── registry.py
    └── tools/
        └── protocol.py
```

*(Note: Trivial files like `.gitignore` and `.env.example`, as well as disabled files like `janitor.py.DISABLED`, are omitted for clarity).*

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI: main.py] --> Orchestrator[Orchestrator: pipeline.py / human.py]
    Orchestrator --> TargetDiscovery[GitHub: discovery.py]
    Orchestrator --> DB[(SQLite: memory.db)]
    Orchestrator --> GitHubClient[GitHub: client.py]
    Orchestrator --> CodeAnalyzer[Analysis: analyzer.py]

    CodeAnalyzer --> RAG[Core: rag.py / ChromaDB]
    CodeAnalyzer --> ASTGraph[Analysis: mapper.py]

    Orchestrator --> ContributionGenerator[Generator: engine.py]
    ContributionGenerator --> PoCGen[Generator: poc.py]
    ContributionGenerator --> DockerSandbox[Core: sandbox.py]

    ContributionGenerator --> Filter1[Gate 1: Layer 1 Appraisal (Qwen)]
    Filter1 --> Filter2[Gate 2: Supreme Audit (Gemini)]

    Orchestrator --> PRManager[PR: manager.py]
    PRManager --> GitHubClient

    Orchestrator --> Notifications[Core/Notifications: notifier.py]
```

## 4. Core Execution Loops / Entry Points

### Target Acquisition & Setup
1. The user initiates a run via the CLI (e.g., `farm_agent run`, `farm_agent superhuman`).
2. The orchestrator pulls targets either via GitHub discovery (`github.discovery`) or from the SQLite queue (`target_repos`).
3. Repositories are filtered (e.g., ignoring excluded languages, blacklisted repos) and cloned locally via `GitPython`.

### Codebase Analysis (RAG & RAG Codebase Mapping)
1. `CodeAnalyzer` coordinates deep inspection of the cloned repository.
2. `github.guidelines` discovers documentation (`.md`, `.rst`, etc.), splits them by semantic headers (`core.rag`), and stores them in a ChromaDB vector index.
3. `analysis.mapper` builds an AST-based call graph mapping file dependencies, extracting "imports", "calls", and "dependents".

### DEV-QA Loop & Filtering
1. Potential vulnerabilities/bugs are identified.
2. The finding is passed through the Anti-Farming Filter: Gate 1 (Qwen) for structural appraisal and Gate 2 (Gemini) for real-world value checks to veto low-effort spam.
3. If approved, `Generator.poc` builds a Proof-of-Concept (PoC) script.
4. The PoC runs inside `DockerSandbox` (on the `sandbox_isolated` network). If it fails to trigger the bug, the finding is discarded.
5. The `ContributionGenerator` drafts a patch.

### Validation (Blast Radius Check)
1. The patch is applied locally.
2. The `DockerSandbox` validates the fix using a double-pass approach:
   - **Pass 1:** Run the PoC again to ensure the vulnerability is resolved.
   - **Pass 2:** Execute the native test suite to check for regressions.
3. If regressions occur, the cycle feeds the error back to the LLM to self-correct.

### PR Submission
1. Once validated, `PRManager` handles creating a fork, checking out a new branch, applying the verified patch, and pushing it back to GitHub.
2. A PR or Issue is created using `GitHubClient`. If it's a security vulnerability targeting a private project, it triggers a private disclosure alert instead.

### Continuous Patrol (Terminator Mode / PR Patrol)
1. In continuous modes (`farm_agent superhuman` or `farm_agent patrol`), the agent loops through existing PRs.
2. It reads maintainer feedback and parses CI errors, dynamically spinning up sandboxes to auto-correct issues and push fixes back to the PR.

## 5. Database/State Schema

Agent-Farm leverages an `aiosqlite` database (`memory.db`) operating in WAL (Write-Ahead Logging) mode. Below is an overview of the core schema:

- `analyzed_repos`: Tracks repositories processed by the analyzer, including metadata and timestamps.
- `submitted_prs`: Logs all pull requests/issues submitted. Fields include `repo`, `pr_number`, `type`, `status`, and `ci_fix_attempts`.
- `findings_cache`: Temporary storage for detected vulnerabilities/bugs before they are transformed into patches.
- `run_log`: High-level metrics for CLI execution runs (e.g., duration, repos processed, total PRs).
- `pr_outcomes`: Tracks the result of submitted PRs (merged, closed, time to close) and records maintainer feedback.
- `repo_preferences`: Dynamically learned preferences for specific projects (e.g., rejected PR types, merge rates).
- `blacklisted_repos`: Projects skipped due to prior hostile responses or repeated failures.
- `api_usage_log`: Logs API calls for tracking quota limits across providers.
- `knowledge_base`: Stores RAG architecture contexts, filter rejection lessons, and self-learning data.
- `target_repos`: The circular queue for targeting (URLs, status, language, bounty amounts) primarily used in Terminator Mode.
- `repo_style_guides`: Caches contributing templates and stylistic rules for specific repositories.
- `task_schedule`: Queue for scheduled tasks handled by the orchestrator.
