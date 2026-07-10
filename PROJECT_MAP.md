# PROJECT_MAP.md — Architectural Blueprint

**Project Name:** Agent-Farm
**Version:** 4.0.0 (Omniscient Context Engine)
**Entry Point:** `farm_agent/cli/main.py` -> `cli()`

---

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous AI agent designed to discover GitHub repositories, analyze code for vulnerabilities and issues, generate validated fixes within isolated Docker sandboxes, and submit high-quality Pull Requests.

### Active Tech Stack

| Component | Technology | Description |
|-----------|------------|-------------|
| **Core Language** | Python 3.11+ | Primary application language. |
| **Orchestration** | Docker (>=7.1) | Isolated sandbox execution for dynamic verification and test suites. |
| **CLI Framework** | `click` + `rich` | Command-line interface and terminal output formatting. |
| **HTTP / API** | `httpx` (async) | Async HTTP client for communicating with GitHub REST/GraphQL APIs. |
| **Data Models** | `pydantic` v2 | Strict validation and configuration mapping. |
| **Database** | SQLite (`aiosqlite`) | Persistent memory tracking repositories, PR outcomes, quotas, and logs. |
| **Vector DB (RAG)** | ChromaDB (>=0.4) | Semantically chunks and stores repository documentation for subsystem context. |
| **Build System** | Hatchling | Modern PEP 517 build backend (`pyproject.toml`). |
| **Primary LLMs** | `deepseek-v4-pro` | Code generation and fix implementations via OpenRouter. |
| **Appraisal LLMs** | `qwen3.7-max` | Layer 1 Appraiser: strict vulnerability validation and scoring. |
| **Audit LLMs** | `gemini-3.5-flash` | Layer 2 Supreme Auditor: verifies incident dossiers and sandbox execution logs. |

---

## 2. Directory Structure

```text
farm_agent/
├── __init__.py
├── agents/             # Task agent configurations
│   ├── __init__.py
│   └── registry.py
├── analysis/           # Code analysis and dependency graphing
│   ├── __init__.py
│   ├── analyzer.py     # CodeAnalyzer (quality, UI/UX scanners) & BloodhoundAnalyzer (Semgrep)
│   └── mapper.py       # RepoMapper (AST/regex dependency graphing)
├── cli/                # Click-based Command Line Interface
│   ├── __init__.py
│   └── main.py         # Main CLI commands (run, target, hunt, superhuman, patrol)
├── core/               # System internals, RAG, and Sandboxing
│   ├── __init__.py
│   ├── config.py       # Configuration loading and Pydantic models
│   ├── daily_log.py
│   ├── exceptions.py
│   ├── leaderboard.py
│   ├── logger.py
│   ├── middleware.py
│   ├── models.py
│   ├── notifier.py
│   ├── profiles.py
│   ├── quotas.py
│   ├── rag.py          # ChromaDB integration & Semantic markdown header chunking
│   ├── retry.py
│   └── sandbox.py      # DockerSandbox (Dynamic Bug Verification & Regression Execution)
├── generator/          # Code patch generation and QA scoring
│   ├── __init__.py
│   ├── engine.py       # ContributionGenerator
│   ├── poc.py          # PoCGenerator (Proof-of-Concept exploit validation)
│   ├── reviewer.py
│   └── scorer.py       # QAHardcoreScorer
├── github/             # GitHub API abstractions
│   ├── __init__.py
│   ├── client.py       # Async GraphQL and REST client
│   ├── discovery.py    # Target crawler and discovery loops
│   ├── guidelines.py   # Extracts CONTRIBUTING.md, PR templates, and internal docs
│   └── security_gate.py# Security Disclosure Protocol (stops public PRs for sensitive bugs)
├── issues/             # GitHub Issue resolution logic
│   ├── __init__.py
│   └── solver.py       # IssueSolver (Proactively plans deep, multi-file fixes)
├── llm/                # LLM Provider integrations and Context Routing
│   ├── __init__.py
│   ├── agents.py
│   ├── context.py
│   ├── models.py
│   ├── provider.py     # OpenRouter provider logic
│   └── router.py
├── notifications/      # External alerting
│   ├── __init__.py
│   └── notifier.py     # Telegram / Slack / Discord integrations
├── orchestrator/       # Main execution loops and memory storage
│   ├── __init__.py
│   ├── human.py        # SuperHumanLoop (Terminator Mode relentless daemon)
│   ├── memory.py       # SQLite database logic and schema
│   └── pipeline.py     # FarmAgentPipeline (Standard and Circular loops)
├── plugins/
│   └── __init__.py
├── pr/                 # Pull Request lifecycle management
│   ├── __init__.py
│   ├── manager.py      # Branching, committing, and submitting PRs
│   └── patrol.py       # PRPatrol (Reads comments, addresses feedback, auto-fixes CI)
├── templates/          # Code generation templates
│   ├── __init__.py
│   └── registry.py
└── tools/
    ├── __init__.py
    └── protocol.py
```

---

## 3. Core Module Dependency Graph

```mermaid
flowchart TD
    CLI[CLI (main.py)] --> Pipeline(FarmAgentPipeline)
    Pipeline --> Discovery(GitHub Discovery)
    Pipeline --> Analyzer(Code Analyzer & RAG)
    Pipeline --> Generator(Contribution Generator)
    Pipeline --> Sandbox(Docker Sandbox)
    Pipeline --> PRManager(PR Manager & Security Gate)

    Discovery --> GitHubClient[GitHub API Client]
    Analyzer --> RepoMapper[AST Mapper]
    Analyzer --> ChromaDB[(ChromaDB RAG)]
    Analyzer --> OpenRouter[OpenRouter LLMs]

    Generator --> OpenRouter
    Generator --> QA(QA Scorer - Qwen)

    Sandbox --> DockerDaemon[Local Docker Daemon]

    PRManager --> GitHubClient
    PRManager --> Memory[(SQLite Memory)]

    SuperHumanLoop[Terminator Mode] --> Pipeline
    SuperHumanLoop --> Patrol(PR Patrol Daemon)

    Patrol --> GitHubClient
    Patrol --> Sandbox
```

---

## 4. Core Execution Loops

### Standard Pipeline (`FarmAgentPipeline._process_repo`)
1. **Clone & Baseline:** Clones the repository locally and runs the native test suite inside the Docker Sandbox to establish a baseline.
2. **Context Gathering:** Indexes documentation into ChromaDB and builds the AST dependency graph.
3. **Analysis:** Scans the codebase for flaws, generating initial findings.
4. **Anti-Farming Gate:** Drops documentation fixes, typo tweaks, and low-impact issues. Only HIGH/CRITICAL severity or verified bugs proceed.
5. **Layer 1 Appraisal:** Qwen-3.7-Max aggressively evaluates the finding for false positives.
6. **PoC Verification:** The system generates an exploit PoC and runs it in the Sandbox. If the vulnerability doesn't trigger, it is dropped.
7. **Generation & QA:** The patch is generated. If QA score < 10.0, critiques are fed back into a self-correcting DEV-QA loop.
8. **Blast Radius & Regression:** The patched code is run in the Sandbox. (Pass 1: Does the PoC fail? Pass 2: Do native tests still pass?).
9. **Layer 2 Audit:** Gemini-3.5-Flash performs a final sanity check on the incident dossier and logs.
10. **Disclosure/Submit:** If it's a private security bug, it triggers the Security Gate. Otherwise, it pushes the branch and creates the Pull Request.

### Circular Target Loop (`FarmAgentPipeline.run_circular`)
Executes the identical standard pipeline, but instead of aggressively crawling GitHub for random targets, it reads sequentially from a deterministic local database table (`target_repos`), updating `scanned_at` timestamps for a crash-safe round-robin execution.

### PR Patrol Daemon (`PRPatrol.patrol`)
A background routine that periodically queries the GitHub API for open Pull Requests generated by the bot. It evaluates CI check runs and maintainer comments. If CI fails, it downloads the traceback, guesses the failing file, and generates a follow-up commit to auto-heal the PR.

---

## 5. Database State Schema (`memory.db`)

Agent-Farm utilizes an `aiosqlite` WAL-mode database to track state and maintain contextual memory.

- **`analyzed_repos`**: Tracks repositories that have already been scanned to avoid redundant processing.
- **`submitted_prs`**: Logs created pull requests, issues, tracking status, and limits (e.g., max discussion replies, max CI fix attempts).
- **`findings_cache`**: Temporary storage of identified issues.
- **`run_log`**: Records start/finish times and overall run execution metrics.
- **`pr_outcomes`**: Tracks merged, closed, or rejected PRs and extracts the maintainer feedback.
- **`repo_preferences`**: A dynamically updated preference model detailing preferred vs rejected contribution types per repository, learned from `pr_outcomes`.
- **`blacklisted_repos`**: Prevents targeting repos that have hostile maintainers or strict AI bans.
- **`api_usage_log`**: Tracks timestamps of OpenRouter requests to enforce strict rate limits.
- **`task_schedule`**: Persistent tracking for asynchronous cleanup jobs.
- **`knowledge_base`**: Stores architectural context and `qa_lesson` strings to prevent the agent from repeating the same mistakes across different PRs.
- **`target_repos`**: The central queue for the Circular Target Loop, tracking bounties and language metadata.
- **`repo_style_guides`**: Caches parsed `CONTRIBUTING.md` and PR templates.
