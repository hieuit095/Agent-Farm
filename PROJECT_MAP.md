# 🗺️ Farm-Agent Project Blueprint

This document serves as a deep-dive architectural guide for new developers working on **Farm-Agent**. It maps out the reality of the codebase.

## 1. System Overview & Tech Stack

The Farm-Agent system leverages the following core technologies:

| Technology | Role |
| :--- | :--- |
| **Python >= 3.11** | Core language handling all business logic, orchestration, async flows, and API interactions. |
| **Docker >= 7.1** | Polyglot sandbox validation; isolates fixes in language-specific environments before creating PRs. |
| **SQLite (aiosqlite)** | Persistent memory via WAL-enabled database (`.farm_agent/memory.db`) to record analyzed repos, PR history, and ML outcomes. |
| **ChromaDB** | Ephemeral (RAM-only) vector index enabling Retrieval-Augmented Generation (RAG) cross-file context. |
| **Minimax / Gemini / OpenAI / Anthropic** | LLM Engine providers that analyze code, solve issues, and generate patches (`farm_agent/llm`). |
| **Httpx / aiohttp** | Async HTTP interactions (primarily with GitHub API). |
| **Click & Rich** | Powers the core CLI architecture (`farm_agent/cli/main.py`) with aesthetically pleasing console outputs. |
| **Hatchling** | Python build backend (`pyproject.toml`). |
| **Pytest** | Testing framework for unit tests (`tests/unit/`). |

---

## 2. Directory Structure

A clean overview of the critical paths in the repository:

```text
Farm-Agent/
├── farm_agent/                     # Core Package Source Code
│   ├── agents/                     # Agent registry implementing DeerFlow pattern (extensible agents)
│   ├── analysis/                   # Static analyzers evaluating code for issues and maintainer vibes
│   ├── cli/                        # CLI Commands (main.py is the primary entry point)
│   ├── core/                       # Core Data Models, Memory Database schemas, Configs, Middlewares, and Sandbox Validations
│   ├── generator/                  # Patch / Fix generation (Engine translating LLM outputs to file patches)
│   ├── github/                     # GitHub operations (API client, Repo discovery, Pull Requests)
│   ├── issues/                     # Analyzers for solving open repository issues
│   ├── llm/                        # LLM provider configurations (Model Routing, Prompting structure)
│   ├── notifications/              # Webhook integrations (e.g., Telegram bots)
│   ├── orchestrator/               # High-level control loops (pipeline.py, human.py, memory.py)
│   ├── plugins/                    # Extensibility modules
│   ├── pr/                         # PR Patrol / Janitor operations
│   ├── templates/                  # Base templating (Issue body styles, PR formats)
│   └── tools/                      # Tool registries for agent interaction
├── tests/                          # Automated Pytest suite
├── docker-compose.yml              # Defines daemon services ("superhuman")
├── pyproject.toml                  # Project manifest, config, dependencies
└── Makefile                        # Utility commands for local environment setup
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    %% Main CLI Entry point
    CLI[CLI (farm_agent/cli/main.py)] --> Pipeline[ContribPipeline]
    CLI --> SuperHuman[SuperHumanLoop]
    CLI --> Janitor[PRJanitor]
    CLI --> Patrol[PRPatrol]

    %% Orchestrator logic
    SuperHuman --> Pipeline
    SuperHuman --> Memory[(Memory SQLite)]

    %% Pipeline logic
    Pipeline --> Discovery[RepoDiscovery]
    Pipeline --> Memory
    Pipeline --> Analyzer[CodeAnalyzer]
    Pipeline --> IssueSolver[IssueSolver]
    Pipeline --> Generator[ContributionGenerator]
    Pipeline --> Sandbox[DockerSandbox]
    Pipeline --> PRManager[PRManager]

    %% Low level engines
    Discovery --> GitHubAPI[GitHubClient]
    Analyzer --> GitHubAPI
    Analyzer --> LLMEngine[LLM Provider]
    IssueSolver --> GitHubAPI
    IssueSolver --> LLMEngine
    Generator --> LLMEngine
    Generator --> ChromaDB[(ChromaDB RAG)]
    PRManager --> GitHubAPI
    Patrol --> GitHubAPI
    Patrol --> LLMEngine
    Janitor --> GitHubAPI
    Janitor --> LLMEngine
```

---

## 4. Core Execution Loops / Entry Points

### A. The "Hunt" Command (`farm_agent hunt`)
1. **Discovery:** Discovers repositories via the `GitHubClient` using combinations of configured star counts and programming languages. Prioritizes repositories in "Familiar Grounds" (repos we've successfully merged PRs into).
2. **Analysis/Issue Solving:** Prioritizes open issues via the `IssueSolver` (Issue-First Pipeline). If no actionable issues, it falls back to the `CodeAnalyzer` which statically scans the code to uncover potential issues, rejecting low-impact/trivial ones with the Anti-Farming Filter.
3. **Validation & Patching:** Fetches repository contents, supplies context to the `ContributionGenerator` which triggers the `DockerSandbox` to apply and validate the fix.
4. **Submission:** Orchestrated sequentially using Async locks to simulate human typing before opening a GitHub PR or Issue.

### B. The "Superhuman" Mode (`docker compose up -d superhuman`)
1. **Circadian Rhythm Loop:** A 24/7 autonomous daemon that randomizes waking hours, sets daily dynamic PR targets, and goes to sleep when its quota is met.
2. **Operations:** Intelligently loops between the `hunt` execution flow and the `patrol` protocol.

### C. The "Patrol" Command (`farm_agent patrol`)
1. Fetches open PRs tracked by the `.farm_agent/memory.db`.
2. Reads review comments on those PRs.
3. Uses the `LLMEngine` to automatically solve maintainer questions, correct style formatting, re-sign CLAs, and push the fixes directly to the branch.

### D. The "Janitor" Command (`farm_agent janitor`)
1. Scans GitHub for open PRs created by the bot.
2. Identifies garbage/trivial PRs and utilizes the LLM to auto-close and delete the branches to avoid clutter.

---

## 5. Database/State Schema (`farm_agent/orchestrator/memory.py`)

Persistent tracking is achieved using an internal SQLite database (`.farm_agent/memory.db`), with **Write-Ahead Logging (WAL)** enabled for async safe access.

| Table | Purpose |
| :--- | :--- |
| **analyzed_repos** | Tracks repositories we have evaluated, ensuring no redundant work is done (e.g. tracking language, stars, findings). |
| **submitted_prs** | A critical ledger of all PRs and Issues created. Used heavily for "Patrol", "Familiar Grounds" (Alumni sync), and enforcing daily rate limits. |
| **findings_cache** | A local caching system for vulnerabilities discovered in code scans. |
| **run_log** | Records individual CLI pipeline runs (used by `stats`). |
| **pr_outcomes** | ML pipeline table tracking closed/merged statuses. Records PR outcomes to automatically compute "preferences". |
| **repo_preferences** | Learns which types of patches maintainers of specific repos like or reject, shaping future attempts. |
| **blacklisted_repos** | Stores URLs for repos with toxic maintainer vibes (from `Vibe Check`) or ones manually excluded from contribution loops. |
| **api_usage_log** | Overdrive protection logic. Uses a sliding window logic to enforce Minimax/LLM provider API constraints. |
| **task_schedule** | A background-job queue tracker for long-running non-blocking maintenance tasks like quota purging. |
