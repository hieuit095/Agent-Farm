# PROJECT_MAP.md — Farm-Agent Architectural Blueprint

## 1. System Overview & Tech Stack

**Farm-Agent** is an autonomous AI agent that discovers open-source GitHub repositories matching predefined criteria (language, star range, activity), scans their code for issues (security vulnerabilities, code quality bugs, performance problems, etc.), generates patches via LLM, strictly validates patches in an isolated polyglot Docker sandbox, and creates PRs or GitHub Issues to contribute back.

**Active Tech Stack:**

| Component | Technology | Role / Evidence |
|-----------|------------|-----------------|
| **Language** | Python 3.11+ | Core implementation (`requires-python = ">=3.11"` in `pyproject.toml`) |
| **HTTP Client** | `httpx` (async) | Interacting with the GitHub REST API and LLM providers (`httpx>=0.27,<1.0`) |
| **LLM Providers** | MiniMax (Primary), OpenRouter, Gemini, OpenAI, Anthropic, Ollama | Used for generating code patches, reviewing PRs, and classifying issues (`config.py:55-68`) |
| **Database** | SQLite via `aiosqlite` | Persistent memory mapping using WAL mode (e.g. `memory.db`) |
| **Sandbox Environment** | `docker>=7.1,<8.0` | Polyglot Guillotine for strict execution and validation of untrusted code patches (`sandbox.py`) |
| **Scheduling** | `apscheduler>=3.10,<4.0` | Task scheduling and recurring operations (`pyproject.toml`) |
| **Config & Validation** | Pydantic v2 + YAML | Strong typing and configuration management (`config.py`) |
| **CLI & TUI** | `click>=8.1,<9.0` + `rich>=13.0,<14.0` | Provides a robust Command Line Interface mapped in `main.py` |
| **Vector Database** | `chromadb>=0.4,<1.0` | Ephemeral RAG index for ensuring contextual accuracy across multi-file code patches |
| **Git Operations** | `gitpython>=3.1,<4.0` | Cloning, branching, committing, and pushing code modifications locally before PR creation |

## 2. Directory Structure

```text
farm_agent/
├── __init__.py           # Package version (3.0.0)
├── agents/               # Lightweight stubs wrapping components
│   ├── __init__.py
│   └── registry.py       # DeerFlow agent system registry
├── analysis/             # Analyzers for evaluating repository logic and issues
│   ├── __init__.py
│   ├── analyzer.py       # Static code analyzer
│   └── mapper.py         # Code mapping capabilities
├── cli/                  # Command Line Interface logic
│   ├── __init__.py
│   └── main.py           # Click CLI, containing main commands (run, hunt, patrol, etc.)
├── core/                 # Core utilities, configuration, schemas, and system resilience
│   ├── __init__.py
│   ├── config.py         # Pydantic configuration definitions
│   ├── daily_log.py      # Daily logging tracker
│   ├── exceptions.py     # Custom exceptions (GitHubAPIError, LLMRateLimitError, etc.)
│   ├── leaderboard.py    # Tracks PR stats and repo rankings
│   ├── logger.py         # Structured application logger
│   ├── middleware.py     # DeerFlow middleware chain for quota and quality enforcement
│   ├── models.py         # Shared Pydantic data models
│   ├── notifier.py       # Notification dispatchers
│   ├── profiles.py       # Contribution profiles
│   ├── quotas.py         # Rate limits and API quota definitions
│   ├── rag.py            # Local ChromaDB RAG engine
│   ├── retry.py          # Retry and exponential backoff decorators
│   └── sandbox.py        # Polyglot Docker Sandbox to validate code (12 languages supported)
├── generator/            # Engine to generate changes via LLMs
│   ├── __init__.py
│   ├── engine.py         # Code Generation Engine invoking LLMs
│   ├── reviewer.py       # PR and patch reviewers
│   └── scorer.py         # QA Scorer evaluating the LLM output against style guides
├── github/               # GitHub API, REST interface, and security handlers
│   ├── __init__.py
│   ├── client.py         # Handles API interactions (PRs, issues, commits) and rate limiting
│   ├── discovery.py      # Target identification logic
│   ├── guidelines.py     # Fetches repository guidelines (e.g., CONTRIBUTING.md)
│   └── security_gate.py  # Checks SECURITY.md files to prevent premature disclosure
├── issues/               # Logic for issue triage and resolution
│   ├── __init__.py
│   └── solver.py         # Estimates complexity and classifies/solves issues
├── llm/                  # Integration layers for different LLM providers
│   ├── __init__.py
│   ├── agents.py         # Multi-agent coordination logic
│   ├── context.py        # Context handling for queries
│   ├── models.py         # Catalog of supported models and task types
│   ├── provider.py       # Abstracts Provider APIs
│   └── router.py         # Task router for model assignment
├── notifications/        # Webhook integrations for Slack, Discord, Telegram
│   ├── __init__.py
│   └── notifier.py
├── orchestrator/         # Main business logic binding subsystems
│   ├── __init__.py
│   ├── human.py          # SuperHumanLoop: 24/7 autonomous loop
│   ├── memory.py         # Persistent memory coordination
│   └── pipeline.py       # ContribPipeline: The main operational workflow orchestrator
├── plugins/              # Plugin abstractions
│   └── __init__.py
├── pr/                   # Tools to manage Pull Requests
│   ├── __init__.py
│   ├── janitor.py.DISABLED # Incomplete feature for sweeping PRs
│   ├── manager.py        # Handles forking, branching, and pushing modifications
│   └── patrol.py         # PR Patrol: handles PR feedback auto-responses and closures
├── templates/            # Boilerplate structures for PRs and issues
│   ├── __init__.py
│   ├── builtin/
│   └── registry.py
└── tools/                # General tool integration protocol
    ├── __init__.py
    └── protocol.py
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    A[CLI (main.py)] -->|Initiates| B[Orchestrator Pipeline]
    A -->|Initiates| C[SuperHumanLoop]
    B -->|Persists State| D[(SQLite Memory)]
    C -->|Uses| B

    B --> E[GitHub Client]
    B --> F[Analysis Engine]
    B --> G[Generator Engine]
    B --> H[Docker Sandbox]
    B --> I[PR Manager]

    E -->|Discovers Repos| B
    E -->|Fetches Security/Guidelines| B

    F -->|RAG Indexing| J[ChromaDB]
    F -->|Semgrep Pre-scan| B

    G -->|Queries| K[LLM Router]
    K --> L[Minimax/OpenRouter]

    H -->|Validates Patch| B

    I -->|Forks/Commits/Pushes| E
    I -->|Notifies| M[Notifier]
```

## 4. Core Execution Loops / Entry Points

Farm-Agent is orchestrated primarily via CLI entry points. Below is the step-by-step logic for the primary loop defined in the orchestrator pipeline:

1. **Discovery (`farm_agent/github/discovery.py`):** The engine searches for repositories meeting a specific criteria or reads targeted lists (`target_repo.json`).
2. **Security Gate & Vibe Check (`farm_agent/github/security_gate.py`, `farm_agent/orchestrator/pipeline.py`):** The system scans `SECURITY.md` for private disclosure requirements. If found, the pipeline aborts for that repo. It also filters out repos with explicit "Hostile" mantainer vibes or anti-bot constraints.
3. **Analysis & RAG Indexing (`farm_agent/analysis/analyzer.py`, `farm_agent/core/rag.py`):**
   - Uses ast-grep and Semgrep (`BloodhoundAnalyzer`) for vulnerability discovery.
   - Builds an ephemeral ChromaDB index to allow multi-file contextual queries.
4. **Code Generation (`farm_agent/generator/engine.py`):** Prompts the LLM (routed via `TaskRouter`) to provide a fix for identified issues or statically analyzed bugs. An "AI Gag Order" filter immediately rejects generations including phrases like "As an AI".
5. **Sandbox Validation (`farm_agent/core/sandbox.py`):** Uses an isolated, highly restrictive polyglot Docker environment to build and run linters or tests against the modified code. If errors are detected, the agent enters a self-correction loop (up to 3 attempts). This is a rigid gate; if Docker is unavailable, PR creation is blocked.
6. **PR Creation (`farm_agent/pr/manager.py`):** The PR manager forks the repository (if necessary), creates a local branch with the patch, pushes to the remote, and opens the PR via the GitHub REST API.
7. **PR Patrol (`farm_agent/pr/patrol.py`):** Running autonomously as a separate CLI entrypoint, this loop continually monitors open PRs to interpret maintainer feedback and autonomously generate fixes.

## 5. Database/State Schema

The local SQLite database (`memory.db`) tracks persistent operations across executions to avoid redundant analysis and handle throttling constraints efficiently.

| Table Name | Description | Key Fields |
|------------|-------------|------------|
| `analyzed_repos` | Tracks repositories that have been fully analyzed to avoid repetitive scanning. | `full_name`, `language`, `stars`, `analyzed_at`, `findings` |
| `submitted_prs` | Logs the details of every Pull Request created by Farm-Agent. | `repo`, `pr_number`, `pr_url`, `status`, `type` |
| `findings_cache` | Stores intermediate vulnerability/issue discoveries locally prior to resolution. | `id`, `repo`, `type`, `severity`, `title`, `file_path`, `status` |
| `run_log` | High-level tracking of pipeline execution iterations for performance monitoring. | `id`, `started_at`, `finished_at`, `repos_analyzed`, `prs_created`, `errors` |
| `pr_outcomes` | Logs final conclusions (merged/closed/ghosted) of PRs to track success rates. | `id`, `repo`, `pr_number`, `outcome`, `time_to_close_hours` |
| `repo_preferences` | Records repository-specific rules or restrictions deduced by the agent over time. | `repo`, `preferred_types`, `rejected_types`, `merge_rate` |
| `blacklisted_repos`| Prevents future interactions with repositories that resulted in explicitly hostile feedback. | `repo`, `reason`, `blacklisted_at` |
| `api_usage_log` | Sliding-window tracker for API hits (specifically for rate-limiting calculations). | `id`, `timestamp`, `endpoint`, `tokens_used` |
| `task_schedule` | Multi-process coordination table ensuring distributed quota cleanup. | `task_id`, `status`, `last_run`, `next_run` |
| `knowledge_base` | Ephemeral/Persistent mapping table for cross-repo heuristics. | `key`, `value`, `updated_at` |
