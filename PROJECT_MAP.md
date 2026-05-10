# 🗺️ Farm-Agent v3.0+ Project Map

This document serves as the architectural blueprint for the Farm-Agent codebase. It reflects the **actual, verified state** of the codebase, ensuring that core modules, dependencies, execution flows, and data schemas are accurately represented.

---

## 1. System Overview & Tech Stack

Farm-Agent is a highly orchestrated application combining CLI interfaces, LLM generation, GitHub integrations, code analysis, and sandboxed validation to automate open-source contributions.

| Component | Technology | Description |
|-----------|------------|-------------|
| **Core Framework** | Python 3.11+ | The primary language for the agent's logic. |
| **CLI App** | `click`, `rich` | Drives the command-line interface, terminal rendering, and interaction. |
| **LLM Orchestration** | `httpx`, `pydantic` | Async HTTP requests to Minimax, OpenRouter, and others, paired with robust data validation. |
| **State Persistence** | `aiosqlite` | Asynchronous SQLite database (`memory.db`) to store runtime state, quotas, target queues, and PR histories. |
| **Code Execution** | Docker SDK (`docker`) | Ephemeral, network-isolated "Polyglot Sandbox" to validate code modifications. |
| **Code Analysis** | `ast-grep`, Semgrep | Static code analysis tools utilized via the Bloodhound Red Team module for vulnerability discovery. |
| **Contextual Search** | `chromadb` | Local vector database used to construct Retrieval-Augmented Generation (RAG) indices for cross-file code intelligence. |
| **Version Control** | `GitPython` | Interacts with the local file system and GitHub remote repos for cloning and patching. |

---

## 2. Directory Structure

This structure represents the active, functional core of Farm-Agent.

```text
farm_agent/
├── __init__.py          # Version = "3.0.0"
├── agents/              # Core Agent abstractions
│   └── registry.py      # DeerFlow agent system / templates
├── analysis/            # Code discovery and vulnerability hunting
│   ├── analyzer.py      # Static code analysis strategies
│   └── mapper.py        # Code tree parsing and structural mapping
├── cli/                 # User interfaces
│   └── main.py          # Command definitions: hunt, run, patrol, target, etc.
├── core/                # System utilities, interfaces, and configs
│   ├── config.py        # Pydantic-based system configurations
│   ├── daily_log.py     # Logging structures
│   ├── exceptions.py    # Custom domain exceptions (e.g. LLMRateLimitError)
│   ├── leaderboard.py   # PR statistics and tracking
│   ├── logger.py        # System logging handlers
│   ├── middleware.py    # Quota and filter enforcement logic
│   ├── models.py        # Pydantic core data models
│   ├── notifier.py      # Messaging integration (e.g., Telegram)
│   ├── profiles.py      # Target configuration profiles
│   ├── quotas.py        # Rate limit and operations tracking
│   ├── rag.py           # ChromaDB integration for contextual fixes
│   ├── retry.py         # Resiliency wrappers for APIs and LLMs
│   └── sandbox.py       # Docker execution environment management
├── generator/           # Patch generation and evaluation
│   ├── engine.py        # Main LLM code generation loop
│   ├── reviewer.py      # Self-critique engine
│   └── scorer.py        # Quality evaluation logic
├── github/              # External provider integrations
│   ├── client.py        # Async REST / GraphQL client wrapper
│   ├── discovery.py     # Discovery of target repositories
│   ├── guidelines.py    # Parses CONTRIBUTING.md for specific repo rules
│   └── security_gate.py # Scans meta-files to avoid private disclosure programs
├── issues/              # Issue triage and solver logic
│   └── solver.py        # Evaluates, scores, and attempts to fix existing issues
├── llm/                 # Generative AI adapters
│   ├── agents.py        # Orchestration layer for LLM roles
│   ├── context.py       # Manages prompt contexts
│   ├── models.py        # Available LLM capabilities and cost structures
│   ├── provider.py      # Provider factories (Minimax, OpenRouter, etc.)
│   └── router.py        # Task-specific LLM routing (e.g., code vs. analysis tasks)
├── notifications/       # Post-execution alerting
│   └── notifier.py      # Integrations for Discord, Slack, Telegram
├── orchestrator/        # Core business execution pipelines
│   ├── human.py         # Top-level autonomous supervisor routines
│   ├── memory.py        # Main persistent storage interface (SQLite schemas)
│   └── pipeline.py      # The primary 'ContribPipeline' execution flow
├── plugins/             # Extensibility framework
│   └── __init__.py
├── pr/                  # Pull request lifecycle management
│   ├── janitor.py.DISABLED # Disabled PR cleanup routines
│   ├── manager.py       # Forking, branching, committing, and pushing logic
│   └── patrol.py        # Post-PR feedback monitoring and auto-fixing
├── templates/           # Reusable structures
│   ├── builtin/         # Builtin code templates
│   └── registry.py      # Template loading system
└── tools/               # Internal action tools
    └── protocol.py      # Defined action capabilities
```

---

## 3. Core Module Dependency Graph

The execution flow relies on central orchestration managing interactions with discrete subsystems (GitHub APIs, LLMs, and local Sandbox environments).

```mermaid
graph TD
    CLI[CLI: main.py] --> Config[config.yaml / .env]
    CLI --> Pipeline[ContribPipeline (orchestrator/pipeline.py)]
    CLI --> Patrol[PR Patrol (pr/patrol.py)]

    Pipeline --> Discovery[Repo Discovery (github/discovery.py)]
    Pipeline --> Security[Security Gate (github/security_gate.py)]
    Pipeline --> Memory[(SQLite DB: memory.py)]

    Pipeline --> Analyzer[Code Analyzer (analysis/analyzer.py)]
    Analyzer --> RAG[ChromaDB RAG (core/rag.py)]

    Pipeline --> Generator[Generation Engine (generator/engine.py)]
    Generator --> LLM[LLM Provider (llm/provider.py)]
    Generator --> Scorer[QA Scorer (generator/scorer.py)]

    Pipeline --> Sandbox[Polyglot Sandbox (core/sandbox.py)]
    Sandbox --> Docker[(Docker Daemon)]

    Pipeline --> PRManager[PR Manager (pr/manager.py)]
    PRManager --> GitHubAPI[GitHub Client (github/client.py)]
```

---

## 4. Core Execution Loop (Terminator Loop)

The operational backbone of the v3.0+ architecture is a relentless, 24/7 autonomous process (the "Terminator Execution Loop") heavily regulated by the **Anti-Farming Filter** and **Sandbox Guillotine**. The standard pipeline executes as follows:

1. **Discovery & Validation (`github/discovery.py` & `orchestrator/pipeline.py`):**
   - The CLI initiates `farm_agent run` or `farm_agent hunt-circular`.
   - Repositories are fetched. The **Security Gate** scans `SECURITY.md` for private disclosure rules; if found, execution aborts to prevent policy violations.
   - The agent checks its local database for quota breaches or blacklisted repositories.

2. **Analysis (`analysis/analyzer.py`):**
   - The codebase is cloned locally.
   - The **Bloodhound Red Team** runs static analysis via `ast-grep` and Semgrep to discover vulnerabilities.
   - Local codebase files are indexed into **ChromaDB** (`core/rag.py`) to provide contextual search capabilities for cross-file references.

3. **Generation & DEV-QA Loop (`generator/engine.py`):**
   - The code is routed to the appropriate LLM via `llm/router.py`.
   - Code changes are generated and immediately evaluated by the `QAHardcoreScorer`.
   - The **Anti-Farming Filter** forcefully drops any findings deemed TRIVIAL (e.g., spelling fixes, formatting).

4. **Sandbox Validation (`core/sandbox.py`):**
   - Generated code patches are executed inside an ephemeral, network-isolated Docker container (`sandbox_isolated`).
   - Relevant linters, compilers, and test suites are executed.
   - If a failure occurs, the engine initiates an autonomous self-correction loop up to 3 times. If validation consistently fails, the PR is abandoned.

5. **PR Generation (`pr/manager.py`):**
   - The verified local clone changes are committed to a fresh branch on a fork of the target repo.
   - The PR is opened via the GitHub API, and metadata is saved to the SQLite `memory.db` (`submitted_prs` table).

---

## 5. Database Schema (State Management)

The `Memory` class (`farm_agent/orchestrator/memory.py`) utilizes asynchronous SQLite to maintain operational state. Important tables include:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `analyzed_repos` | Tracks repositories that have already been evaluated to avoid duplicate work. | `full_name`, `language`, `analyzed_at`, `status` |
| `submitted_prs` | Historical log of every PR created by the agent. Monitored by the `PR Patrol`. | `id`, `repo`, `pr_number`, `pr_url`, `status`, `type` |
| `findings_cache` | Stores static analysis discoveries locally. | `id`, `repo`, `file_path`, `type`, `severity` |
| `target_repos` | A queue of high-value targets (acquired manually or algorithmically) waiting for the Terminator Loop to process. | `repo_url`, `status`, `scanned_at` |
| `repo_style_guides`| Caches parsed contributing rules and PR templates to enforce repository-specific standards on generated patches. | `repo`, `style_summary`, `contributing_md` |
| `api_usage_log` | Sliding-window transaction log used to dynamically throttle LLM usage to respect API provider limits (e.g., Minimax 5-hour/7-day windows). | `id`, `timestamp`, `provider` |
| `blacklisted_repos`| Repositories where the agent detected hostility or explicit "no AI" policies. | `repo`, `reason`, `pr_number` |
| `pr_outcomes` | Metrics tracking PR merge/close ratios used by the leaderboard. | `id`, `repo`, `outcome` |
