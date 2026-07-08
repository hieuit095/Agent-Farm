# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence Basis:** Direct code inspection.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter, and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

Version 4.0.0 introduces the **Omniscient Context Engine**, which recursively discovers repository documentation, chunks it semantically by markdown headers, ingests it into ChromaDB, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents. Furthermore, version 4.0.0 incorporates **Dynamic Bug Verification** (generating and executing Proof-of-Concept exploits in an isolated container sandbox, evaluated via LLM) and **Blast Radius & Regression Auditing** (using baseline test suite runs and downstream dependent analysis to guarantee zero regressions).

| Component | Technology | Source |
|-----------|------------|--------|
| Language | Python 3.11+ | `pyproject.toml` |
| HTTP client | `httpx` (async) | `pyproject.toml` |
| Primary LLM | `deepseek/deepseek-v4-flash` via OpenRouter | `farm_agent/core/config.py` |
| Code Gen LLM | `deepseek/deepseek-v4-pro` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Layer 1 Appraiser | `qwen/qwen3.7-max` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Layer 2 Supreme Auditor | `google/gemini-3.5-flash` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Red Team (Bloodhound) | `deepseek/deepseek-v4-flash` via OpenRouter | `farm_agent/core/config.py` |
| Semgrep rulesets | `p/security-audit`, `p/cwe-top-25`, `p/default`, `p/golang`, `p/rust`, `p/smart-contracts` | `farm_agent/core/config.py` |
| Database | SQLite (`aiosqlite`) — WAL mode, fallback to DELETE | `farm_agent/orchestrator/memory.py` |
| Docker Sandbox | `docker>=7.1` — complete network + capability isolation | `farm_agent/core/sandbox.py` |
| Config | Pydantic v2 + YAML + `.env` | `farm_agent/core/config.py` |
| CLI | `click>=8.1` + `rich>=13.0` | `farm_agent/cli/main.py` |
| Vector DB | `chromadb>=0.4` — RAG for file & documentation context | `farm_agent/core/rag.py` |
| Notifications | Telegram / Slack / Discord | `farm_agent/core/notifier.py` |

---

## 2. Directory Structure

```text
.                                       # Workspace Root (v4.0.0)
├── Dockerfile                          # Stage 1 builder (wheel creation) + Stage 2 lean runtime v4.0.0
├── docker-compose.yml                  # agent-farm service definition with volumes (data/, logs/, secret_findings/)
├── start.sh                            # Unix quick start wrapper script
├── start.bat                           # Windows quick start wrapper script
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
│   │   └── human.py                    # SuperHumanLoop relentless daily scheduler
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   ├── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │   └── janitor.py                  # PR Janitor (sweeps and destroys garbage PRs)
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
graph TD
    A[CLI Main] -->|Invokes| B[FarmAgentPipeline]
    B -->|Uses| C[RepoDiscovery]
    B -->|Uses| D[CodeAnalyzer]
    B -->|Uses| E[ContributionGenerator]
    B -->|Uses| F[PRManager]
    B -->|Uses| G[DockerSandbox]
    B -->|Uses| I[Memory (SQLite)]
    B -->|Uses| J[GitHubClient]

    D -->|Utilizes| K[BloodhoundAnalyzer]
    D -->|Calls| L[RepoMapper]

    E -->|Generates via| M[LLM Provider]
    E -->|Uses| N[PoCGenerator]
    E -->|Uses| O[QAHardcoreScorer]

    L --> P[ChromaDB / RAG]

    H[PRPatrol] -->|Operates alongside| B
    H --> J
    H --> I

    Q[SuperHumanLoop] -->|Orchestrates| B
    Q -->|Orchestrates| H
```

---

## 4. Core Execution Loops / Entry Points

### 4A. Standard Pipeline (`FarmAgentPipeline.run()`)
1.  **Discovery**: Retrieves a list of candidate repositories matching the criteria from GitHub.
2.  **Repo Setup**: Clones the repo locally and runs a baseline test execution in `DockerSandbox`.
3.  **Gate Checks**: Checks `AI_POLICY.md` for bans, interaction limits, and evaluates maintainer sentiment (Vibe Check).
4.  **Analysis**: `CodeAnalyzer` scans code using multiple parallel agents (Security, Quality, Docs) and maps structural dependencies using `RepoMapper`.
5.  **Filtering**: Drops documentation-only paths, enforces severity checks, runs deduplication logic, and executes the **Devil's Advocate** filter (`_validate_findings`) and **Layer 1 Appraiser**.
6.  **Fix Generation**: Uses a DEV-QA loop where `ContributionGenerator` writes patches, evaluating them via `QAHardcoreScorer`.
7.  **Dynamic Verification**: Uses `PoCGenerator` to trigger vulnerabilities in the `DockerSandbox`, dropping False Positives.
8.  **Sandbox Validation**: Runs the newly applied patch in the sandbox, checking efficacy (bug fixed) and regression (baseline tests still pass).
9.  **Layer 2 Audit**: The **Supreme Auditor** (Gemini) does a final review of the incident dossier and logs.
10. **Submission**: Opens a PR via `PRManager` or logs private disclosures via `Security Disclosure Gate`.

### 4B. Circular Target Loop (`FarmAgentPipeline.run_circular()`)
A deterministic loop fetching targets directly from the SQLite `target_repos` table, running `BloodhoundAnalyzer` (Semgrep) pre-filters before full analysis.

### 4C. PR Patrol (`PRPatrol.patrol()`)
Periodically scans open PRs. Reads comments, runs LLM classification (`CODE_FIX`, `QUESTION`, `CI_FAILURE`), and orchestrates automatic updates to the PR branch (e.g., CI auto-fixes run in the Docker Sandbox).

### 4D. Terminator Mode (`SuperHumanLoop.run_daily_routine()`)
A continuous 24/7 loop alternating between `run_circular` (hunting) and `patrol`, managing daily PR quotas and API usage limits.

---

## 5. Database/State Schema

The agent uses an SQLite database (`data/memory.db`) initialized via `aiosqlite`. Key tables:

*   **`analyzed_repos`**: History of analyzed repos (full name, language, stars, timestamp).
*   **`submitted_prs`**: Records all created PRs/issues, tracking state, branch, CI fix attempts, and discussion limits.
*   **`run_log`**: Aggregated stats for individual pipeline runs.
*   **`pr_outcomes`**: Tracks PR resolution states (merged/closed) and maintainer feedback.
*   **`repo_preferences`**: A feedback loop storing learned preferences for each repo based on `pr_outcomes`.
*   **`target_repos`**: Deterministic queue for circular hunting (`repo_url`, `status`, `scanned_at`, `bounty_amount`).
*   **`knowledge_base`**: Stores retrieved architectural context, QA lessons, and filter rejection lessons for RAG queries.
*   **`api_usage_log`**: Time-series log tracking OpenRouter API requests for quota management.
*   **`repo_style_guides`**: Caches parsed contributing templates and formatting requirements.
