# 🗺️ Agent-Farm Project Map & Architecture

This document serves as a deep-dive architectural guide for Agent-Farm. It details the system components, data flow, active technologies, and directory structure.

---

## 1. System Overview & Tech Stack

Agent-Farm is built on a highly concurrent, isolated, and fault-tolerant architecture.

| Technology | Role / Usage in Codebase |
|------------|---------------------------|
| **Python 3.11+** | Core runtime environment. |
| **Hatchling** | Build system backend (`pyproject.toml`). |
| **Pydantic (v2) & Pydantic-Settings** | Configuration management (`farm_agent/core/config.py`) and robust data modeling (`farm_agent/core/models.py`). |
| **Click** | CLI framework (`farm_agent/cli/main.py`). |
| **httpx** | Async HTTP client for interacting with GitHub REST/GraphQL APIs and LLM providers. |
| **aiosqlite** | Async SQLite interface for persistent state management (`farm_agent/orchestrator/memory.py`). |
| **ChromaDB** | Vector database for the RAG-based Omniscient Context Engine (`farm_agent/core/rag.py`). |
| **Docker** | Execution of isolated validation environments (sandboxes) for PoCs and unit tests (`farm_agent/core/sandbox.py`). |
| **AST (Abstract Syntax Trees)** | Code parsing for Python, with regex fallbacks for other languages to build dependency graphs (`farm_agent/analysis/mapper.py`). |
| **Rich** | Terminal formatting, progress tracking, and tables in the CLI. |

---

## 2. Directory Structure

This structure represents the actual active modules inside `farm_agent/`. *(Note: Disabled files and trivial artifacts are excluded.)*

```text
farm_agent/
├── __init__.py
├── agents/                 # Registry-based agent configurations (DeerFlow pattern)
│   └── registry.py
├── analysis/               # Code scanning and dependency mapping
│   ├── analyzer.py         # Parallelized security, quality, and UX scanners
│   └── mapper.py           # AST and regex-based module dependency grapher
├── cli/                    # Command-line interface
│   └── main.py             # Click CLI definitions (run, target, superhuman, patrol, etc.)
├── core/                   # Shared system utilities and infrastructure
│   ├── config.py           # Pydantic configuration loading
│   ├── exceptions.py       # Custom exception hierarchy
│   ├── leaderboard.py      # Contribution statistics tracker
│   ├── logger.py           # Daily rotating file logger
│   ├── middleware.py       # Context middleware chains
│   ├── models.py           # Core Pydantic data models
│   ├── notifier.py         # Telegram/Slack/Discord alerting
│   ├── profiles.py         # Execution profile setups (thorough, quick, etc.)
│   ├── quotas.py           # API token rotation and quota limits
│   ├── rag.py              # ChromaDB vector embedding and context loader
│   ├── retry.py            # Async retry wrappers for flaky APIs
│   └── sandbox.py          # Docker-isolated validation execution
├── generator/              # LLM logic for building fixes and verifying them
│   ├── engine.py           # Contribution patch generation
│   ├── poc.py              # Proof-of-concept exploit/trigger generation
│   ├── reviewer.py         # Blast-radius validation & auto-correction loops
│   └── scorer.py           # Qwen-based rigorous QA evaluator
├── github/                 # API integrations and crawlers
│   ├── client.py           # Core GitHub wrapper (REST + GraphQL)
│   ├── discovery.py        # Repository crawler
│   ├── guidelines.py       # Extracting project rules (CONTRIBUTING.md)
│   └── security_gate.py    # Checks for private disclosure requirements
├── issues/                 # Issue-first operational mode
│   └── solver.py           # Multi-file reasoning to resolve open GitHub issues
├── llm/                    # Language model orchestration
│   ├── agents.py           # System prompts
│   ├── context.py          # Context collation
│   ├── models.py           # Model definitions (deepseek-v4-pro, qwen3.7-max, etc.)
│   ├── provider.py         # Unified OpenRouter interface
│   └── router.py           # Task-to-Model router map
├── notifications/          # Alert integration modules
│   └── notifier.py
├── orchestrator/           # High-level control loops
│   ├── human.py            # SuperHumanLoop (Terminator mode: 24/7 patrol & hunt)
│   ├── memory.py           # SQLite persistence layer (WAL mode)
│   └── pipeline.py         # Standard and Circular task coordination
├── plugins/                # Plugin system
├── pr/                     # Pull Request lifecycle
│   ├── manager.py          # Branching, committing, and PR creation
│   └── patrol.py           # AI-driven PR comment handling and CI fixing
├── templates/              # Hardcoded contribution fallback patterns
│   └── registry.py
└── tools/                  # LLM functional tools
    └── protocol.py
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent run/superhuman)] --> ORCH[Orchestrator Pipeline]
    ORCH --> MEM[(SQLite Memory)]
    ORCH --> GHC[GitHub Client]

    ORCH --> DISC[Discovery / Crawler]
    DISC --> GHC

    ORCH --> RAG[Omniscient Context Engine]
    RAG --> MAP[Repo Mapper (AST/Regex)]
    RAG --> CHR[(ChromaDB)]

    ORCH --> ANA[Analysis Module]
    ANA --> |Gate 1: Qwen| LLM[LLM Router]

    ORCH --> GEN[Generator Engine]
    GEN --> POC[PoC Generator]
    POC --> SAND[Docker Sandbox]
    GEN --> |Code Gen: DeepSeek| LLM
    GEN --> REV[Blast Radius Reviewer]
    REV --> SAND

    ORCH --> PRM[PR Manager]
    PRM --> GHC

    ORCH --> PAT[PR Patrol]
    PAT --> |Fixes CI/Answers| LLM
    PAT --> GHC
```

---

## 4. Core Execution Loops & Entry Points

### Standard Pipeline (`farm_agent run` / `farm_agent target`)
1. **Context Initialization**: `FarmAgentPipeline` initializes `GitHubClient` and `Memory`.
2. **Discovery**: Locates target repositories based on config.
3. **Omniscient Context Gathering**: RAG vectorizes documentation; `RepoMapper` parses code into a dependency graph.
4. **Analysis & Gatekeeping**: Analyzers scan for issues. Findings must pass Gate 1 (Qwen Appraisal) and Gate 2 (Real-World Value).
5. **Generation & Sandbox Validation**:
   - `PoCGenerator` writes an exploit script and runs it in `DockerSandbox`.
   - `ContributionGenerator` drafts a fix.
   - `ReviewerAgent` runs the PoC again (Blast Radius Pass 1) and the native test suite (Blast Radius Pass 2).
6. **Submission**: `PRManager` forks, branches, commits, and opens the PR. Records to SQLite.

### Terminator Mode / Super Human Loop (`farm_agent superhuman`)
- Relentless execution. Runs a combination of the `FarmAgentPipeline` (Hunting/Targeting) and `PRPatrol`.
- Manages strict daily PR quotas.
- Automatically handles graceful shutdowns via `SIGINT`/`SIGTERM`.

### Issue Solver (`farm_agent solve`)
- Inverts the flow: Looks for open GitHub issues matching complexity criteria (via `IssueSolver`).
- Uses LLM deep-planning to draft multi-file solutions.

### PR Patrol (`farm_agent patrol`)
- Sweeps database for open PRs created by the agent.
- Analyzes GitHub review comments or CI failures.
- Auto-generates fixes (via isolated Docker runs) and pushes new commits to the existing branch.

---

## 5. Database / State Schema (`memory.db`)

Agent-Farm leverages an SQLite database in WAL (Write-Ahead Logging) mode to maintain state across restarts and concurrent runs.

- **`analyzed_repos`**: Tracks repos already processed. (Columns: `full_name`, `language`, `stars`, `analyzed_at`, `findings`, `metadata`).
- **`submitted_prs`**: Logs bot-created PRs/issues and limits. (Columns: `id`, `repo`, `pr_number`, `pr_url`, `title`, `type`, `status`, `ci_fix_attempts`, `discussion_replies`).
- **`findings_cache`**: Temporary cache of detected code flaws. (Columns: `id`, `repo`, `type`, `severity`, `title`, `file_path`, `status`).
- **`run_log`**: Historical metrics of pipeline runs.
- **`pr_outcomes`**: Tracks merged/closed states and time-to-close metrics for machine-learning style adaptation.
- **`repo_preferences`**: Learned preferences for specific projects (e.g. rejection tendencies).
- **`blacklisted_repos`**: Projects permanently ignored due to hostile interactions or private disclosures.
- **`api_usage_log`**: Usage tracker for OpenRouter quota limits.
- **`task_schedule`**: Timers for the `SuperHumanLoop`.
- **`knowledge_base`**: Stores architectural context and feedback lessons from previous PR failures.
- **`target_repos`**: A deterministic circular queue for continuous hunting.
- **`repo_style_guides`**: Cached formatting/templating rules extracted from `CONTRIBUTING.md`.
