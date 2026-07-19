# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  

This document serves as a deep-dive architectural guide to the Agent-Farm codebase.

---

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous AI agent ecosystem designed to discover open-source GitHub repositories, analyze code for vulnerabilities and issues via multi-phase LLM prompts, generate patches, and validate them dynamically in isolated Docker sandboxes. It incorporates advanced self-correcting DEV-QA loops and filters out low-effort or hallucinated PRs.

| Component | Technology | Role / Usage |
|-----------|------------|--------------|
| **Language** | Python 3.11+ | Core programming language. |
| **HTTP client** | `httpx` (async) | Used for asynchronous REST interactions (e.g., GitHub API). |
| **Build Backend** | `hatchling` | Package building configured via `pyproject.toml`. |
| **Config/Data Validation** | `pydantic` v2, `pydantic-settings`, YAML | Validates models, schema configurations, and environment variables. |
| **Primary/Red Team LLMs** | `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro` | Powers the core analysis, Bloodhound Pre-Filter, and Contribution Code Generation via OpenRouter. |
| **Layer 1 Appraiser** | `qwen/qwen3.7-max` | Evaluates findings to rule out false positives and theoretical edge cases. |
| **Layer 2 Supreme Auditor** | `google/gemini-3.5-flash` | Final gatekeeper reviewing incident dossier, patch, and sandbox logs to prevent hallucinations before PR generation. |
| **Static Code Analysis** | Semgrep (`ast-grep`) | Powers Bloodhound Red Team with `p/security-audit`, `p/cwe-top-25`, and language-specific rulesets. |
| **Database** | SQLite (`aiosqlite`) | Maintains persistent state, memory queues, PR limits, metrics, and KB in `data/memory.db`. |
| **Docker Sandbox** | `docker` (Python API) | Complete network and capability isolation for running PoCs and regression tests. |
| **CLI Framework** | `click`, `rich` | Provides a robust, formatted command-line interface. |
| **Vector Database** | `chromadb` | Powers the Omniscient Context Engine (RAG) by indexing semantic chunks of documentation. |
| **Notifications** | Telegram, Slack, Discord | Alerts for pipeline completions, successful PRs, and required private disclosures. |

---

## 2. Directory Structure

```ascii
Agent-Farm/
├── farm_agent/
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   ├── analysis/
│   │   ├── analyzer.py                 # Core analyzers and Bloodhound Semgrep scanner
│   │   └── mapper.py                   # AST/regex module dependency graphing
│   ├── cli/
│   │   └── main.py                     # Click CLI entry points
│   ├── core/
│   │   ├── config.py                   # Pydantic configuration definitions
│   │   ├── exceptions.py               # Custom exceptions
│   │   ├── leaderboard.py              # Stats collection
│   │   ├── logger.py                   # Logger setup
│   │   ├── middleware.py               # Context middleware chain
│   │   ├── models.py                   # Pydantic data models
│   │   ├── notifier.py                 # Integration for Telegram, Slack, Discord
│   │   ├── profiles.py                 # CLI run configurations presets
│   │   ├── quotas.py                   # Quota limits handling
│   │   ├── rag.py                      # ChromaDB vector DB loading & semantic chunking
│   │   ├── retry.py                    # Retry decorators
│   │   └── sandbox.py                  # DockerSandbox for PoC and tests
│   ├── generator/
│   │   ├── engine.py                   # Contribution patching and generation
│   │   ├── poc.py                      # Generates PoCs and evaluates their outcome
│   │   ├── reviewer.py                 # Self-reflective code auditor
│   │   └── scorer.py                   # QA grader powered by LLMs
│   ├── github/
│   │   ├── client.py                   # GitHub REST API interactions
│   │   ├── discovery.py                # Repository targeting and searching
│   │   ├── guidelines.py               # Parse and extract contributing guidelines
│   │   └── security_gate.py            # Determines if a private security disclosure is needed
│   ├── issues/
│   │   └── solver.py                   # Solves issues dynamically
│   ├── llm/
│   │   ├── agents.py                   # Prompts and LLM routing
│   │   ├── context.py                  # Context builders
│   │   ├── models.py                   # Model registries
│   │   ├── provider.py                 # OpenRouter interactions
│   │   └── router.py                   # Routes tasks to specific models
│   ├── notifications/
│   │   └── notifier.py                 # Standard Notification wrapper
│   ├── orchestrator/
│   │   ├── human.py                    # SuperHumanLoop (Terminator Mode)
│   │   ├── memory.py                   # SQLite Database initialization and operations
│   │   └── pipeline.py                 # Standard and Circular core pipeline loops
│   ├── plugins/                        # Extension plugins
│   ├── pr/
│   │   ├── manager.py                  # PR forks, branch, and commits management
│   │   └── patrol.py                   # Monitors and replies to open PRs, auto-fixes CI
│   ├── templates/
│   │   └── registry.py                 # Registers built-in PR templates
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
├── tests/                              # Unit & integration tests
├── Dockerfile                          # Docker configuration for Agent-Farm
├── docker-compose.yml                  # Compose definition for agent-farm service
├── Makefile                            # Make targets (install, test, build, lint, clean, docker)
├── pyproject.toml                      # Project metadata and Hatchling build configuration
├── requirements.txt                    # Project dependencies
├── start.sh                            # Unix 1-Click Launch Script
└── start.bat                           # Windows 1-Click Launch Script
```

*(Note: Trivial and disabled files such as `.gitignore`, `.env.example`, and `.DISABLED` files have been omitted for clarity)*

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    %% Entry Point
    CLI[CLI (main.py)] --> Pipeline[FarmAgentPipeline (pipeline.py)]
    CLI --> HumanLoop[SuperHumanLoop (human.py)]
    HumanLoop --> Pipeline

    %% Orchestrator
    Pipeline --> Mem[Memory (memory.py / SQLite)]
    Pipeline --> GH[GitHubClient (client.py)]
    Pipeline --> Analyzer[CodeAnalyzer & Bloodhound (analyzer.py)]
    Pipeline --> Generator[ContributionGenerator (engine.py)]
    Pipeline --> Sandbox[DockerSandbox (sandbox.py)]
    Pipeline --> PRManager[PRManager (manager.py)]

    %% Analysis & Context
    Analyzer --> Mapper[RepoMapper (mapper.py)]
    Pipeline --> RAG[Omniscient Context Engine (rag.py / ChromaDB)]

    %% Generator & Gates
    Generator --> PoC[PoCGenerator (poc.py)]
    Generator --> Scorer[QAHardcoreScorer (scorer.py)]

    %% PR Management & Security
    PRManager --> GH
    Pipeline --> SecGate[Security Gate (security_gate.py)]
    CLI --> Patrol[PR Patrol (patrol.py)]
    Patrol --> GH
```

---

## 4. Core Execution Loops / Entry Points

### Circular Target Loop (`hunt-circular` / `SuperHumanLoop`)
1. **Target Selection:** Reads the determinisic target from `target_repo.json` (tracked in `target_repos` SQLite table).
2. **Bloodhound Pre-Filter:** The `BloodhoundAnalyzer` conducts a white-hat Semgrep scan. If no bugs are found, it early-exits. Vulnerabilities in non-production files are filtered out.
3. **Contextual Augmentation:** Uses GraphQL/REST to build a file tree, extracts relevant code files, and builds a dependency map (`RepoMapper`). `RepoIndexer` semantically maps documentation via ChromaDB.
4. **DEV-QA Bounty Loop:** Generates code patches using LLMs. The `QAHardcoreScorer` grades it; rejections are sent back for a maximum of 3 DEV-QA cycles.
5. **Dynamic Bug Verification (PoC):** Generates a PoC exploit. The patch is verified if the PoC successfully triggers the bug on unpatched code, and fails to trigger it on the patched code.
6. **Regression Audit:** The `DockerSandbox` runs native tests on the patched codebase to ensure no regressions occur.
7. **Supreme Audit:** Layer 2 Auditor (`gemini-3.5-flash`) verifies the entire dossier and sandbox logs to prevent hallucinations.
8. **Security Gate:** Checks if a private disclosure is requested, saving it locally if needed, otherwise delegating to `PRManager` to submit the Pull Request.

### Standard Pipeline (`run`)
Performs repository discovery based on language/star targets (`RepoDiscovery`), filtering out restricted repos, hostile maintainers (`check_maintainer_vibe`), and enforcing Anti-Farming rules. Then, it runs the same core steps as the Circular loop.

### PR Patrol
Continuously queries open PRs. Reads reviewer feedback, answers questions, handles CLA checks, and auto-fixes CI failures by pushing new commits via a sandbox-verified fix.

---

## 5. Database/State Schema

Agent-Farm utilizes an `aiosqlite` instance operating in **WAL (Write-Ahead Logging)** mode. The database (`data/memory.db`) orchestrates state logic and persists queues, quotas, findings, and preferences.

| Table | Description | Key Columns |
|-------|-------------|-------------|
| **`analyzed_repos`** | Tracks previously scanned repositories. | `full_name`, `language`, `stars`, `findings`, `analyzed_at` |
| **`submitted_prs`** | Tracks bot-created PRs/Issues. | `repo`, `pr_number`, `type`, `status`, `ci_fix_attempts`, `discussion_replies` |
| **`findings_cache`** | Temporary storage for detected code findings. | `id`, `repo`, `type`, `severity`, `title`, `file_path` |
| **`run_log`** | General run metrics. | `started_at`, `repos_analyzed`, `prs_created`, `findings`, `errors` |
| **`pr_outcomes`** | Stores merged/closed states and feedback for repo profiling. | `repo`, `pr_number`, `outcome`, `feedback`, `time_to_close_hours` |
| **`repo_preferences`** | Aggregated preferences dynamically updated from PR outcomes. | `repo`, `preferred_types`, `rejected_types`, `merge_rate`, `avg_review_hours` |
| **`blacklisted_repos`** | Tracks repositories to skip (due to hostility or AI policies). | `repo`, `reason`, `blacklisted_at` |
| **`api_usage_log`** | Tracks OpenRouter API calls for quota limits. | `timestamp`, `provider` |
| **`task_schedule`** | Schedules next-run timestamps for periodic tasks (e.g. `SuperHumanLoop`). | `task_key`, `next_run` |
| **`knowledge_base`** | Learning lessons, QA critiques, and Architectural constraints. | `repo_name`, `entry_type`, `content` |
| **`target_repos`** | Deterministic circular target queue. | `repo_url`, `status`, `scanned_at`, `bounty_amount` |
| **`repo_style_guides`** | Summarized contributing templates and formatting guidelines. | `repo`, `style_summary`, `contributing_md` |
