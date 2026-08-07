# 🗺️ Agent-Farm (v4.0.0) Architecture Blueprint

This document serves as a deep-dive architectural guide for understanding the internal mechanics of Agent-Farm. It reflects the active, production state of the codebase.

---

## 1. System Overview & Tech Stack

Agent-Farm is built on a robust Python asynchronous foundation, leveraging Docker for execution isolation and SQLite for persistent memory.

| Component | Technology / Library | Role |
| :--- | :--- | :--- |
| **Runtime Engine** | `Python >= 3.11` | Core execution and asynchronous flow (`asyncio`). |
| **Packaging & Build** | `Hatchling` (`pyproject.toml`) | Modern, extensible Python build backend. |
| **Execution Sandbox** | `Docker` (Python SDK `docker>=7.1`) | Provisions `sandbox_isolated` containers for executing PoCs and native unit tests (`pytest`, `npm test`) dynamically. |
| **Persistent Memory** | `SQLite` (`aiosqlite`) | Maintains `memory.db` to track analyzed repos, submitted PRs, outcomes, quotas, target repos, and cached findings. |
| **Omniscient Context** | `ChromaDB` | Vector store powering Retrieval-Augmented Generation (RAG) for mapping codebase structures and documentation. |
| **LLM Routing** | `OpenRouter`, `Minimax` APIs | Intelligent query routing (e.g., DeepSeek for generation, Qwen for appraisal, Gemini for auditing). |
| **Code Validation** | `Semgrep` | Static Application Security Testing (SAST) and AST-grep radar used in the Bloodhound Red Team pipeline. |
| **CLI Framework** | `Click` & `Rich` | Drives the `farm_agent` terminal interface, logs, and formatted outputs. |
| **Linting & Formatting** | `Ruff` | Strict code style enforcement (100-character line limit) across the CI pipeline. |

---

## 2. Directory Structure

The project follows a modular layout designed to separate orchestration, core services, domain logic (GitHub/PRs), and AI generation.

```text
Agent-Farm/
├── farm_agent/                     # Core application package
│   ├── agents/                     # Agent registry and definitions
│   │   └── registry.py             # Agent role configurations
│   ├── analysis/                   # Codebase intelligence and AST mapping
│   │   ├── analyzer.py             # CodeAnalyzer for context extraction
│   │   └── mapper.py               # AST-based dependency graphing
│   ├── cli/                        # Command Line Interface
│   │   └── main.py                 # Core CLI commands (run, superhuman, patrol, etc.)
│   ├── core/                       # Shared foundational services
│   │   ├── config.py               # Pydantic configuration and env loading
│   │   ├── logger.py               # Standardized application logging
│   │   ├── sandbox.py              # Docker container provisioning & execution logic
│   │   └── exceptions.py           # Custom system exceptions (e.g., rate limits)
│   ├── generator/                  # AI patch and payload generation
│   │   ├── engine.py               # ContributionGenerator (patch application logic)
│   │   ├── poc.py                  # Proof-of-Concept script generation
│   │   └── reviewer.py             # Self-review logic
│   ├── github/                     # GitHub integration and API wrappers
│   │   ├── client.py               # Asynchronous API wrapper with token rotation
│   │   └── discovery.py            # Repo crawling and classification
│   ├── issues/                     # Issue-First Pipeline logic
│   │   └── solver.py               # Deep multi-file issue solving and planning
│   ├── llm/                        # Large Language Model integrations
│   │   ├── models.py               # Provider models and fallback configurations
│   │   ├── provider.py             # Provider clients (Minimax, OpenAI/OpenRouter)
│   │   └── router.py               # Task routing rules (Qwen/DeepSeek/Gemini)
│   ├── notifications/              # Alerting systems
│   │   └── notifier.py             # Telegram, Slack, and Discord integrations
│   ├── orchestrator/               # Core execution loops
│   │   ├── memory.py               # SQLite state management and quota tracking
│   │   └── pipeline.py             # Main FarmAgentPipeline (Target discovery to PR creation)
│   ├── plugins/                    # Extensible plugin system
│   ├── pr/                         # Pull Request management
│   │   ├── manager.py              # Submitting and formatting Pull Requests
│   │   └── patrol.py               # PR monitoring, CI log parsing, and auto-healing
│   ├── templates/                  # Standardized patch/PR templates
│   │   ├── registry.py             # Template loading and management
│   │   └── builtin/                # Pre-defined YAML patterns
│   └── tools/                      # Tool protocol definitions
├── tests/                          # Automated Pytest suite
│   ├── unit/                       # Unit tests for components
│   └── integration/                # Full pipeline and API integration tests
├── scripts/                        # Utility scripts
├── Dockerfile                      # Multi-stage image build for production
├── docker-compose.yml              # Defines network isolation (`sandbox_isolated`) and daemon
├── Makefile                        # Dev commands (`make install`, `make test`, `make lint`)
├── pyproject.toml                  # Hatchling build config and dependency versions
├── requirements.txt                # Production dependency locking
├── .env.example                    # Environment variable template
├── start.sh                        # Unix 1-click launch script
└── start.bat                       # Windows 1-click launch script
```
*(Note: Excludes trivial configurations like `.gitignore` and deactivated files like `janitor.py.DISABLED`.)*

---

## 3. Core Module Dependency Graph

The execution pipeline flows linearly from target discovery through LLM generation, into sandboxed verification, and finally PR submission.

```mermaid
graph TD
    %% Main Entry Points
    CLI[CLI (cli/main.py)] --> Pipeline[FarmAgentPipeline (orchestrator/pipeline.py)]
    CLI --> PRPatrol[PR Patrol (pr/patrol.py)]

    %% Orchestrator Core Dependencies
    Pipeline --> Memory[(SQLite Memory (memory.py))]
    Pipeline --> GitHubClient[GitHubClient (github/client.py)]
    Pipeline --> Analyzer[CodeAnalyzer (analysis/analyzer.py)]
    Pipeline --> Solver[Issue Solver (issues/solver.py)]
    Pipeline --> Generator[ContributionGenerator (generator/engine.py)]
    Pipeline --> PRManager[PRManager (pr/manager.py)]

    %% Sandbox and Verification Flow
    Generator --> Sandbox[Docker Sandbox (core/sandbox.py)]
    Sandbox --> PoC[PoC Execution (generator/poc.py)]
    Sandbox --> Tests[Native Test Suite Execution]

    %% LLM Routing
    Generator --> LLMRouter[TaskRouter (llm/router.py)]
    Analyzer --> LLMRouter
    Solver --> LLMRouter
    LLMRouter --> API[OpenRouter/Minimax APIs]
```

---

## 4. Core Execution Loops / Entry Points

### 4.1. Terminator Mode (`superhuman`)
The relentless continuous execution loop invoked via `farm_agent superhuman`.
1. **Target Fetching:** Pulls a pending repository from the `target_repos` SQLite table.
2. **Analysis:** The `CodeAnalyzer` maps the codebase and identifies existing issues.
3. **Execution:** Triggers the pipeline to generate patches (via `issues/solver.py` or the `Bloodhound` radar) and submits them.
4. **Patrol:** In parallel, executes `PR Patrol` to check the status of previously submitted PRs.
5. **Loop:** Loops indefinitely without artificial delays, sleeping only when rate limits or quotas are hit.

### 4.2. Bloodhound Red Team Pipeline
The active vulnerability discovery flow.
1. **Radar:** Uses `Semgrep` (with AST-grep) to rapidly scan cloned code for standard vulnerability signatures.
2. **White-Hat Audit (LLM):** Suspect matches are fed into the LLM (often routed through OpenRouter) for contextual validation.
3. **Appraisal & Audit:** Findings pass through Qwen (Layer 1 Appraisal) and Gemini (Layer 2 Supreme Audit) to filter false positives (the Anti-Farming Filter).
4. **Patch Generation:** A validated finding is passed to the `ContributionGenerator`.

### 4.3. DEV-QA Bounty Loop (Sandbox Execution)
Before any PR is created, the system must guarantee the patch works.
1. **PoC Creation:** `poc.py` generates a script designed to trigger the identified bug.
2. **First Pass (Efficacy):** The sandbox spins up, applies the fix, and runs the PoC. If the bug is still present, the fix is rejected and fed back to the LLM for correction.
3. **Second Pass (Regression):** If the PoC passes, the sandbox runs the native repository tests (e.g., `make test`, `npm test`). If tests fail, the fix is rejected to prevent breaking downstream code.
4. **Commit:** Only fixes that pass both checks are pushed to GitHub.

---

## 5. Database & State Schema

Agent-Farm leverages an `aiosqlite` connection to `memory.db` to maintain state across restarts and enforce API quotas safely.

| Table Name | Description / Role |
| :--- | :--- |
| `analyzed_repos` | Tracks repositories that have been fully scanned to prevent redundant parsing and unnecessary API calls. |
| `submitted_prs` | Logs all created pull requests, including status (`merged`, `closed`, `open`) and type (`security`, `refactor`). |
| `pr_outcomes` | Detailed historical log of PR merge rates, used for maintainer vibe analysis and calculating success metrics. |
| `target_repos` | The queue for Terminator mode. Includes target URLs, assigned languages, bounty thresholds, and current processing status. |
| `findings_cache` | Temporarily stores raw vulnerabilities/issues identified by the LLM or Bloodhound before they are validated and processed. |
| `api_usage_log` | Time-series data tracking LLM token consumption and request rates. Prevents the system from breaching rate limits (e.g., OpenRouter quotas). |
| `repo_style_guides` | Stores summaries of specific repo rules (e.g., `CONTRIBUTING.md` guidelines) to ensure generated PRs match maintainer expectations. |
| `blacklisted_repos` | Repositories that have opted out, failed consistently, or are deemed low value. These are permanently skipped by the pipeline. |
| `task_schedule` | Persistent timestamps for periodic tasks (like DB cleanup or quota resets) enabling safe, multi-process coordination. |
