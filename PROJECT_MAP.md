# Agent-Farm (v4.0.0) — Architecture Blueprint

This document serves as the deep-dive architectural guide for the Agent-Farm system. It details the underlying technologies, directory structure, module dependencies, core execution loops, and database schema that power the autonomous open-source contribution pipeline.

---

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous pipeline built primarily in Python, leveraging local sandboxing, advanced LLM orchestration, and deep static/semantic analysis to safely and effectively contribute to open-source projects.

| Component | Technology | Role in System |
| :--- | :--- | :--- |
| **Core Runtime** | Python (>= 3.11) | Primary application logic, orchestration, and scripting. Built with `hatchling`. |
| **CLI Framework** | `click`, `rich` | Provides a robust, terminal-based user interface and command routing (e.g. `farm_agent superhuman`). |
| **Data Validation & Config** | `pydantic` (v2), `pydantic-settings`, `pyyaml` | Defines core data models (e.g., `Contribution`, `Finding`) and loads configuration from `config.yaml` and `.env`. |
| **State Persistence** | SQLite (`aiosqlite`) | Asynchronous, persistent database (`memory.db`) storing analyzed targets, PR outcomes, findings cache, and the knowledge base. |
| **Container Sandboxing** | Docker Engine API (`docker`) | Provisions locked-down isolated environments for Dynamic Bug Verification (PoC execution) and Blast Radius Auditing (regression testing). |
| **Context & Vector DB** | ChromaDB (`chromadb`) | Powers the Omniscient Context Engine by storing semantic chunks of project documentation (H1/H2/H3 chunked markdown). |
| **LLM Orchestration** | OpenRouter, OpenAI, Anthropic, Google GenAI | Multi-provider LLM integration routing. Utilizes specific models (e.g., `deepseek-v4-pro`, `qwen3.7-max`, `gemini-3.5-flash`) for tailored layers of analysis and generation. |
| **Source Control & Git** | `gitpython`, `httpx` | Handles local Git operations, repo forking, branching, committing, and GitHub REST/GraphQL API interactions. |
| **Job Scheduling** | `apscheduler` | Manages recurrent background tasks in the continuous execution loops. |

---

## 2. Directory Structure

The core package relies on a structured, modular design. Files disabled or removed (e.g., `.DISABLED` extensions) are excluded.

```text
.
├── docker-compose.yml           # Multi-container orchestration (agent-farm service, internet/isolated networks)
├── Dockerfile                   # Docker image definition for the agent runtime
├── pyproject.toml               # Python project configuration (dependencies, hatchling build)
├── requirements.txt             # Bare minimum requirements definition
├── start.sh / start.bat         # 1-Click Docker Desktop Quick-Start wrappers
├── farm_agent/                  # Main Python package
│   ├── __init__.py
│   ├── cli/
│   │   └── main.py              # Click command groups (run, hunt, superhuman, patrol, etc.)
│   ├── core/                    # Fundamental application logic and models
│   │   ├── config.py            # Pydantic configuration loader
│   │   ├── daily_log.py         # Formats daily execution activity logs
│   │   ├── exceptions.py        # System-wide custom exceptions
│   │   ├── leaderboard.py       # Metrics and success rate calculations
│   │   ├── logger.py            # Global logging configuration
│   │   ├── middleware.py        # Core processing chain logic
│   │   ├── models.py            # Pydantic schema definitions for system data
│   │   ├── notifier.py          # Push notification handlers (Telegram, Slack, Discord)
│   │   ├── profiles.py          # Pre-configured execution run profiles
│   │   ├── quotas.py            # API token quota and usage tracking
│   │   ├── rag.py               # ChromaDB semantic chunking and retrieval logic
│   │   ├── retry.py             # Resilient async retries for API endpoints
│   │   └── sandbox.py           # Docker isolated PoC execution and testing
│   ├── analysis/                # Code intelligence and scanning
│   │   ├── analyzer.py          # Bloodhound Red Team code scanning via AST/Semgrep
│   │   └── mapper.py            # AST-based dependency graphing and module linkage
│   ├── generator/               # AI generation engines
│   │   ├── engine.py            # Core contribution code generation
│   │   ├── poc.py               # Proof-of-Concept payload script generation
│   │   ├── reviewer.py          # Self-reflective auditing and blast-radius checks
│   │   └── scorer.py            # Multi-layer QA and evaluation logic
│   ├── github/                  # External integrations
│   │   ├── client.py            # Async GitHub API (REST & GraphQL) interaction
│   │   ├── discovery.py         # Network crawler for new target repositories
│   │   ├── guidelines.py        # Project documentation and PR template extractor
│   │   └── security_gate.py     # Identification of private disclosure channels
│   ├── issues/                  # Issue resolution specialization
│   │   └── solver.py            # Deep planner for resolving open GitHub issues
│   ├── llm/                     # Language model configuration
│   │   ├── agents.py            # Prompts and agent personalities
│   │   ├── context.py           # Context assembly for LLM prompts
│   │   ├── models.py            # Definitions of capabilities (cost, speed, tier)
│   │   ├── provider.py          # Interface for multi-API generation
│   │   └── router.py            # Task assignment routing based on model capabilities
│   ├── notifications/           # Alert systems integration
│   │   └── notifier.py          # Extended notification dispatch logic
│   ├── orchestrator/            # High-level control flow
│   │   ├── human.py             # Terminator Mode / Superhuman loop scheduler
│   │   ├── memory.py            # SQLite database interactions and persistent state
│   │   └── pipeline.py          # Main execution sequence (Discover -> Analyze -> Generate -> PR)
│   ├── plugins/                 # Extensible plugin framework
│   ├── pr/                      # Pull Request lifecycle management
│   │   ├── manager.py           # Git ops: branching, committing, pushing, PR creation
│   │   └── patrol.py            # PR Patrol: CI auto-fixing and maintainer comment handling
│   ├── templates/               # Generation and prompt templates
│   │   └── registry.py          # Template registration
│   └── tools/                   # Utility scripts
│       └── protocol.py          # Standard protocol definitions
└── tests/                       # Pytest test suite definitions
```

---

## 3. Core Module Dependency Graph

The primary data flow relies on the orchestrator tying together analysis, generation, and PR management.

```mermaid
flowchart TD
    CLI[CLI Entry Point \n(farm_agent/cli/main.py)] --> Config[Configuration & State\n(farm_agent/core/config.py,\nfarm_agent/orchestrator/memory.py)]
    CLI --> Orchestrator[Pipeline Orchestrator\n(farm_agent/orchestrator/pipeline.py)]
    CLI --> HumanLoop[SuperHumanLoop\n(farm_agent/orchestrator/human.py)]

    HumanLoop --> Orchestrator
    HumanLoop --> Patrol[PR Patrol\n(farm_agent/pr/patrol.py)]

    Orchestrator --> Discovery[GitHub Discovery\n(farm_agent/github/discovery.py)]
    Discovery --> GitHubClient[GitHub API Client\n(farm_agent/github/client.py)]

    Orchestrator --> Analysis[Omniscient Context Engine\n(farm_agent/analysis/analyzer.py)]
    Analysis --> Mapper[AST Graph Mapper\n(farm_agent/analysis/mapper.py)]
    Analysis --> RAG[RAG & ChromaDB\n(farm_agent/core/rag.py)]

    Orchestrator --> Generator[Contribution Generator\n(farm_agent/generator/engine.py)]
    Generator --> LLM[LLM Router\n(farm_agent/llm/router.py)]
    Generator --> POC[Dynamic Bug Verification\n(farm_agent/generator/poc.py)]
    Generator --> QA[Anti-Farming & Blast Radius QA\n(farm_agent/generator/reviewer.py)]
    POC --> Sandbox[Docker Sandbox Execution\n(farm_agent/core/sandbox.py)]
    QA --> Sandbox

    Orchestrator --> PRManager[PR Submission\n(farm_agent/pr/manager.py)]
    PRManager --> GitHubClient
    Patrol --> PRManager
    Patrol --> Sandbox
```

---

## 4. Core Execution Loops / Entry Points

The pipeline follows distinct paths based on the selected mode:

### 1. The Standard Pipeline (`farm_agent run` / `farm_agent target`)
Implemented in `farm_agent/orchestrator/pipeline.py`.
1. **Target Identification:** `DiscoveryCriteria` identifies suitable repositories (or uses a direct URL).
2. **Context Engine Initialization:** Discovers subsystem docs via `guidelines.py` and semantic chunks via `rag.py`. AST mapping extracts local module dependencies via `mapper.py`.
3. **Analysis & Triage:** The `BloodhoundAnalyzer` identifies potential vulnerabilities. These are piped through the **Anti-Farming Filter** (Qwen Layer 1 Appraisal and Gemini Layer 2 Supreme Audit) to block trivial PRs.
4. **DEV-QA Bounty Loop:**
   - Generates a PoC (`poc.py`) to trigger the vulnerability.
   - Executes PoC inside `DockerSandbox`.
   - Generates the patch.
   - Re-runs the PoC and runs native tests (Blast Radius Auditing) inside the Sandbox to ensure regression-free fixes.
5. **PR Submission:** Creates a fork, commits, pushes, and creates the PR (or sends a private notification for security patches).

### 2. Terminator Mode (`farm_agent superhuman`)
Implemented in `farm_agent/orchestrator/human.py`.
A relentless continuous loop.
- Operates 24/7 without artificial delays.
- Pulls targets deterministically from the `target_repos` DB table.
- Interleaves continuous pipeline generation with **PR Patrol** (reviewing comments and fixing CI issues dynamically).

### 3. Issue Solver (`farm_agent solve`)
Implemented in `farm_agent/issues/solver.py`.
Bypasses the discovery phase, directly ingesting a specified GitHub Issue, mapping the necessary files, and jumping straight to the DEV-QA loop to provide a fix.

---

## 5. Database/State Schema

The persistence layer uses a local SQLite database (`memory.db`) managed via `aiosqlite`. It employs WAL mode for concurrency.

### Core Tables

* **`analyzed_repos`**: Prevents redundant scans.
  * `full_name` (PK), `language`, `stars`, `analyzed_at`, `findings`, `metadata`.
* **`submitted_prs`**: Tracks active contributions and limits bot iteration loops.
  * `id` (PK), `repo`, `pr_number`, `pr_url`, `title`, `type`, `status`, `branch`, `fork`, `created_at`, `updated_at`, `ci_fix_attempts`, `discussion_replies`. *(Unique: `repo`, `pr_number`)*.
* **`target_repos`**: The circular queue for Hunt/Terminator Modes.
  * `repo_url` (PK), `status`, `scanned_at`, `language`, `bounty_amount`, `diamond_target`.
* **`pr_outcomes`**: ML feedback loop based on success/failure to adapt behavior.
  * `id` (PK), `repo`, `pr_number`, `pr_url`, `pr_type`, `outcome`, `feedback`, `time_to_close_hours`, `recorded_at`.
* **`findings_cache`**: Temporary storage for identified vulnerabilities awaiting processing.
  * `id` (PK), `repo`, `type`, `severity`, `title`, `file_path`, `status`, `created_at`.
* **`knowledge_base`**: Architectural context and past lessons learned.
  * `repo_name`, `entry_type`, `content`, `created_at`.
* **`blacklisted_repos`**: Explicit blocklist to avoid hostile maintainers or projects where the agent repeatedly fails.
  * `repo` (PK), `reason`, `pr_number`, `blacklisted_at`.
* **`run_log`**: Historical performance tracking.
  * `id` (PK), `started_at`, `finished_at`, `repos_analyzed`, `prs_created`, `findings`, `errors`, `metadata`.

*(All schema models are mapped to the Pydantic models defined in `farm_agent/core/models.py`)*