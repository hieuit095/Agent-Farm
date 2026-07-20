# 🗺️ Agent-Farm Project Architecture Map

This document serves as a deep-dive architectural guide to the Agent-Farm system.

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous system that crawls GitHub, analyzes repositories for vulnerabilities or issues, generates fixes, validates them in an isolated Docker sandbox, and submits pull requests.

| Component | Technology | Role in Project |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Core implementation language. |
| **CLI Framework** | Click | Provides the command-line interface (`farm_agent`). |
| **Data Validation** | Pydantic (v2) | Core data structures and configuration management. |
| **HTTP Client** | HTTPX | Asynchronous HTTP requests to GitHub and LLM providers. |
| **Containerization** | Docker | Sandbox execution environment for PoC and test validation. |
| **Vector Database** | ChromaDB | Local vector store for the Omniscient Context Engine (RAG). |
| **Database** | SQLite & aiosqlite | Persistent memory and state management (`data/memory.db`). |
| **LLM Integration** | OpenRouter (DeepSeek, Qwen), Minimax | Intelligence layer for code analysis, generation, and review. |
| **Git Operations** | GitPython | Local repository management and PR branch creation. |

## 2. Directory Structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── start.sh
├── start.bat
│
├── farm_agent/
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
│   │   ├── notifier.py                 # Telegram/Slack/Discord notifications
│   │   ├── profiles.py                 # Run configurations
│   │   ├── quotas.py                   # Quota controllers
│   │   ├── rag.py                      # ChromaDB vector DB context loaders
│   │   ├── retry.py                    # Retry decorators for external APIs
│   │   └── sandbox.py                  # DockerSandbox engine for PoC execution
│   │
│   ├── analysis/
│   │   ├── analyzer.py                 # CodeAnalyzer & BloodhoundAnalyzer
│   │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
│   │
│   ├── generator/
│   │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
│   │   ├── poc.py                      # PoC validation generator
│   │   ├── reviewer.py                 # ReviewerAgent (Self-reflective code auditor)
│   │   └── scorer.py                   # QA grader
│   │
│   ├── github/
│   │   ├── client.py                   # Async GitHub REST and GraphQL Client
│   │   ├── discovery.py                # Target network search and crawler discoverers
│   │   ├── guidelines.py               # Guidelines, PR templates, and subsystem doc discovery
│   │   └── security_gate.py            # Identifies private security disclosure files
│   │
│   ├── issues/
│   │   └── solver.py                   # IssueSolver (solves specific open issues)
│   │
│   ├── llm/
│   │   ├── agents.py                   # LLM agent prompts and routing models
│   │   ├── context.py                  # Generator system instruction builders
│   │   ├── models.py                   # Model registry definitions
│   │   ├── provider.py                 # LLM provider integration handlers
│   │   └── router.py                   # Task router mapping
│   │
│   ├── notifications/
│   │   └── notifier.py                 # Notification handlers
│   │
│   ├── orchestrator/
│   │   ├── memory.py                   # Persistent SQLite memory interface
│   │   ├── pipeline.py                 # Standard & Circular orchestrator pipelines
│   │   └── human.py                    # SuperHumanLoop relentless daily scheduler
│   │
│   ├── plugins/
│   │   └── __init__.py
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   └── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │
│   ├── templates/
│   │   ├── builtin/                    # Built-in contribution templates
│   │   └── registry.py                 # Template registry
│   │
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   │
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[farm_agent CLI] --> Pipeline[FarmAgentPipeline]
    CLI --> HumanLoop[SuperHumanLoop]
    CLI --> PRPatrol[PR Patrol]
    CLI --> IssueSolver[IssueSolver]

    HumanLoop --> Pipeline

    Pipeline --> Discovery[GitHub Discovery]
    Pipeline --> Analyzer[Code Analysis & RAG]
    Pipeline --> Generator[Contribution Generator]
    Pipeline --> PRManager[PR Manager]

    Analyzer --> RAG[Omniscient Context Engine]
    Analyzer --> Mapper[RepoMapper (AST/Calls)]

    Generator --> Sandbox[DockerSandbox]
    Generator --> Reviewer[ReviewerAgent (Expert Appraisal)]

    Sandbox --> PoC[Dynamic Bug Verification]
    Sandbox --> Regression[Blast Radius & Regression Tests]

    PRManager --> GitHub[GitHub Client]

    Pipeline --> Memory[(SQLite Memory)]
```

## 4. Core Execution Loops / Entry Points

1. **Standard Pipeline (`farm_agent run` or `farm_agent target`)**:
   - `FarmAgentPipeline` coordinates the flow.
   - Discovers targets via `GitHubClient`.
   - Analyzes code via `CodeAnalyzer` and builds context via the `Omniscient Context Engine` (RAG).
   - Generates patches and PoCs via `ContributionGenerator`.
   - Validates in `DockerSandbox` (Dynamic Bug Verification and Regression Auditing).
   - Appraises the fix (Expert Appraisal).
   - Submits PR via `PRManager`.

2. **Terminator Mode (`farm_agent superhuman`)**:
   - A continuous execution loop (`SuperHumanLoop`).
   - Retrieves targets from the `target_repos` database table.
   - Runs the `FarmAgentPipeline` for each target.
   - Periodically runs PR patrol to address maintainer feedback and fix CI issues.

3. **Issue Solver (`farm_agent solve`)**:
   - Focuses specifically on resolving existing open issues.
   - Analyzes the issue context and uses a multi-file deep planner (`IssueSolver`) to generate a fix.
   - Follows the same validation and PR submission flow.

4. **PR Patrol (`farm_agent patrol`)**:
   - Polls open PRs submitted by the system.
   - Checks for new maintainer comments or failing CI checks.
   - Drafts fixes and pushes auto-commits to resolve issues.

## 5. Database/State Schema (`data/memory.db`)

Agent-Farm utilizes a SQLite database in WAL (Write-Ahead Logging) mode to maintain state, track progress, and learn from outcomes.

- **`analyzed_repos`**: Tracks repositories that have been analyzed. (`full_name` PK)
- **`submitted_prs`**: Records bot-created PRs, issues, and their statuses. Includes a unique constraint on `(repo, pr_number)`.
- **`findings_cache`**: Temporary cache of detected code findings before they are processed.
- **`run_log`**: Logs of overall pipeline run metrics, durations, and counts.
- **`pr_outcomes`**: Stores the final state of PRs (merged/closed) and maintainer feedback.
- **`repo_preferences`**: Learned project contribution preferences dynamically updated from PR outcomes.
- **`blacklisted_repos`**: Repositories blacklisted due to hostile maintainer responses or persistent failures.
- **`api_usage_log`**: Tracks LLM API usage and token consumption.
- **`task_schedule`**: Persistent schedule queue for tasks in the `SuperHumanLoop`.
- **`knowledge_base`**: Stores lessons, critiques, and architectural context. Includes a unique constraint on `(repo_name, entry_type, content)`.
- **`target_repos`**: Deterministic circular target queue for Continuous Execution (Terminator Mode). (`repo_url` PK)
- **`repo_style_guides`**: Caches contribution templates, formatting, and structures per repository.
