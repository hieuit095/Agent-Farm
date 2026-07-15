# PROJECT_MAP.md — Agent-Farm Architectural Blueprint

**Version:** v4.0.0 — Omniscient Context Engine

This document provides a deep-dive architectural guide to the Agent-Farm system. It maps out the actual structure, technologies, dependency relationships, and schemas driving the repository.

---

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous AI agent system designed to execute continuous security research and open source contributions on GitHub. It discovers repositories, scans code via multi-phase LLM prompts, generates patches and PoC scripts, validates them inside locked-down Docker sandboxes, and applies a rigid two-layer filtering system prior to generating PRs or private security disclosures.

| Component | Technology | Role |
|-----------|------------|------|
| **Core Language** | Python 3.11+ | Primary execution environment. |
| **HTTP Client** | `httpx` (async) | Async external API requests (GitHub, OpenRouter). |
| **Primary LLM** | `deepseek/deepseek-v4-flash` via OpenRouter | General reasoning, system coordination. |
| **Code Gen LLM** | `deepseek/deepseek-v4-pro` via OpenRouter | Generating vulnerability fixes and sandbox PoC scripts. |
| **Layer 1 Appraiser** | `qwen/qwen3.7-max` via OpenRouter | First gate: rigorously evaluates finding validity. |
| **Layer 2 Auditor** | `google/gemini-3.5-flash` via OpenRouter | Supreme gate: final audit of vulnerability dossier and patch. |
| **Red Team Scan** | Semgrep (`p/security-audit`, `p/cwe-top-25`, etc) | Preliminary rapid static analysis to find potential vulnerabilities. |
| **State / DB** | SQLite (`aiosqlite`) | Local persistent memory configured with WAL mode. |
| **Validation Environment**| Docker `>=7.1` | Isolated sandboxes for executing untrusted PoC and tests safely. |
| **Configuration** | Pydantic v2 + YAML + `.env` | Environment configurations and application parameters. |
| **CLI Framework** | Click (`click>=8.1`) + Rich (`rich>=13.0`) | Terminal UI components and command handling. |
| **Vector DB / RAG**| ChromaDB (`chromadb>=0.4`) | Indexes internal codebase documentation via semantic chunking. |

---

## 2. Directory Structure

```text
.
├── docker-compose.yml           # Multi-container orchestration (agent-farm service)
├── Dockerfile                   # Build steps for the Agent-Farm container
├── Makefile                     # Build & run helper commands (install, test, lint)
├── pyproject.toml               # Python project dependencies (Hatchling backend)
├── requirements.txt             # Dependency freezing (for local quickstart/sandbox)
├── start.bat                    # Windows quick start wrapper script
├── start.sh                     # Unix quick start wrapper script
└── farm_agent/                  # Main package module (v4.0.0)
    ├── __init__.py
    ├── agents/
    │   └── registry.py          # Central registry for managing specialized task agents
    ├── analysis/
    │   ├── analyzer.py          # CodeAnalyzer & BloodhoundAnalyzer (LLM & Semgrep scanning)
    │   └── mapper.py            # AST-based dependency graph mapping (RepoMapper)
    ├── cli/
    │   └── main.py              # Central Click-based CLI entry point
    ├── core/
    │   ├── config.py            # Pydantic v2 application configurations
    │   ├── daily_log.py         # Markdown activity logs formatting
    │   ├── exceptions.py        # Centralized custom exception definitions
    │   ├── leaderboard.py       # Metrics aggregator for leaderboard statistics
    │   ├── logger.py            # Setup for rotating log files
    │   ├── middleware.py        # Pipeline execution middleware components
    │   ├── models.py            # Core Pydantic data schemas
    │   ├── notifier.py          # Notification handlers (Slack, Discord, Telegram)
    │   ├── profiles.py          # Named execution configuration profiles
    │   ├── quotas.py            # OpenRouter API quota limitations handling
    │   ├── rag.py               # ChromaDB interfacing for semantic document indexing
    │   ├── retry.py             # Resilience decorators for external API backoffs
    │   └── sandbox.py           # DockerSandbox implementation for dynamic execution
    ├── generator/
    │   ├── engine.py            # ContributionGenerator: generating fixes
    │   ├── poc.py               # PoCGenerator: generates and evaluates bug PoCs
    │   ├── reviewer.py          # Self-reflective auditing agent with Blast Radius
    │   └── scorer.py            # Hardcore Qwen-based QA grading system
    ├── github/
    │   ├── client.py            # Resilient async GitHub REST & GraphQL API Client
    │   ├── discovery.py         # Target repository searching & crawling
    │   ├── guidelines.py        # Logic to parse repository styles & CONTRIBUTING files
    │   └── security_gate.py     # Detects private security disclosure policies
    ├── issues/
    │   └── solver.py            # Issue-first deep solver planning multi-file changes
    ├── llm/
    │   ├── agents.py            # LLM prompt scaffolding and basic agent definitions
    │   ├── context.py           # Generator system instruction logic
    │   ├── models.py            # Registry of available LLMs and their properties
    │   ├── provider.py          # OpenRouter integration and API execution
    │   └── router.py            # Routes tasks dynamically to the appropriate model
    ├── notifications/
    │   └── notifier.py          # Abstract notification channel interfacing
    ├── orchestrator/
    │   ├── human.py             # SuperHumanLoop (Terminator Mode) execution scheduler
    │   ├── memory.py            # Interface for SQLite data persistence and schema management
    │   └── pipeline.py          # Orchestrates execution loops (FarmAgentPipeline)
    ├── plugins/                 # Extensibility hooks for customized behaviour
    ├── pr/
    │   ├── janitor.py           # Sweeps external PRs to purge garbage submissions
    │   ├── manager.py           # Controls GitHub forks, branches, commits, and PR actions
    │   └── patrol.py            # Monitors open PRs, replies to comments, and fixes CI
    ├── templates/               # Reusable contribution template string structures
    └── tools/
        └── protocol.py          # Shared tool interfaces
```

---

## 3. Core Module Dependency Graph

```mermaid
flowchart TD
    %% CLI and Main Loops
    CLI[main.py CLI] --> Pipeline(FarmAgentPipeline)
    CLI --> Patrol(PRPatrol)
    CLI --> Terminator(Terminator Mode / SuperHumanLoop)

    %% Pipeline Internals
    Terminator --> Pipeline
    Pipeline --> Memory[Memory DB (SQLite)]
    Pipeline --> GitHub[GitHubClient]
    Pipeline --> Discovery[RepoDiscovery]
    Pipeline --> Analyzer[CodeAnalyzer / Bloodhound]

    %% Code Context and Knowledge Injection
    Analyzer --> RepoMapper[RepoMapper AST Dependency Map]
    Pipeline --> RAG[ChromaDB RAG Engine]

    %% Generation and Quality Assurance
    Pipeline --> Generator[ContributionGenerator]
    Generator --> PoC[PoCGenerator]
    Generator --> Scorer[QAHardcoreScorer (Layer 1)]
    Pipeline --> Auditor[Supreme Auditor (Layer 2)]

    %% Dynamic Verification
    Generator --> Docker[DockerSandbox]
    Docker -- "Validates Efficacy & Regressions" --> Auditor

    %% Final Submission
    Auditor --> Diplomat[Security Disclosure Gate]
    Diplomat --> Manager[PRManager]
    Manager --> GitHub
    Manager --> Notification[Notifier]
```

---

## 4. Core Execution Loops / Entry Points

The agent ecosystem operates primarily through the Click commands defined in `farm_agent/cli/main.py`. The fundamental execution logic runs within `FarmAgentPipeline` located in `farm_agent/orchestrator/pipeline.py`.

### A. Terminator Mode
The command `farm_agent superhuman` invokes a continuous operation loop (historically known as Super Human mode, now upgraded to Terminator Mode). This relentless loop utilizes the `SuperHumanLoop` class. It manages continuous cycles between `FarmAgentPipeline.run_circular` (pulling fixed targets from `target_repo.json`) and `PRPatrol`, dynamically allocating resources 24/7 without artificial delays.

### B. Standard Pipeline (`farm_agent run` / `farm_agent target`)
1. **Early Discovery & Clone:** Fetches repository targets, bypassing those that fail the AI_POLICY gate, Interaction Limits gate, or the Maintainer Vibe check. It clones the target repository to a temporary directory early to establish the code baseline.
2. **Context Establishment:** Indexes markdown documentation recursively utilizing semantic ChromaDB integration (`RepoIndexer`), and creates an AST-based dependency linkage graph mapping `imports`, `calls`, and `dependents`.
3. **Analysis & Bloodhound:** Leverages Semgrep for pre-scans and parallel LLM instances to find issues. The findings are heavily pruned by the Anti-Farming Filter to discard README changes and trivial fixes.
4. **DEV-QA Verification & Generation:** Validated findings proceed into generation.
   - A Proof of Concept script is created.
   - The patch is applied locally.
   - The DockerSandbox executes a two-pass Blast Radius check. Pass 1 checks if the PoC is neutralized. Pass 2 executes the native test suite to prevent regressions.
5. **Appraisal & Auditing:** Findings pass through the Layer 1 Expert Appraiser (`qwen3.7-max`), and the overall fix passes the Layer 2 Supreme Auditor (`gemini-3.5-flash`).
6. **Submission:** Determines if the issue falls under a direct PR route or must go through the Diplomat Security Disclosure Gate. PRs are submitted via the `PRManager`.

---

## 5. Database/State Schema

Agent-Farm leverages an `aiosqlite` SQLite database operating in WAL mode to retain knowledge, limits, and runtime states. Key tables include:

* **`analyzed_repos`**: Prevents duplicated work by tracking previously analyzed repositories. Fields include `full_name`, `language`, `stars`, `findings`, and `metadata`.
* **`submitted_prs`**: Logs bot-created Pull Requests, their states, branches, and discussion limiters. Keyed by a unique `(repo, pr_number)` constraint.
* **`pr_outcomes`**: Maintains maintainer review remarks, merge states, and close durations to learn repo preferences.
* **`repo_preferences`**: Actively updated repository-specific preferences derived from `pr_outcomes`. Fields include `preferred_types`, `rejected_types`, and `merge_rate`.
* **`run_log`**: Historical aggregated metrics on complete CLI executions (run durations, repos hit, errors).
* **`blacklisted_repos`**: Explicit blocklist. Entries are marked if the maintainer vibe check fails (`toxic_maintainer`), preventing future analysis.
* **`api_usage_log`**: LLM API tracking to enforce `max_daily_prs` and calculate OpenRouter costs.
* **`knowledge_base`**: Crucial storage for QA rejection lessons, filter rejections, and context definitions. Unique composite constraint on `(repo_name, entry_type, content)`.
* **`target_repos`**: Circular queue determining targets, storing `scanned_at` timestamps for round-robin deterministic selection.
* **`findings_cache`**: Temporary storage for current active scan findings.
* **`repo_style_guides`**: Caches parsed contributing templates and structural logic rules (`CONTRIBUTING.md`).
