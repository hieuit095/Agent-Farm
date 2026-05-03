# Farm-Agent Project Architecture Blueprint

This document serves as the canonical architectural guide for the Farm-Agent project, mapping its core functionalities, directories, technology stack, and module dependencies.

## 1. System Overview & Tech Stack

The Farm-Agent project uses a mix of powerful asynchronous orchestration, AI integration, and deterministic systems.

| Component / Layer | Technologies & Libraries | Role |
| :--- | :--- | :--- |
| **Language & Runtime** | Python >= 3.11 | Core runtime environment. |
| **Package Management** | Hatchling | Modern PEP 517 build backend. |
| **CLI Framework** | `click`, `rich` | Building robust, styled terminal interfaces. |
| **HTTP & Networking** | `httpx` | Asynchronous API communications (GitHub REST API). |
| **Database (Memory)** | `aiosqlite` (SQLite) | Persistent local storage for the agent's memory (cache, PR logs, history). |
| **LLM Integrations** | `google-genai`, `openai`, `anthropic`, `ollama` | Interface with LLM providers (Minimax, Gemini, OpenRouter). |
| **Code Orchestration** | `pydantic`, `pydantic-settings`, `PyYAML` | Structured data validation and parsing of the `config.yaml`. |
| **Sandbox Execution** | `docker` SDK | Manages network-isolated containers for executing untrusted patches. |
| **VCS Management** | `gitpython` | Orchestrating git operations (cloning, branching, committing, pushing). |
| **Red Team Tools** | Ast-grep, Semgrep | White-Hat security vulnerability discovery. |

## 2. Directory Structure

Below is an annotated ASCII map showing the current repository layout and what each folder manages:

```
.
├── Dockerfile                  # Builds the core isolated polyglot docker image
├── LICENSE                     # MIT License
├── Makefile                    # Developer aliases for test, ruff check, install
├── PROJECT_MAP.md              # This architecture map file
├── README.md                   # System overview, key features, and run instructions
├── config.example.yaml         # Blueprint for generating `config.yaml` with keys and quotas
├── docker-compose.yml          # Container configuration with dual networks (internet vs sandbox)
├── farm_agent/                 # Main Source Code Package
│   ├── cli/                    # `main.py` entrypoint. Maps commands (run, hunt, superhuman, patrol, etc.)
│   ├── core/                   # Utilities: Config loading, Database models, Sandbox execution (`sandbox.py`)
│   ├── generator/              # Code patching engine (`engine.py`, `scorer.py` for quality grading)
│   ├── github/                 # GitHub API wrapper, Anti-farming Gate, and Discovery search tools
│   ├── issues/                 # Issue processing logic and heuristics (`solver.py`)
│   ├── llm/                    # Router for handling tasks across providers (Minimax, Gemini, OpenRouter)
│   ├── orchestrator/           # Orchestrates the Pipeline (`pipeline.py`), Terminator Loop (`human.py`)
│   ├── pr/                     # Handles Pull Request branching (`manager.py`), Auto-responses (`patrol.py`)
│   └── templates/              # Built-in contribution markdown and structural templates
├── pyproject.toml              # Project metadata, dependencies, entry points, and test/ruff configurations
├── target_repo.json            # Contains specific repositories used by the Circular Target Loop
└── tests/                      # Automated unit tests for concurrent API fetches and system logic
```

## 3. Core Module Dependency Graph

The agent functions via a directed graph mapping CLI invocations down to API and LLM executors.

```mermaid
graph TD;
    CLI[CLI (farm_agent/cli/main.py)] --> Orchestrator[Orchestrator (Pipeline/Human Loop)]
    Orchestrator --> Memory[Memory (SQLite State)]
    Orchestrator --> GH[GitHub Client (API/Discovery/Gate)]
    Orchestrator --> Issues[Issue Solver]
    Orchestrator --> RedTeam[Red Team Analysis (Bloodhound)]
    Issues --> LLMEngine[LLM Generation Engine]
    RedTeam --> LLMEngine
    LLMEngine --> Sandbox[Polyglot Docker Sandbox]
    Sandbox --> PRManager[PR Manager (Branch/Push/CLA)]
    PRManager --> GH
    Orchestrator --> PRPatrol[PR Patrol (Feedback auto-respond)]
    PRPatrol --> LLMEngine
    PRPatrol --> PRManager
```

## 4. Core Execution Loops / Entry Points

The agent operates through various execution models mapped from CLI entry points to internal orchestrators:

- **The Standard Pipeline (`farm_agent run`, `farm_agent target`)**
  1. **Discovery**: Identifies high-value targets via GitHub search algorithms or predefined URLs.
  2. **Security Gate**: Runs anti-farming filters to block trivial projects and checks blacklisted repos.
  3. **Analysis/Issues**: Invokes static tools (Ast-grep, Semgrep) to find weaknesses, or parses existing open GitHub issues.
  4. **Engine Generation**: An LLM (e.g. Minimax or OpenRouter) generates Git merge-diffs to fix the code.
  5. **Sandbox Verification**: Patches are executed within a restricted Docker sandbox to ensure unit tests and syntaxes compile correctly.
  6. **PR Finalization**: The code is committed to a fork, pushed, and opened as a Pull Request via `PRManager`.

- **Terminator Execution Loop (`farm_agent superhuman`)**
  - Runs indefinitely (`SuperHumanLoop`) attempting to maximize the number of PRs submitted to reach daily maximum quotas.
  - Interleaves `hunt` (finding and fixing issues) and `patrol` (addressing PR feedback).
  - Uses no artificial delays or organic wait times.

- **PR Patrol Loop (`farm_agent patrol`)**
  - Scans all historically submitted PRs still "open".
  - Reads maintainer feedback and queries LLMs to categorize comments (e.g., CODE_CHANGE, QUESTION, STYLE_FIX, CLA).
  - Automatically pushes required changes, signs CLAs, or responds directly in thread, then closes the discussion dynamically when limits are reached.

- **Circular Target Loop (`farm_agent hunt-circular`)**
  - Reads a curated JSON file (`target_repo.json`) and sequentially rotates targets by looking at the oldest `scanned_at` timestamp. Processed via `run_circular` in the Orchestrator Pipeline.

## 5. Database/State Schema

The SQLite memory database (`data/memory.db` by default) ensures the agent is stateless across crash restarts and prevents spamming repositories.

| Table Name | Description |
| :--- | :--- |
| `analyzed_repos` | Tracks every repository the agent has scanned, preventing duplicate processing across runs. |
| `submitted_prs` | Logs all Pull Requests created by the agent. Includes current PR status (open, closed, merged) to feed into Alumni Sync and PR Patrol. |
| `findings_cache` | Stores intermediate analysis issues so the pipeline can resume processing without re-scanning code. |
| `run_log` | High-level audit logs containing pipeline statistics per session. |
| `pr_outcomes` | Metrics storing success rates of individual PR components (merge rate computations). |
| `repo_preferences` | Caches maintainer style guides and strict formatting rules discovered from earlier PRs. |
| `blacklisted_repos` | A strict list of repositories the agent is forbidden to touch (failed gates, strict anti-farming). |
| `api_usage_log` | Logs token limits used by Red Team/LLM models to stay under budget. |
| `task_schedule` | Used for async cron-like background jobs. |
| `knowledge_base` | RAG vector embeddings storing learned coding rules (purged after TTL via `janitor`/`gc`). |
