# PROJECT_MAP.md — Farm-Agent Ground Truth

**Generated:** 2026-04-15
**Version:** v3.0.0
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)
**Language:** Python 3.11+

---

## 1. System Overview & Tech Stack

**What the system actually does:**

Farm-Agent is an autonomous AI agent designed to discover open-source GitHub repositories matching predefined criteria, analyze their code for issues (such as security vulnerabilities, code quality bugs, and performance problems) or open issues, generate patches via LLMs, validate those patches in isolated Docker sandboxes, and create PRs or issues to contribute back.

**Active Tech Stack:**

| Component | Technology | Role / Evidence |
|-----------|------------|-----------------|
| Language | Python 3.11+ | Core implementation language (`requires-python = ">=3.11"` in `pyproject.toml`) |
| HTTP client | `httpx` (async) | Interacting with APIs like GitHub (`httpx>=0.27,<1.0`) |
| LLM Providers | MiniMax, OpenRouter, Gemini, OpenAI, Anthropic, Ollama | Providing AI capabilities (`config.py`, `pyproject.toml`) |
| Database | SQLite via `aiosqlite` | Persistent memory in WAL mode (`memory.py`, default: `data/memory.db`) |
| Docker | `docker>=7.1,<8.0` | Polyglot sandbox validation (`sandbox.py`) |
| Scheduling | `apscheduler>=3.10,<4.0` | Task scheduling |
| Config | Pydantic v2 + YAML | Strongly typed config (`config.py`) |
| CLI | `click>=8.1,<9.0` + `rich>=13.0,<14.0` | Interactive command-line interface (`main.py`) |
| Vector DB | `chromadb>=0.4,<1.0` | Local RAG indexing for precise fixes (`rag.py`) |
| Git Python | `gitpython>=3.1,<4.0` | Git operations |
| Build System | Hatchling | Build backend (`pyproject.toml`) |

---

## 2. Directory Structure

```text
farm_agent/
├── cli/
│   └── main.py          # Click CLI, core entry point for all commands (run, target, hunt, superhuman, etc.)
├── core/
│   ├── config.py        # Pydantic configuration system (FarmAgentConfig)
│   ├── exceptions.py    # Custom exceptions
│   ├── leaderboard.py   # PR stats and repo rankings
│   ├── logger.py        # Logging configuration
│   ├── middleware.py    # Middleware chain (DeerFlow pattern)
│   ├── models.py        # Pydantic data models
│   ├── notifier.py      # Notifications
│   ├── profiles.py      # Contribution profiles
│   ├── quotas.py        # Quota tracking
│   ├── rag.py           # ChromaDB RAG implementation
│   ├── retry.py         # Async retry decorators
│   └── sandbox.py       # DockerSandbox for patch validation
├── generator/
│   ├── engine.py        # Code generation via LLM
│   ├── reviewer.py      # Code reviewer agent
│   └── scorer.py        # QA Hardcore Scorer for DEV-QA loop
├── github/
│   ├── client.py        # GitHub API client (REST & GraphQL)
│   ├── discovery.py     # Repo discovery and target management
│   ├── guidelines.py    # Repo style guide extraction
│   └── security_gate.py # Security Disclosure Gate
├── issues/
│   └── solver.py        # Issue-First Pipeline logic
├── llm/
│   ├── agents.py        # LLM agent definitions
│   ├── models.py        # Supported models and capabilities
│   ├── provider.py      # LLM provider abstractions
│   └── router.py        # Task routing
├── notifications/
│   └── notifier.py      # Notification routing
├── orchestrator/
│   ├── human.py         # SuperHumanLoop (organic 24/7 loop)
│   ├── memory.py        # SQLite persistent memory and schema
│   └── pipeline.py      # ContribPipeline (core pipeline orchestrator)
├── plugins/
│   └── base.py          # Plugin base (if any)
├── pr/
│   ├── janitor.py       # PR cleanup utilities
│   ├── manager.py       # PR creation and management
│   └── patrol.py        # PRPatrol for responding to feedback
├── templates/
│   └── registry.py      # Contribution templates
├── tools/
│   └── protocol.py      # Tool definitions (DeerFlow pattern)
└── __init__.py          # Package initialization
```

---

## 3. Core Module Dependency Graph

Farm-Agent follows the **DeerFlow** architectural pattern, utilizing registry-based agents and middleware.

```mermaid
graph TD
    CLI[CLI (main.py)] --> Pipeline[ContribPipeline (orchestrator/pipeline.py)]
    CLI --> HumanLoop[SuperHumanLoop (orchestrator/human.py)]
    HumanLoop --> Pipeline

    Pipeline --> Discovery[GitHub Discovery]
    Pipeline --> Analyzer[CodeAnalyzer]
    Pipeline --> Solver[IssueSolver]
    Pipeline --> Generator[ContributionGenerator]
    Pipeline --> Sandbox[DockerSandbox]
    Pipeline --> PRManager[PRManager]

    Analyzer --> RAG[ChromaDB RAG]
    Solver --> RAG
    Generator --> Scorer[QAHardcoreScorer]

    Pipeline --> SecurityGate[SecurityGate]
    SecurityGate --> DB[(SQLite Memory)]
    Discovery --> DB
    PRManager --> DB
```

---

## 4. Core Execution Loops / Entry Points

### Single Pipeline Run (e.g., `farm_agent run`)
1. **Discovery:** Discovers candidate repositories via GitHub API based on config criteria.
2. **Gate:** Checks AI policies, interaction limits, maintainer vibes, and the Security Disclosure Gate.
3. **Analysis:** Runs static analysis (Bloodhound, Semgrep) or fetches open issues (Issue-First).
4. **Filtering (Anti-Farming):** Drops trivial findings, prevents docs PRs, and avoids duplicate work.
5. **Engine:** LLMs generate proposed patches or issues.
6. **DEV-QA Bounty Loop:** Scores the generated patch. If rejected, self-corrects based on repo style guides and QA lessons.
7. **Sandbox:** Executes the generated patch inside an isolated Docker container. If it fails, attempts self-correction up to a maximum limit.
8. **PR:** Commits, pushes the branch, and creates the PR via GitHub API.

### Super Human Mode (`farm_agent superhuman`)
- Mimics a human developer.
- Dynamically sets random daily PR quotas.
- Injects unpredictable delays between actions.
- Interleaves Hunt mode with PR Patrol mode.
- Shifts to patrol-only mode once the daily quota is met.

### Circular Target Loop (`farm_agent hunt-circular`)
- Deterministic, crash-safe round-robin processing from a `target_repo.json` list.
- Uses `scanned_at` timestamps managed within the SQLite database to rotate targets.

### PR Patrol (`farm_agent patrol`)
- Scans open PRs created by Farm-Agent.
- Reads maintainer review comments.
- Generates and pushes code fixes, answers questions, or handles CLAs.

---

## 5. Database / State Schema

Farm-Agent relies on an SQLite database (`aiosqlite`) running in Write-Ahead Logging (WAL) mode for persistent, concurrent-safe memory.

### Key Tables

| Table | Purpose |
|-------|---------|
| `analyzed_repos` | Tracks which repositories have been scanned to avoid duplicate work. |
| `submitted_prs` | Records all PRs submitted by the agent, tracking status, CI fixes, and discussion replies. |
| `findings_cache` | Caches analysis findings. |
| `run_log` | Historical log of pipeline runs. |
| `pr_outcomes` | Outcome tracking (merged, closed, rejected) used for future learning. |
| `repo_preferences` | Aggregates preferences per repository based on PR outcomes. |
| `blacklisted_repos` | Repositories permanently blocked due to hostility or configuration. |
| `api_usage_log` | LLM API usage logs to enforce quotas (e.g., Minimax sliding windows). |
| `task_schedule` | Persistent task scheduling (e.g., for garbage collection). |
| `knowledge_base` | QA lessons and audit history. |
| `target_repos` | Status and timestamp tracking for the Circular Target Loop. |
| `repo_style_guides` | Cached parsed `CONTRIBUTING.md` and PR templates for Diplomat Protocol. |

### Schema Management
- Schema initialization runs idempotently, wrapping DDL operations in try-except blocks to ignore 'already exists' errors during schema evolution.
