# 🗺️ Agent-Farm (v4.0.0) — Architecture Blueprint

This document provides a deep-dive architectural guide to the internal workings, dependency flow, and state schemas of the **Agent-Farm** project.

---

## 1. System Overview & Tech Stack

| Technology | Role | Description / Notes |
|------------|------|----------------------|
| **Python 3.11+** | Core Language | Strict async/await, heavily utilizing `asyncio`. Pydantic models for type safety. |
| **Docker (v7.1+)** | Sandboxing & Orchestration | Creates locked-down `DockerSandbox` environments for executing generated Proof-of-Concepts (PoCs) and running PR test validations. Host docker socket (`/var/run/docker.sock`) is mounted. |
| **SQLite (WAL Mode)** | State Memory (`data/memory.db`) | Tracks analyzed repositories, PRs, outcomes, blacklists, quotas, and the architectural context knowledge base. |
| **ChromaDB** | Vector DB / Context RAG | Indexes recursively-discovered markdown/doc files with semantic header chunking to provide deep contextual codebase knowledge. |
| **OpenRouter / LLMs** | AI Pipeline | Drives Code Analyzers, Patch Generators, Peer Reviewers, and Strict Quality Gates using `deepseek-v4-pro`, `qwen3.7-max`, and `gemini-3.5-flash`. |
| **Click / Rich** | CLI & UI | Provides powerful CLI tools like `run`, `hunt`, `superhuman`, `patrol`, and system statistics tracking. |
| **Hatchling** | Build Backend | Manages package distribution (`pyproject.toml`). |
| **Ruff / Pytest** | QA Toolchain | Used internally for enforcing 100-char limits, code style, and performing isolated unit testing. |

---

## 2. Directory Structure

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
│   │   ├── human.py                    # SuperHumanLoop relentless daily scheduler ("Terminator Mode")
│   │   ├── memory.py                   # Persistence memory sqlite connection interface
│   │   └── pipeline.py                 # FarmAgentPipeline (Standard & Circular pipelines implementation)
│   │
│   ├── plugins/                        # Extension module interfaces
│   ├── templates/                      # Generation templates
│   ├── notifications/                  # Notifications integration logic
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   └── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   │
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    subgraph CLI & Initialization
        A[cli/main.py] --> B(core/config.py)
        A --> C(orchestrator/pipeline.py)
        A --> U(orchestrator/human.py - SuperHumanLoop)
    end

    subgraph Orchestrator (FarmAgentPipeline)
        C --> D(orchestrator/memory.py)
        C --> E(github/client.py)
        C --> F(github/discovery.py)
        C --> G(analysis/analyzer.py)
        C --> H(generator/engine.py)
        C --> I(pr/manager.py)
    end

    subgraph Deep Code Understanding
        G --> J(analysis/mapper.py - RepoMapper)
        G --> K(core/rag.py - Omniscient Context)
    end

    subgraph Validation & Generation
        H --> L(generator/poc.py)
        L --> M(core/sandbox.py - DockerSandbox)
        H --> N(generator/reviewer.py)
        N --> M
    end

    subgraph External
        E --> O((GitHub API))
        G --> P((OpenRouter LLMs))
        H --> P
        K --> Q[(ChromaDB)]
        D --> R[(memory.db SQLite)]
        M --> S((Host Docker Socket))
    end
```

---

## 4. Core Execution Loops / Entry Points

Agent-Farm utilizes an end-to-end `FarmAgentPipeline` logic managed within `farm_agent/orchestrator/pipeline.py`. The standard execution flow (`farm_agent run` or `farm_agent superhuman`) operates as follows:

1. **Target Discovery:** The system crawls GitHub via `github/discovery.py` or retrieves hardcoded/tracked targets from `memory.db`.
2. **Reconnaissance & Mapping:**
   * It clones the target into a unique temporary directory caching `clone_url` (`_clone_and_patch_repo`).
   * Evaluates maintainer styles and retrieves guidelines using `github/guidelines.py`.
   * Maps internal AST dependencies (Go, Rust, Python, TS) through `analysis/mapper.py` and vectors documentation via ChromaDB.
3. **Static Analysis & Appraisal (Anti-Farming Filter):**
   * Uses AST-Grep/Semgrep logic and LLM red-team sweeps via `analysis/analyzer.py`.
   * Findings go through strict filtering using `Qwen` models to drop trivial or false positive issues.
4. **Patch Generation & Dynamic Validation:**
   * The `generator/engine.py` constructs a self-contained fix and PoC script.
   * `DockerSandbox` runs the PoC inside a container. If the bug doesn't trigger initially, it drops the patch.
   * A patch is applied and the PoC is re-run. Native test suites are also run to guarantee zero regressions.
5. **PR Submission & Patrol:**
   * `pr/manager.py` forks the target, creates branches, commits cleanly separated patches (avoiding CLI string-injection vulnerabilities), and creates the PR.
   * PRs remain monitored by `pr/patrol.py` (PR Patrol) to answer comments or push auto-heal fixes when CI pipeline failures are detected.

---

## 5. Database/State Schema

Database file resides in `data/memory.db` and operates in **WAL (Write-Ahead Logging)** mode. Composite indices prevent full table scans.

* **`analyzed_repos`**: Tracks repositories that have already gone through analysis.
  * Columns: `full_name` (PK), `language`, `stars`, `analyzed_at`, `findings`, `metadata`.
* **`submitted_prs`**: Tracks bot-created PRs, issues, and associated limits counters.
  * Columns: `id` (PK AUTOINCREMENT), `repo`, `pr_number`, `pr_url`, `title`, `type`, `status`, `branch`, `fork`, `created_at`, `updated_at`, `ci_fix_attempts`, `discussion_replies`.
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
* **`knowledge_base`**: Stores lessons, past critiques, self-learning lessons, and architectural context.
  * Columns: `repo_name`, `entry_type`, `content`, `created_at`.
  * Unique Constraint: `(repo_name, entry_type, content)`.
* **`target_repos`**: Deterministic circular target queue.
  * Columns: `repo_url` (PK), `status`, `scanned_at`, `language`, `bounty_amount`, `diamond_target`.
* **`repo_style_guides`**: Caches contributing templates, formatting, and structures.
  * Columns: `repo` (PK), `style_summary`, `contributing_md`, `pr_template`, `created_at`, `updated_at`.

### Optimization & Indices
* **`idx_api_usage`**: Composite index on `(provider, timestamp)` to optimize LLM call counts and quota checks.
* **`idx_api_usage_cleanup`**: Index on `(timestamp)` to optimize daily purge queries.