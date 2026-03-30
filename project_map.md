# Farm-Agent — Project Map

> **Last updated:** 2026-03-30
> **Status:** Active development — v2.5.0
> **Purpose:** This file is the authoritative source of truth for the project's current architecture.

---

## 1. PROJECT OVERVIEW

Farm-Agent is an AI-powered autonomous agent that discovers GitHub repositories matching user-defined criteria, analyzes their source code for issues, generates targeted fixes or enhancements, and submits pull requests — all without human intervention. It also continuously patrols its submitted PRs to respond to maintainer review feedback, auto-heals failing CI pipelines, and cleans up low-quality PRs via a "Ruthless Janitor" mode.

**Primary goal:** Maximize meaningful open-source contributions by operating 24/7 with a human-developer operational cadence (Super Human Mode), including daily PR quotas, randomized delays, and adaptive behavior based on review feedback.

---

## 2. TECH STACK & INFRASTRUCTURE

### Languages & Runtimes
- **Python 3.12** (primary language)
- **Docker** (containerized deployment)

### Core Dependencies
| Package | Purpose |
|---------|---------|
| `httpx` | Async HTTP client (GitHub API, LLM API) |
| `pydantic` + `pydantic-settings` | Configuration validation |
| `aiosqlite` | Async SQLite (persistent memory) |
| `google-genai` | Minimax LLM API client |
| `openai` | OpenAI-compatible LLM interface |
| `anthropic` | Anthropic Claude API |
| `apscheduler` | Cron-based scheduler for automated runs |
| `click` | CLI framework |
| `rich` | Terminal UI / tables / panels |
| `gitpython` | Git operations (fork management) |
| `docker` | Docker API for sandbox validation |
| `chromadb` | Vector store for RAG-based cross-file analysis |
| `numpy` | Numerical operations |
| `pyyaml` | YAML config parsing |

### Infrastructure
- **Database:** SQLite with WAL mode (`data/memory.db`)
- **Cache:** File-based daily logs (`logs/`, `daily_log/`)
- **Container:** Docker image built from `Dockerfile`; `docker-compose.yml` defines `scheduler` and `runner` services
- **Notifications:** Telegram bot (push), Slack/Discord webhooks (optional)

---

## 3. SYSTEM ARCHITECTURE

### High-Level Data Flow

```
CLI Entry Point
(farm_agent run | hunt | patrol | superhuman)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                  ContribPipeline                       │
│  discover → analyze → filter → generate → validate    │
└───────────────┬───────────────────────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│Discovery│ │Analyzer │ │Generator │◄──── PRManager
│(GitHub)│ │  (LLM)  │ │          │     (GitHub API)
└────────┘ └────┬────┘ └────┬────┘
                │           │
                │     ┌─────┴─────┐
                │     ▼           ▼
                │  ┌────────┐ ┌────────┐
                │  │Sandbox │ │GitHub  │
                │  │Docker  │ │Client  │
                │  └────────┘ └────────┘
                │
┌───────────────┴─────────────────────┐
│          Memory (SQLite)            │
│  analyzed_repos, submitted_prs,      │
│  findings_cache, run_log,           │
│  pr_outcomes, repo_preferences,     │
│  blacklisted_repos, api_usage_log  │
└─────────────────────────────────────┘
```

### Operational Modes

1. **Hunt Mode** — Discovers repos via GitHub Search API, analyzes code with LLM, generates PRs
2. **Patrol Mode** — Monitors open PRs for maintainer feedback, auto-responds with fixes or answers
3. **Super Human Mode** — 24/7 stochastic loop alternating between Hunt and Patrol with human-like delays and randomized daily PR quotas (1–5/day)
4. **Janitor Mode** — Scans all user PRs and destroys low-value ones using LLM classification

### Key Design Patterns

- **Agent Registry** (`agents/registry.py`): Strategy pattern for swappable analysis agents
- **Tool Registry** (`tools/protocol.py`): Extensible toolset for LLM function calling
- **Middleware Chain** (`core/middleware.py`): Request/response processing pipeline (DeerFlow pattern)
- **Hybrid Contribution Router**: SECURITY_FIX / CRITICAL → Direct PR; everything else → Issue-First protocol
- **Anti-Farming Gate**: Drops findings by MEDIUM/LOW impact or farming keywords before LLM is invoked
- **Sandbox Guillotine**: Docker-based patch validation before PR creation (self-correction loop)
- **Familiar Grounds**: Prioritizes previously-merged repos in hunt rounds (higher success rate)
- **Minimax Overdrive**: Global LLM semaphore (4 concurrent) + sliding-window quota tracking (950 req/5h, 9500/7d)

---

## 4. DIRECTORY TREE

```
ContribAI/
├── farm_agent/                     # Main package
│   ├── __init__.py
│   ├── cli/
│   │   ├── main.py                 # CLI entry point (Click-based commands)
│   │   └── tui.py                 # Interactive TUI mode
│   │
│   ├── core/
│   │   ├── config.py               # Pydantic config system + YAML loader
│   │   ├── models.py               # Shared Pydantic models (Repository, Finding, etc.)
│   │   ├── logger.py               # Daily rotating file logger
│   │   ├── middleware.py           # DeerFlow middleware chain
│   │   ├── exceptions.py           # Custom exception classes
│   │   ├── notifier.py             # Telegram push notifications
│   │   ├── quotas.py                # API quota tracking
│   │   ├── retry.py                # Retry utilities
│   │   ├── sandbox.py               # Docker sandbox for patch validation
│   │   ├── rag.py                  # RAG context building
│   │   ├── daily_log.py            # Markdown daily operation log
│   │   ├── leaderboard.py           # PR merge-rate statistics
│   │   └── profiles.py             # Named config profiles
│   │
│   ├── agents/
│   │   └── registry.py             # Agent registry (analysis agents)
│   │
│   ├── analysis/
│   │   ├── analyzer.py             # Main code analyzer (LLM-based)
│   │   ├── strategies.py           # Analysis strategy definitions
│   │   ├── mapper.py                # Language-specific finding mappers
│   │   ├── language_rules.py        # Language-specific analysis rules
│   │   └── skills.py                # Skill definitions for agents
│   │
│   ├── generator/
│   │   ├── engine.py               # Contribution generation engine
│   │   ├── reviewer.py             # Self-review of generated code
│   │   └── scorer.py               # Contribution quality scoring
│   │
│   ├── github/
│   │   ├── client.py               # Async GitHub REST API client
│   │   ├── discovery.py             # Repo discovery via GitHub Search
│   │   └── guidelines.py           # CONTRIBUTING.md / PR template parsing
│   │
│   ├── llm/
│   │   ├── provider.py             # Abstract LLM provider + Minimax implementation
│   │   ├── router.py               # Multi-model task router
│   │   ├── models.py               # Model definitions & capabilities
│   │   ├── context.py              # LLM context management
│   │   └── agents.py              # LLM agent definitions
│   │
│   ├── orchestrator/
│   │   ├── pipeline.py             # Main ContribPipeline orchestrator
│   │   ├── memory.py              # SQLite-backed persistent memory
│   │   └── human.py               # SuperHumanLoop (24/7 stochastic ops)
│   │
│   ├── pr/
│   │   ├── manager.py              # PR creation, compliance checks, DCO signing
│   │   ├── patrol.py               # PRPatrol: review feedback auto-responder
│   │   └── janitor.py             # PRJanitor: garbage PR destroyer
│   │
│   ├── scheduler/
│   │   └── scheduler.py           # APScheduler-based cron runner
│   │
│   ├── issues/
│   │   └── solver.py               # Issue-driven contribution solver
│   │
│   ├── notifications/
│   │   └── notifier.py            # Slack/Discord/Telegram notifications
│   │
│   ├── plugins/
│   │   └── base.py                # Plugin system base classes
│   │
│   ├── templates/
│   │   └── registry.py            # PR description templates
│   │
│   └── tools/
│       └── protocol.py            # LLM tool/function-calling protocol
│
├── tests/                          # Test suite
├── scripts/                        # Utility scripts (CI trap injection, cleanup)
├── docs/                          # Documentation
├── data/                          # Runtime data (memory.db)
├── logs/                          # Daily rotating log files
├── daily_log/                     # Markdown daily operation logs
│
├── config.yaml                    # Runtime configuration
├── config.example.yaml           # Configuration template
├── pyproject.toml                # Python project metadata + dependencies
├── Dockerfile                    # Container build
├── docker-compose.yml            # Container orchestration (scheduler + runner)
├── docker-compose.superhuman.yml  # Superhuman mode composition
└── Makefile                      # Build/run shortcuts
```

---

## 5. CORE MODULES & RESPONSIBILITIES

### CLI Layer (`farm_agent/cli/`)

| File | Responsibility |
|------|----------------|
| `main.py` | Click-based CLI with commands: `run`, `hunt`, `target`, `analyze`, `solve`, `patrol`, `superhuman`, `janitor`, `schedule`, `serve`, `status`, `stats`, `cleanup`, `reset-db`, `config`, `templates`, `profile`, `models`, `vips`, `leaderboard`, `notify-test`, `system-status`, `interactive` |
| `tui.py` | Interactive TUI for browsing and contributing |

### Orchestration Layer (`farm_agent/orchestrator/`)

| File | Responsibility |
|------|----------------|
| `pipeline.py` | **ContribPipeline**: Main coordinator — discover → analyze → generate → PR. Implements Anti-Farming Gate, Hybrid Contribution Router (Issue-First vs Direct PR), Sandbox Guillotine (Docker validation + self-correction), AI Policy check, Maintainer Vibe Check, CI auto-close |
| `memory.py` | **Memory**: SQLite-backed persistent store. Tracks: analyzed repos, submitted PRs, findings cache, run history, PR outcomes, repo preferences, blacklists, API usage quotas, task schedules. Uses WAL mode + periodic checkpointing |
| `human.py` | **SuperHumanLoop**: 24/7 stochastic operational loop. Sets random daily PR quota (1–5), alternates Hunt/Patrol via dice roll (60/40), injects human-like delays, implements Familiar Grounds (prioritizes merged repos), Telegram polling for remote commands, mandatory lunch break (12:00–13:01 UTC) |

### Code Analysis & Generation (`farm_agent/analysis/`, `farm_agent/generator/`)

| File | Responsibility |
|------|----------------|
| `analyzer.py` | **CodeAnalyzer**: LLM-driven code analysis. Fetches repo file tree, reads files, queries LLM for findings. Includes Maintainer Vibe Check, false-positive validation, cross-file RAG via ChromaDB |
| `engine.py` | **ContributionGenerator**: Takes findings + repo context → generates code patches via LLM. Uses search/replace blocks for edits, self-review, adaptive PR titles from guidelines, Gag Order (blocks AI disclosures), Discipline Protocol (blocks scratchpad/note files), Diff Minimizer (rejects oversized patches) |
| `reviewer.py` | Self-review of generated code before submission |
| `scorer.py` | Quality scoring for contributions |

### GitHub Integration (`farm_agent/github/`)

| File | Responsibility |
|------|----------------|
| `client.py` | **GitHubClient**: Full async REST API client. Handles: repo metadata, file tree/content, forking, branching, committing, PR creation, issue creation, PR comments/reviews, CI check runs, combined status, rate limit checking, Secondary Rate Limit handling with backoff, interaction limits check, maintainer vibe analysis, style mimicry (recent merged PRs) |
| `discovery.py` | **RepoDiscovery**: GitHub Search API queries for repo discovery. Filters by language, star range, last activity, topics, requires contributing guide |
| `guidelines.py` | Parses CONTRIBUTING.md and PR templates, extracts commit conventions, required sections, PR title format |

### LLM Layer (`farm_agent/llm/`)

| File | Responsibility |
|------|----------------|
| `provider.py` | **LLMProvider** (abstract) + **MinimaxProvider**: Minimax Chat Completion v2 API. Global semaphore (4 concurrent), proactive 2s think-gap throttling, quota tracking (5h/7d sliding windows), response sanitization (strips `<thinking>` tags) |
| `router.py` | **TaskRouter**: Routes tasks to optimal models (future multi-model) |
| `models.py` | Model definitions (capabilities, tiers, pricing) |

### PR Management (`farm_agent/pr/`)

| File | Responsibility |
|------|----------------|
| `manager.py` | **PRManager**: Fork creation, branch management, file commits with DCO signoff, PR creation, compliance checks (CI, branch protection), post-PR CI polling, auto-close on failure |
| `patrol.py` | **PRPatrol**: Scans open PRs, classifies feedback via LLM (CODE_CHANGE, QUESTION, STYLE_FIX, REJECT, HOSTILE_REJECT), generates + pushes fixes, answers questions, handles CI auto-heal (downloads logs, extracts tracebacks, fixes, validates in Docker sandbox), CLA re-sign, issue assignment detection. Uses human-like WPM typing simulation and notification lag delays |
| `janitor.py` | **PRJanitor**: Evaluates all user PRs via LLM, destroys garbage PRs (docs, formatting, exploratory), spares critical ones |

### Scheduler (`farm_agent/scheduler/`)

| File | Responsibility |
|------|----------------|
| `scheduler.py` | **ContribScheduler**: APScheduler-based cron runner. Parses 5-field cron expressions, executes `ContribPipeline.run()` on schedule with graceful SIGINT/SIGTERM shutdown |

### Supporting Systems

| File | Responsibility |
|------|----------------|
| `core/config.py` | **FarmAgentConfig**: Pydantic root config. Sub-models: GitHub, LLM, Analysis, Contribution, Discovery, Storage, Scheduler, Web, Pipeline, Quota, Notifications, Logging, MultiModel. Token fallback: config file → env vars → `gh auth token` CLI |
| `core/models.py` | Pydantic models: Repository, Issue, Finding, Contribution, FileChange, PRResult, AnalysisResult, RepoContext, etc. |
| `core/notifier.py` | **TelegramNotifier**: Telegram bot polling + push notifications. Handles `/start`, `/status`, `/clean`, `/accept` commands |
| `core/sandbox.py` | **DockerSandbox**: Runs pytest/npm test in Docker to validate patches before PR creation |
| `core/rag.py` | **RepoIndexer**: ChromaDB-based RAG for cross-file semantic search |
| `core/daily_log.py` | **DailyMarkdownLogger**: Appends daily operation logs to `daily_log/` |

---

## 6. DATABASES & CACHING

### SQLite Schema (`data/memory.db`)

**Tables:**

| Table | Purpose |
|-------|---------|
| `analyzed_repos` | Repos scanned — full_name PK, language, stars, analyzed_at, findings count |
| `submitted_prs` | PRs created — repo, pr_number (UNIQUE together), pr_url, title, type, status, branch, fork, ci_fix_attempts, discussion_replies |
| `findings_cache` | Cached analysis findings — id, repo, type, severity, title, file_path, status |
| `run_log` | Pipeline run history — started_at, finished_at, repos_analyzed, prs_created, findings, errors |
| `pr_outcomes` | Learning data — outcome (merged/closed/rejected), feedback, time_to_close_hours |
| `repo_preferences` | Learned per-repo preferences — preferred_types, rejected_types, merge_rate, avg_review_hours |
| `blacklisted_repos` | Blocked repos — reason, associated PR number, blacklisted_at |
| `api_usage_log` | LLM quota tracking — timestamp, provider (indexed for sliding-window queries) |
| `task_schedule` | Non-blocking skip logic — task_key, next_run |

**Operational Details:**
- WAL mode enabled (`PRAGMA journal_mode=WAL`)
- WAL auto-checkpoint at 1000 pages
- 7-day TTL cleanup on `api_usage_log` and `task_schedule`
- Atomic INSERT OR IGNORE for friendly-repos sync (TOCTOU race prevention)
- 5% safety buffer on quota thresholds (950/9500 vs 1000/10000 limits)

---

## 7. ENTRY POINTS & DEPLOYMENT

### CLI Commands

```bash
# Auto-discover repos and contribute
farm_agent run                        # Standard pipeline
farm_agent hunt                       # Aggressive multi-round discovery (default)
farm_agent hunt --mode analysis       # Code analysis only
farm_agent hunt --mode issues        # Issue-solving only
farm_agent hunt --mode both          # Both (default)
farm_agent hunt --dry-run             # Analyze without creating PRs

# Single-repo targeting
farm_agent target <repo_url>          # Target specific repo
farm_agent analyze <repo_url>        # Analyze without contributing
farm_agent solve <repo_url>          # Solve open issues

# PR lifecycle management
farm_agent patrol                     # Check open PRs for review feedback
farm_agent superhuman                 # 24/7 autonomous operation loop
farm_agent janitor                    # Destroy garbage PRs

# Utilities
farm_agent status                     # Show submitted PRs
farm_agent stats                      # Show overall statistics
farm_agent leaderboard                # Merge-rate leaderboard
farm_agent vips                      # VIP roster (merged PR repos)
farm_agent templates                  # List contribution templates
farm_agent models                     # List available LLM models
farm_agent system-status             # Memory, PRs, rate limits
farm_agent cleanup                    # Delete forks with merged/closed PRs
farm_agent reset-db                  # Reset run history (keeps submitted_prs)
farm_agent notify-test                # Send test notification
farm_agent schedule                   # Start scheduler daemon

# Interactive
farm_agent interactive                # TUI mode
farm_agent profile <name>            # Run with named profile
```

### Docker Deployment

```bash
# Scheduler daemon (runs on cron schedule)
docker compose up -d scheduler

# One-shot run with CLI profile
docker compose --profile cli run --rm runner run --dry-run
docker compose --profile cli run --rm runner hunt --time-warp

# Build image
docker build -t worker-daemon:latest .
```

### Configuration

Config file search order: explicit path → `./config.yaml` → `~/.farm_agent/config.yaml`

**Environment variable overrides:**
- `GITHUB_TOKEN` — GitHub API token
- `MINIMAX_API_KEY` — Minimax LLM API key
- `MINIMAX_GROUP_ID` — Minimax group ID
- `TELEGRAM_BOT_TOKEN` — Telegram bot for notifications

---

## 8. CRITICAL ARCHITECTURAL NOTES

### Security & Safety

- **AI Policy Enforcement**: Repos with `AI_POLICY.md` or anti-AI language in `CONTRIBUTING.md` are automatically skipped
- **Interaction Limits Check**: Repos restricting to prior contributors are skipped to avoid 422 errors
- **Maintainer Vibe Check**: LLM-analyzes recent merged-PR comments to detect hostile maintainers; repo is blacklisted on detection
- **Gag Order**: All generated commit messages, PR bodies, and comments are sanitized to remove AI disclosures before posting
- **DCO Signoff**: All commits automatically include `Signed-off-by:` trailer
- **Anti-Farming Gate**: Findings with MEDIUM/LOW/TRIVIAL impact OR farming keywords (docstring, formatting, typo, etc.) are dropped before LLM is invoked — prevents low-value PRs

### Rate Limiting & Quotas

- **GitHub Secondary Rate Limits**: 403 responses with backoff (60s, 120s), proactive 1.5–3s throttling before every API call
- **Minimax Overdrive**: Global 4-concurrent semaphore + sliding-window quota (950 req/5h, 9500/7d)
- **PR Quotas**: Configurable `max_prs_per_day` (default 10), random daily quota 3–10 via SuperHumanLoop
- **Concurrency Caps**: Repo processing capped at `min(max_concurrent, 5)` for Minimax to prevent GitHub thundering herd

### Self-Healing & Auto-Correction

- **Sandbox Guillotine**: Docker-based pytest/npm test validation before PR creation; up to 3 self-correction attempts
- **CI Auto-Heal**: Patrol downloads failing CI logs, extracts tracebacks, generates fixes, validates in Docker, pushes
- **Patch Self-Correction**: LLM receives validation failure output and regenerates with different approach
- **Discussion Reply Limit**: Max 3 replies per PR per cycle; after limit, bot surrenders/closes

### Known Anti-Patterns Blocked

- **Scratchpad files**: New `.md`/`.txt` files in `src/`/`source/`/`app/`/`lib/` are rejected by Discipline Protocol
- **Config/tooling files**: `tsconfig.json`, `.eslintrc`, `package.json`, etc. are in `PROTECTED_META_FILES` and never modified
- **Config/build file findings**: Any finding targeting tsconfig, eslint, webpack, vite, babel, etc. is pre-filtered
- **Full-function rewrites**: Diff Minimizer blocks patches where replace/search ratio > 2 or > 50 lines
- **Duplicate PRs**: Title-similarity and file-overlap checks against both local DB and GitHub API history
