# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Generated:** 2026-06-02  
**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence basis:** Direct code inspection. No assumptions. All line numbers and features are verified against the actual `v4.0.0` codebase.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter (Qwen → Gemini), and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

Version 4.0.0 introduces the **Omniscient Context Engine**, which recursively discovers repository documentation, chunks it semantically by markdown headers, ingests it into ChromaDB, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents. Furthermore, version 4.0.0 incorporates **Dynamic Bug Verification** (generating and executing Proof-of-Concept exploits in an isolated container sandbox, evaluated via LLM) and **Blast Radius & Regression Auditing** (using baseline test suite runs and downstream dependent analysis to guarantee zero regressions).

| Component | Technology | Active Role |
|-----------|------------|-------------|
| Language | Python 3.11+ | Core runtime language and script orchestration |
| HTTP client | `httpx` (async) | Interfacing with REST/GraphQL APIs |
| Primary LLM | `deepseek/deepseek-v4-flash` via OpenRouter | High-speed code analysis and structural intelligence |
| Code Gen LLM | `deepseek/deepseek-v4-pro` via OpenRouter | Generates complex multi-file code patches |
| Layer 1 Appraiser | `qwen/qwen3.7-max` via OpenRouter | First gate: rigorously filters False Positives |
| Layer 2 Supreme Auditor | `google/gemini-3.5-flash` via OpenRouter | Final approval on patches before GitHub submission |
| Red Team (Bloodhound) | `deepseek/deepseek-v4-flash` via OpenRouter | Initial proactive vulnerability sweeping |
| Static Scanners | `semgrep` | Pattern matching and CWE ruleset vulnerability discovery |
| Database | SQLite (`aiosqlite`) — WAL mode | High-performance local state and memory |
| Docker Sandbox | `docker>=7.1` | Completely isolated environments for PoC execution |
| Config | Pydantic v2 + YAML + `.env` | Strict type-checked configuration validation |
| CLI | `click>=8.1` + `rich>=13.0` | CLI command routing and styling |
| Vector DB | `chromadb>=0.4` | Local RAG vector search for repo intelligence |
| Notifications | Telegram / Slack / Discord | Multi-channel reporting for merges, bugs, and errors |

---

## 2. Directory Structure Blueprint

```text
.                                       # Workspace Root (v4.0.0)
├── Dockerfile                          # Stage 1 builder (wheel creation) + Stage 2 lean runtime v4.0.0
├── docker-compose.yml                  # agent-farm service definition with volumes (data/, logs/, secret_findings/)
├── start.sh                            # Unix quick start wrapper script
├── start.bat                           # Windows quick start wrapper script
├── Makefile                            # Standard Make directives (install, test, lint, build)
│
├── farm_agent/                         # Package root (version = "4.0.0")
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
│   │   ├── notifier.py                 # Telegram notifications integration
│   │   ├── profiles.py                 # Thorough, quick, and standard run configurations
│   │   ├── quotas.py                   # OpenRouter usage quota controllers
│   │   ├── rag.py                      # ChromaDB vector DB context loaders (with semantic markdown header chunking)
│   │   ├── retry.py                    # Retry decorators for GitHub/LLM interfaces
│   │   └── sandbox.py                  # DockerSandbox engine with Polyglot Guillotine, PoC execution context mapping
│   │
│   ├── analysis/
│   │   ├── analyzer.py                 # CodeAnalyzer (parallelized security, quality, UX scanners) & BloodhoundAnalyzer
│   │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
│   │
│   ├── generator/
│   │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
│   │   ├── poc.py                      # PoCGenerator (PoC validation & LLM evaluation)
│   │   ├── reviewer.py                 # ReviewerAgent (Self-reflective code auditor with Blast Radius checks)
│   │   └── scorer.py                   # QAHardcoreScorer (Qwen-based QA grader)
│   │
│   ├── github/
│   │   ├── client.py                   # Async-retrying GitHub REST and GraphQL Client
│   │   ├── discovery.py                # Target network search and crawler discoverers
│   │   ├── guidelines.py               # Guidelines, PR templates, and subsystem doc discovery
│   │   └── security_gate.py            # Identifies private security disclosure files
│   │
│   ├── issues/
│   │   └── solver.py                   # IssueSolver (solves issues, multi-file deep planner)
│   │
│   ├── llm/
│   │   ├── agents.py                   # LLM agent prompts and routing models
│   │   ├── context.py                  # Generator system instruction builders
│   │   ├── models.py                   # Model registry definitions
│   │   ├── provider.py                 # OpenRouter integration handlers
│   │   └── router.py                   # Task router mapping
│   │
│   ├── orchestrator/
│   │   ├── memory.py                   # Persistence memory sqlite connection interface
│   │   ├── pipeline.py                 # Pipeline (Standard & Circular pipelines implementation)
│   │   └── human.py                    # SuperHumanLoop (Terminator relentless daily scheduler)
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   └── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   │
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD;
    CLI[CLI (main.py)] --> Pipeline[FarmAgentPipeline];
    CLI --> SuperHumanLoop[Terminator Loop (human.py)];
    SuperHumanLoop --> Pipeline;
    SuperHumanLoop --> PRPatrol[PR Patrol];

    Pipeline --> GitHubClient[GitHub API Client];
    Pipeline --> Memory[SQLite Memory DB];
    Pipeline --> CodeAnalyzer[Code Analysis];
    Pipeline --> RepoIndexer[RAG Engine];

    CodeAnalyzer --> BloodhoundAnalyzer[Red Team Scan];
    CodeAnalyzer --> RepoMapper[AST / Dependency Map];

    Pipeline --> PoCGenerator[PoC Execution Sandbox];
    PoCGenerator --> DockerSandbox[Docker Execution];

    Pipeline --> ContributionGenerator[Patch Fix Generator];
    ContributionGenerator --> DockerSandbox;

    Pipeline --> Gatekeeper1[Layer 1 Appraiser: Qwen];
    ContributionGenerator --> Gatekeeper2[Layer 2 Audit: Gemini];

    Gatekeeper2 --> PRManager[PR Manager];
    Gatekeeper2 --> SecurityGate[Security Disclosure];
```

---

## 4. Core Execution Loops & Entry Points

### Terminator Execution Loop (SuperHuman Mode)
Orchestrated in `farm_agent/orchestrator/human.py` (`SuperHumanLoop`), the system runs a relentless, database-driven operational cycle that has entirely replaced legacy stocastic human delays:
1. **Loop Initialization:** Starts the relentless `while True` loop and checks daily constraints.
2. **Execution Steps:**
   - Evaluates active notifications and forces `PRPatrol` if feedback is open.
   - Triggers `hunt_circular()` directly from the JSON/SQLite target queue.
   - Follows with `patrol()` to continuously monitor CI pipelines and review responses.
3. **Throttling & Concurrency:** Incorporates `LLM_QUOTA_COOLDOWN` (5 minutes) if 429 limits hit and completely collapses execution to maintain token pools.
4. **Shutdown Hooks:** Gracefully manages SIGINT/TERM limits to guarantee that memory flushes cleanly out of WAL mode.

### Deep Issue Solver Loop
Orchestrated by `farm_agent/issues/solver.py`, transforming standard single-file patching into systemic resolution:
1. **Complexity Heuristics Assessment:** Filters issues evaluating label tags, length metrics, and referenced files to filter out unsolvable context.
2. **Dependency Routing:** Maps structural file constraints via `RepoMapper.get_module_dependencies`.
3. **Patch Execution Generation:** Proposes the deep-fix via LLM generation and directly runs native tests via isolated environments.

### DEV-QA Double-Pass Verification (Pipeline)
1. **Pre-Analysis Check:** Runs `npm test`, `pytest`, or baseline equivalents *before* attempting patches to establish standard baseline test failures.
2. **Patch Application & Pass 1:** Fixes the code and runs PoC execution again. The PoC must *fail* to verify bug eradication.
3. **Regression Audit Pass 2:** Re-runs the baseline test. It halts the pipeline completely and triggers auto-revert `git reset --hard` if the patch broke downstream or adjacent logic.

---

## 5. Database/State Schema (`memory.db`)

Built on asynchronous `aiosqlite` configured locally via WAL.

| Table Name | Description / Primary State |
|------------|---------------------------|
| `target_repos` | Queue table loaded via `target_repo.json`. Rotates via `scanned_at` logic continuously. |
| `analyzed_repos` | Stores historic data of projects that have already been run through Bloodhound. |
| `findings_cache` | Temporary buffer evaluating specific vulnerabilities before Gatekeeper assessment. |
| `submitted_prs` | Vital PR tracking. Holds URL limits, discussion replies count, and CI fix limits to prevent spam blocks. |
| `pr_outcomes` | Logs final conclusions (merged/rejected) of submitted PRs for maintainer vibe checking. |
| `blacklisted_repos`| Permanent blacklist avoiding repositories triggered by HOSTILE responses or failed Gate 0 AI bans. |
| `api_usage_log` | High-frequency logging to map token expenditure for rate limit handling. |
| `knowledge_base` | Houses architectural chunk strings and `FILTER_REJECTION_LESSON` entries to ensure continuous agent learning. |

**Indexes Built:** `idx_api_usage` maps composite `(provider, timestamp)` heavily optimizing quota queries inside `AdaptiveConcurrencyManager`.
