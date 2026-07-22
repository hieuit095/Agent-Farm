# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Generated:** 2026-06-02  
**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence basis:** Direct code inspection. No assumptions. All line numbers are verified.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter (Qwen → Gemini), and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

Version 4.0.0 introduces the **Omniscient Context Engine**, which recursively discovers repository documentation, chunks it semantically by markdown headers, ingests it into ChromaDB, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents. Furthermore, version 4.0.0 incorporates **Dynamic Bug Verification** (generating and executing Proof-of-Concept exploits in an isolated container sandbox, evaluated via LLM) and **Blast Radius & Regression Auditing** (using baseline test suite runs and downstream dependent analysis to guarantee zero regressions).

| Component | Technology | Source |
|-----------|------------|--------|
| Language | Python 3.11+ | `pyproject.toml` |
| HTTP client | `httpx` (async) | `pyproject.toml` |
| Primary LLM | `deepseek/deepseek-v4-flash` via OpenRouter | `config.py:56` |
| Code Gen LLM | `deepseek/deepseek-v4-pro` via OpenRouter | `pipeline.py:395` |
| Layer 1 Appraiser | `qwen/qwen3.7-max` via OpenRouter | `pipeline.py:2790` |
| Layer 2 Supreme Auditor | `google/gemini-3.5-flash` via OpenRouter | `pipeline.py:2851` |
| Red Team (Bloodhound) | `deepseek/deepseek-v4-flash` via OpenRouter | `config.py:109` |
| Semgrep rulesets | `p/security-audit`, `p/cwe-top-25`, `p/default`, `p/golang`, `p/rust`, `p/smart-contracts` | `config.py:114` |
| Database | SQLite (`aiosqlite`) — WAL mode, fallback to DELETE | `memory.py:151` |
| Docker Sandbox | `docker>=7.1` — complete network + capability isolation | `sandbox.py:198` |
| Config | Pydantic v2 + YAML + `.env` | `config.py:222` |
| CLI | `click>=8.1` + `rich>=13.0` | `main.py` |
| Vector DB | `chromadb>=0.4` — RAG for file & documentation context | `core/rag.py` |
| Notifications | Telegram / Slack / Discord | `notifier.py` |

---

## 2. Directory Structure

```text
.
├── Dockerfile                          # Stage 1 builder (wheel creation) + Stage 2 lean runtime v4.0.0
├── docker-compose.yml                  # agent-farm service definition with volumes (data/, logs/, secret_findings/)
├── start.sh                            # Unix quick start wrapper script
├── start.bat                           # Windows quick start wrapper script
├── Makefile                            # Standard tasks for dev setup, testing, formatting
├── README.md                           # Main user-facing documentation
├── PROJECT_MAP.md                      # Architecture blueprint (this file)
├── pyproject.toml                      # Project metadata, dependencies, and tools config
├── requirements.txt                    # Minimal pip dependencies
└── farm_agent/                         # Package root (version = "4.0.0")
    ├── __init__.py
    ├── cli/
    │   └── main.py                     # Click CLI — command registrations
    ├── core/
    │   ├── config.py                   # Pydantic v2 config and YAML loading
    │   ├── daily_log.py                # Formats daily markdown activity logs
    │   ├── exceptions.py               # System exception types hierarchy
    │   ├── leaderboard.py              # Leaderboard stat collections
    │   ├── logger.py                   # Rotating file logging system setup
    │   ├── middleware.py               # Context middleware chain layers
    │   ├── models.py                   # Core Pydantic data structures definitions
    │   ├── notifier.py                 # Telegram/Slack/Discord notifications integration
    │   ├── profiles.py                 # Thorough, quick, and standard run configurations
    │   ├── quotas.py                   # OpenRouter usage quota controllers
    │   ├── rag.py                      # ChromaDB vector DB context loaders
    │   ├── retry.py                    # Retry decorators for GitHub/LLM interfaces
    │   └── sandbox.py                  # DockerSandbox engine for PoC and testing
    ├── analysis/
    │   ├── analyzer.py                 # CodeAnalyzer (security, quality scanners) & BloodhoundAnalyzer
    │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
    ├── generator/
    │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
    │   ├── poc.py                      # PoCGenerator (PoC validation & LLM evaluation)
    │   ├── reviewer.py                 # ReviewerAgent (Self-reflective code auditor)
    │   └── scorer.py                   # QAHardcoreScorer (Qwen-based QA grader)
    ├── github/
    │   ├── client.py                   # Async-retrying GitHub REST and GraphQL Client
    │   ├── discovery.py                # Target network search and crawler discoverers
    │   ├── guidelines.py               # Guidelines, PR templates, and subsystem doc discovery
    │   └── security_gate.py            # Identifies private security disclosure files
    ├── issues/
    │   └── solver.py                   # IssueSolver (solves issues, multi-file deep planner)
    ├── llm/
    │   ├── agents.py                   # LLM agent prompts and routing models
    │   ├── context.py                  # Generator system instruction builders
    │   ├── models.py                   # Model registry definitions
    │   ├── provider.py                 # OpenRouter integration handlers
    │   └── router.py                   # Task router mapping
    ├── notifications/
    │   └── notifier.py                 # Push notification module
    ├── orchestrator/
    │   ├── memory.py                   # Persistence memory sqlite connection interface
    │   ├── pipeline.py                 # Pipeline (Standard & Circular pipelines implementation)
    │   └── human.py                    # SuperHumanLoop relentless daily scheduler
    ├── plugins/                        # Extensibility plugins
    ├── pr/
    │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
    │   └── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
    ├── templates/                      # Formatting templates for PR descriptions
    │   └── registry.py
    ├── tools/
    │   └── protocol.py                 # CLI tool protocols
    └── web/                            # Web components (if any)
```

*(Note: Trivial and disabled files have been omitted from this tree).*

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    A[CLI Entry (main.py)] -->|orchestrates| B(Orchestrator: pipeline.py / human.py)
    B --> C(GitHub Client: client.py)
    B --> D(Code Analyzer: analysis/analyzer.py)
    B --> E(Memory State: memory.py)
    B --> M(RAG Context: core/rag.py)

    C -->|fetches| F[Target Repo Code]
    M -->|reads| F
    D -->|analyzes| F
    D -->|AST graph| G(Repo Mapper: analysis/mapper.py)

    B --> H{Anti-Farming Filter}
    H -->|rejected| I[Drop Finding]
    H -->|approved| J(Generator: generator/engine.py)

    J --> K(PoC Validation: generator/poc.py)
    K <--> L((Docker Sandbox: core/sandbox.py))

    L -->|Pass 1 (Efficacy)| K
    L -->|Pass 2 (Regression)| J

    J --> O(PR Manager: pr/manager.py)
    O --> C

    P(PR Patrol: pr/patrol.py) --> C
    P --> L
```

---

## 4. Core Execution Loops / Entry Points

### 4A. Standard Pipeline (`_process_repo()`)
Processes a single repository through the full contribution pipeline:
1. **Early Clone Initialization:** Clones repository early to local temporary directory.
2. **Baseline Native Test Run:** Runs unpatched native tests once to establish pre-existing failure baseline.
3. **Omniscient Context Discovery:** Recursively discovers and semantically chunks docs, indexing into ChromaDB.
4. **CodeAnalyzer:** Runs parallel LLM analyzers with AST dependency injection.
5. **Anti-Farming Filters (Gates):** Rejects trivial, doc-only, or low-severity findings. Evaluates findings using Layer 1 (Qwen) Expert Appraisal.
6. **Dynamic Bug Verification (Phase 3):** Generates PoC, runs in Sandbox. If it fails to trigger, drops the finding.
7. **Fix Generation:** Drafts code patches using generator engine.
8. **Double-Pass Sandbox Validation (DEV-QA Loop):**
   * **Pass 1:** PoC must NOT trigger the vulnerability.
   * **Pass 2:** Native tests must PASS (Blast Radius & Regression Auditing).
9. **Final Audit & Submit:** Layer 2 (Gemini) audit. Submits PR or writes to private disclosure folder.

### 4B. Terminator Mode (`SuperHumanLoop`)
A relentless 24/7 continuous execution loop without artificial delays.
- Pulls targets exclusively from the SQLite `target_repos` table in a circular pattern (`run_circular()`).
- Alternates with the **PR Patrol** daemon (`PRPatrol.patrol()`) which checks open PRs for maintainer review comments, replies to questions, and auto-fixes CI failures via isolated Docker sandbox execution.

---

## 5. Database/State Schema

The SQLite Database resides in `data/memory.db` and operates in **WAL (Write-Ahead Logging)** mode. It uses composite indices to prevent full table scans.

### Schema Details
* **`analyzed_repos`**: Tracks repositories that have already gone through analysis (PK: `full_name`).
* **`submitted_prs`**: Tracks bot-created PRs, issues, and associated limits counters (PK: `id`). Unique Constraint: `(repo, pr_number)`.
* **`findings_cache`**: Temporary cache of detected code findings.
* **`run_log`**: Log of overall runs metrics and durations.
* **`pr_outcomes`**: Stores merged/closed PR states and maintainer review remarks. Unique Constraint: `(repo, pr_number)`.
* **`repo_preferences`**: Learned project contribution preferences updated dynamically from outcomes.
* **`blacklisted_repos`**: Projects blacklisted due to hostile maintainer checks or failures.
* **`api_usage_log`**: Tracks LLM API usage. Includes indices for efficient cleanup.
* **`task_schedule`**: Persistent schedule queue for tasks in the `SuperHumanLoop`.
* **`knowledge_base`**: Stores lessons, past critiques, self-learning lessons, and architectural context.
* **`target_repos`**: Deterministic circular target queue.
* **`repo_style_guides`**: Caches contributing templates, formatting, and structures.

### Optimization & Indices
* **`idx_api_usage`**: Composite index on `(provider, timestamp)` to optimize LLM call counts and quota checks.
* **`idx_api_usage_cleanup`**: Index on `(timestamp)` to optimize daily purge queries.
