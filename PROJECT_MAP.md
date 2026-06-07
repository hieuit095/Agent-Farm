# Agent-Farm Architectural Blueprint

This document serves as the canonical map for understanding the Agent-Farm v4.0.0 architecture. It details the tech stack, execution pipelines, data models, and directory structure.

## 1. System Overview & Tech Stack

Agent-Farm leverages an asynchronous execution framework with specialized modules for static analysis, language model interaction, dynamic sandbox verification, and GitHub workflow management.

| Component | Technology | Primary Role in the System |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.11+ | Core execution engine and CLI logic. |
| **Build & Packaging** | Hatchling | Modern PEP 517 build backend (`pyproject.toml`). |
| **CLI Framework** | Click | Exposes granular CLI commands (e.g., `run`, `hunt`, `superhuman`). |
| **Concurrency** | Asyncio | Parallel fetching, throttling limits, and non-blocking I/O. |
| **Database/State** | SQLite3 (`aiosqlite`) | Persistent state tracker (WAL mode). See schema below. |
| **LLM Provider** | OpenRouter / Custom | Dynamic multi-model dispatch (e.g., DeepSeek, Qwen, Gemini). |
| **Vector DB (RAG)** | ChromaDB | Semantically indexes subsystem docs (`docs/`, `wiki/`) into chunks. |
| **Isolation** | Docker | Hosts sibling containers (`DockerSandbox`) for dynamic PoC tests. |
| **Version Control** | GitPython | Local cloning, branching, and commit logic. |
| **API Clients** | HTTPX | Handles GitHub REST and GraphQL queries with robust retry jitter. |

## 2. Core Execution Loops

Agent-Farm revolves around resilient pipelines designed to operate continuously.

### SuperHumanLoop (`superhuman`)
An autonomous 24/7 daemon loop (in `farm_agent/orchestrator/human.py`) with simulated human coding delays. It rotates through task queues (hunting, PR patrolling, testing) rather than a relentless unthrottled loop.

### Circular Target Pipeline (`run_circular`)
A deterministic queue processor (in `farm_agent/orchestrator/pipeline.py`) that steps strictly round-robin through targets defined in `target_repo.json`. Used for focused engagements rather than open-ended discovery.

### Issue-First Pipeline (`issues/solver.py`)
Analyzes open GitHub issues. It uses complexity estimation heuristics (based on label, body length, file references) and plans out multi-file changes before generating code.

## 3. Core Module Dependency Graph

The "DeerFlow" architecture orchestrates agents and tasks using an isolated Sandbox component to guarantee safety before commits.

```mermaid
graph TD
    A[CLI Entry (main.py)] --> B(Orchestrator Pipeline)
    B --> C{Discovery & Clone}
    C -->|target_repo.json| D[Code Analyzer & RAG Mapper]
    D --> E{LLM Generator}
    E --> F[DockerSandbox Verification]
    F -->|PoC Fails| G[Drop Finding]
    F -->|PoC & Tests Pass| H{Gatekeeper Audit}
    H -->|Veto| G
    H -->|Approve| I[PR / Issue Submission]
    I --> J[(SQLite Memory)]
```

## 4. SQLite Schema & Persistence

Database file resides in `data/memory.db` and operates in **WAL (Write-Ahead Logging)** mode. Composite indices prevent full table scans.

### Table Schema

* **`analyzed_repos`**: Tracks repositories that have already gone through analysis.
  * Columns: `full_name` (PK), `language`, `stars`, `analyzed_at`, `findings`, `metadata`.
* **`submitted_prs`**: Tracks bot-created PRs, issues, and associated limits counters.
  * Columns: `id` (PK AUTOINCREMENT), `repo`, `pr_number`, `pr_url`, `title`, `type` (e.g. `issue_proposal` for Route B), `status`, `branch`, `fork`, `created_at`, `updated_at`, `ci_fix_attempts`, `discussion_replies`.
  * Unique Constraint: `(repo, pr_number)`.
* **`findings_cache`**: Temporary cache of detected code findings.
  * Columns: `id` (PK), `repo`, `type`, `severity`, `title`, `file_path`, `status`, `created_at`.
* **`run_log`**: Log of overall runs metrics and durations.
  * Columns: `id` (PK AUTOINCREMENT), `started_at`, `finished_at`, `repos_analyzed`, `prs_created`, `findings`, `errors`, `metadata`.
* **`pr_outcomes`**: Stores merged/closed PR states and maintainer review remarks.
  * Columns: `id` (PK AUTOINCREMENT), `repo`, `pr_number`, `pr_url`, `pr_type`, `outcome`, `feedback`, `time_to_close_hours`, `recorded_at`.
  * Unique Constraint: `(repo, pr_number)`.
* **`repo_preferences`**: Learned project contribution preferences updated dynamically from outcomes.
  * Columns: `repo` (PK), `preferred_types`, `rejected_types`, `merge_rate`, `avg_review_hours`, `notes`, `updated_at`.
* **`blacklisted_repos`**: Projects blacklisted due to hostile maintainer checks or failures.
  * Columns: `repo` (PK), `reason`, `pr_number`, `blacklisted_at`.
* **`api_usage_log`**: Tracks LLM API usage.
  * Columns: `id` (PK AUTOINCREMENT), `timestamp`, `provider`.
* **`task_schedule`**: Persistent schedule queue for tasks in the `SuperHumanLoop`.
  * Columns: `task_key` (PK), `next_run`, `updated_at`.
* **`knowledge_base`**: Stores lessons, past critiques, self-learning lessons, and **architectural context**.
  * Columns: `repo_name`, `entry_type` (e.g. `FILTER_REJECTION_LESSON`, `ARCHITECTURE_CONTEXT`), `content`, `created_at`.
  * Unique Constraint: `(repo_name, entry_type, content)`.
* **`target_repos`**: Deterministic circular target queue.
  * Columns: `repo_url` (PK), `status`, `scanned_at`, `language`, `bounty_amount`, `diamond_target`.
* **`repo_style_guides`**: Caches contributing templates, formatting, and structures.
  * Columns: `repo` (PK), `style_summary`, `contributing_md`, `pr_template`, `created_at`, `updated_at`.

### Optimization & Indices
* **`idx_api_usage`**: Composite index on `(provider, timestamp)` to optimize LLM call counts and quota checks.
* **`idx_api_usage_cleanup`**: Index on `(timestamp)` to optimize daily purge queries.

## 5. Omniscient Context Engine & Subsystems

Version 4.0.0 upgrades the system's codebase understanding from superficial file scans to deep documentation and linkage maps:

1. **Documentation Discovery**:
   - In `guidelines.py`, `discover_subsystem_docs()` searches for markdown (`.md`), text (`.txt`), and reStructuredText (`.rst`) files.
   - Focuses recursively on target folders: `docs/`, `architecture/`, `wiki/`, and the root `README.md`.
   - Utilizes `asyncio.to_thread` for non-blocking disk reads.
2. **Semantic Header-Based Chunking**:
   - In `rag.py`, documentation markdown is split cleanly by headers (H1, H2, and H3).
   - Overly large sections are sub-chunked while retaining original header title context.
   - Chunks are stored in ChromaDB using a cosine metric collection, tagged with metadata (`file_path`, `folder_path`, `header_title`, `is_doc: "true"`).
3. **Subsystem Dependency Graphing**:
   - In `mapper.py`, `RepoMapper.get_module_dependencies()` constructs local call linkages.
   - Uses `ast` parsing for Python files to map package imports and external `ast.Call`/`ast.Attribute` expressions.
   - Employs optimized regex patterns for Go (`import`), Rust (`use`), and JavaScript/TypeScript to extract dependency call paths, mapping `"imports"`, `"calls"`, and `"dependents"`.

## 6. Directory & Module Architecture

```text
.                                       # Workspace Root (v4.0.0)
├── Dockerfile                          # Stage 1 builder (wheel creation) + Stage 2 lean runtime v4.0.0
├── docker-compose.yml                  # agent-farm service definition with volumes (data/, logs/, secret_findings/)
├── start.sh                            # Unix quick start wrapper script
├── start.bat                           # Windows quick start wrapper script
│
├── farm_agent/                         # Package root (version = "4.0.0")
│   ├── __init__.py
│   │
│   ├── cli/
│   │   └── main.py                     # Click CLI — command registrations
│   │
│   ├── core/
│   │   ├── config.py                   # Pydantic v2 config and YAML loading
│   │   ├── daily_log.py                # Formats daily markdown activity logs
│   │   ├── exceptions.py               # System exception types hierarchy
│   │   ├── leaderboard.py              # Leaderboard stat collections
│   │   ├── logger.py                   # Rotating file logging system setup
│   │   ├── middleware.py               # Context middleware chain layers
│   │   ├── models.py                   # Core Pydantic data structures definitions
│   │   ├── notifier.py                 # Telegram notifications integration
│   │   ├── profiles.py                 # Thorough, quick, and standard run configurations
│   │   ├── quotas.py                   # OpenRouter usage quota controllers
│   │   ├── rag.py                      # ChromaDB vector DB context loaders (with semantic markdown header chunking)
│   │   ├── retry.py                    # Retry decorators for GitHub/LLM interfaces
│   │   └── sandbox.py                  # DockerSandbox engine with Polyglot Guillotine, PoC execution context mapping
│   │
│   ├── analysis/
│   │   ├── analyzer.py                 # CodeAnalyzer (parallelized security, quality, UX scanners) & BloodhoundAnalyzer
│   │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
│   │
│   ├── generator/
│   │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
│   │   ├── poc.py                      # PoCGenerator (PoC validation & LLM evaluation)
│   │   ├── reviewer.py                 # ReviewerAgent (Self-reflective code auditor with Blast Radius checks)
│   │   └── scorer.py                   # QAHardcoreScorer (Qwen-based QA grader)
│   │
│   ├── github/
│   │   ├── client.py                   # Async-retrying GitHub REST and GraphQL Client
│   │   ├── discovery.py                # Target network search and crawler discoverers
│   │   ├── guidelines.py               # Guidelines, PR templates, and subsystem doc discovery
│   │   └── security_gate.py            # Identifies private security disclosure files
│   │
│   ├── issues/
│   │   └── solver.py                   # IssueSolver (solves issues, multi-file deep planner)
│   │
│   ├── llm/
│   │   ├── agents.py                   # LLM agent prompts and routing models
│   │   ├── context.py                  # Generator system instruction builders
│   │   ├── models.py                   # Model registry definitions
│   │   ├── provider.py                 # OpenRouter integration handlers
│   │   └── router.py                   # Task router mapping
│   │
│   ├── orchestrator/
│   │   ├── memory.py                   # Persistence memory sqlite connection interface
│   │   ├── pipeline.py                 # Pipeline (Standard & Circular pipelines implementation)
│   │   └── human.py                    # SuperHumanLoop relentless daily scheduler
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   ├── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │   └── janitor.py                  # PR Janitor (sweeps and destroys garbage PRs)
│   │
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   │
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
```

## 7. Error Handling & Fallback Matrix

| Scenario | Behavior |
|----------|----------|
| Missing runtime config file | Auto-defaults are used. Loads token from `GITHUB_TOKEN` environment variable or fallbacks to `gh auth token` CLI |
| Qwen / Gemini API failure | **Fail-Closed**: Instantiation throws error, drops the current finding, and skips generation |
| Docker Daemon offline | Sandbox functions return error, blocking PR submissions |
| Sandbox Execution Timeout | Hard timeout wrapper (`timeout --signal=KILL 60s`) terminates execution. Exit code 137. |
| Database WAL mode error | Logs warning and automatically reverts journal mode to `DELETE` |
| Primary Token Rate Limited | Swaps active auth headers to configured `secondary_tokens` list |
| GitHub API Error (502/503/429) | Backs off. Jittered retry: 5 retries, base 10s, max 120s, ±25% random jitter |
| DEV-QA Cycles fail | Marks target status as `COMPLETED_TOO_COMPLEX` to avoid loops |
| Maintainer marked Hostile | Project repository is blocked and blacklisted in `blacklisted_repos` |
| Private Disclosure target | Saved to `/app/secret_findings/{repo}.json`, skips PR creation, sends Telegram/Discord/Slack alert |

*All evidence anchored to source files. All line numbers verified by direct inspection. No speculation.*
