# 🗺️ Project Map — ContribAI v2.6.0

> Complete annotated file tree reflecting the production architecture.
> Last updated: 2026-03-27.

---

## Root Files

| File | Purpose |
|---|---|
| `config.yaml` / `config.example.yaml` | Pydantic-validated YAML configuration (GitHub, LLM, discovery, quotas, notifications) |
| `pyproject.toml` | Package metadata, dependencies, entry points, and tool configs (ruff, pytest) |
| `requirements.txt` | Minimal pip requirements (points to pyproject.toml editable install) |
| `start.bat` | Windows interactive Command Center — menu-driven launcher for all CLI modes |
| `Makefile` | Unix convenience targets (`make test`, `make lint`, `make run`) |
| `Dockerfile` | Standard containerized build |
| `Dockerfile.superhuman` | Multi-stage ARM64/AMD64 build optimized for edge SBCs (Orange Pi, Raspberry Pi) |
| `docker-compose.yml` | Standard Docker Compose deployment |
| `docker-compose.superhuman.yml` | Edge-optimized single-service compose with 512MB RAM cap and log rotation |
| `AGENTS.md` | AI agent configuration and coding conventions |
| `SECURITY.md` | Security policy and responsible disclosure guidelines |

---

## `contribai/` — Core Package (17 subpackages, 62 modules)

### `cli/` — Command-Line Interface

| File | Responsibility |
|---|---|
| `main.py` | Click-based CLI entry point. Commands: `hunt`, `run`, `patrol`, `dashboard`, `superhuman`, `analyze`, `target` |
| `tui.py` | Interactive Terminal UI (Rich-based) for real-time pipeline monitoring |

### `core/` — Shared Infrastructure (11 modules)

| File | Responsibility |
|---|---|
| `config.py` | Pydantic `BaseModel` configuration tree. Root: `ContribAIConfig`. Auto-resolves tokens from env vars and `gh` CLI |
| `models.py` | Domain models: `Repository`, `AnalysisResult`, `Finding`, `Contribution`, `PRResult`, `RepoContext`, `DiscoveryCriteria`, `FileNode`, `Issue` |
| `exceptions.py` | Custom exception hierarchy: `ContribAIError`, `ConfigError`, `GitHubAPIError`, `RateLimitError`, `LLMError`, `LLMRateLimitError` |
| `sandbox.py` | **`DockerSandbox`** — runs linters/tests in ephemeral Docker containers. Shift-left validation before PR creation |
| `notifier.py` | **`TelegramNotifier`** — Interactive Command & Control (C2) center. Uses async Long-Polling for command handling (`/status`, `/rptoday`, `/quota`, `/help`), Command Menu registration (`setMyCommands`), and push notifications via Telegram Bot API. |
| `daily_log.py` | `DailyMarkdownLogger` — generates daily Markdown reports (hunt results, patrol activity, errors) |
| `middleware.py` | DeerFlow-pattern middleware chain (rate limiting, quality gates, daily PR cap enforcement) |
| `logger.py` | Structured logging setup with daily file rotation and configurable retention |
| `retry.py` | Async retry decorators with exponential backoff for API calls |
| `quotas.py` | API usage quota tracking (GitHub calls, LLM tokens, daily limits) |
| `profiles.py` | Contribution profile management (per-language preferences, strategy selection) |
| `leaderboard.py` | Contribution statistics leaderboard (repos analyzed, PRs merged, success rates) |

### `analysis/` — Code Analysis Engine (5 modules)

| File | Responsibility |
|---|---|
| `analyzer.py` | **`CodeAnalyzer`** — orchestrates multi-strategy LLM analysis. Fetches file trees, selects key files, runs analysis prompts |
| `strategies.py` | Analysis strategy definitions: security, code quality, performance, documentation, UI/UX |
| `language_rules.py` | Language-specific analysis rules and patterns (Python, JS/TS, Go, Rust, Java, etc.) |
| `mapper.py` | **`RepoMapper`** — builds project skeleton maps for architectural awareness in LLM prompts |
| `skills.py` | Skill definitions for the analysis agent (DeerFlow pattern) |

### `generator/` — Contribution Generation (2 modules, 902 lines core)

| File | Responsibility |
|---|---|
| `engine.py` | **`ContributionGenerator`** (902 lines) — generates code fixes from findings. Features: agentic tool-calling loop (file reads), style mimicry, project map injection, cross-file pattern detection, **4-tier search/replace matching** (exact → trailing-whitespace-normalized → fully-stripped → indent-agnostic with re-indentation), **patch-correction retry loop** (re-prompts LLM up to 2× on failed patches), self-review gate, and strict verbatim SEARCH block enforcement in prompts |
| `scorer.py` | Contribution quality scorer — rates generated patches on relevance, correctness, and impact |

### `github/` — GitHub Integration (3 modules, 752 lines core)

| File | Responsibility |
|---|---|
| `client.py` | **`GitHubClient`** (752 lines) — full GitHub REST API v3 wrapper. 40+ methods. Features **Git Timestamp Spoofing** (backdating `author.date` 15-45m) for local-coding illusion, `check_interaction_limits` radar to evade 422 errors, and **Auto-SHA fetch** in `create_or_update_file()`. |
| `discovery.py` | **`RepoDiscovery`** — GitHub search API integration. Builds queries from `DiscoveryCriteria`, handles pagination, relaxed merge-friendly filtering |
| `guidelines.py` | `fetch_repo_guidelines()` — extracts CONTRIBUTING.md, PR templates, commit conventions, and AI policy detection |

### `issues/` — Issue Solving

| File | Responsibility |
|---|---|
| `solver.py` | **`IssueSolver`** — deep multi-file issue planning. Fetches issue context, generates solution plans, produces multi-file patches |

### `llm/` — LLM Provider Layer (5 modules)

| File | Responsibility |
|---|---|
| `provider.py` | **`LLMProvider`** (abstract) + **`MinimaxProvider`** (sole implementation). REST API client for MiniMax M2.7 with rate limit handling and tool-calling support |
| `router.py` | Task-based model routing (analysis → model, code_gen → model). Currently single-model passthrough |
| `agents.py` | DeerFlow-pattern agent definitions (analyzer agent, generator agent, reviewer agent) |
| `context.py` | Context building utilities — `build_generator_system_prompt()`, style mimicry extraction via `extract_style_guide()` from recent merged PRs |
| `models.py` | LLM-specific data models (prompt templates, response parsing, tool call structures) |

### `orchestrator/` — Pipeline Orchestration (3 modules)

| File | Responsibility |
|---|---|
| `pipeline.py` | **`ContribPipeline`** — main orchestrator. Coordinates discover→analyze→generate→sandbox→PR flow. Implements the "Soft Fetch Throttler" (micro-sleeps during file fetching) and Global PR Lock (`_human_typing_lock`) to create a human bottleneck and prevent concurrent PR pushes. |
| `human.py` | **`SuperHumanLoop`** — stochastic daily routine. Random PR targets (1-5/day), Mandatory Lunch Break, `LLMRateLimitError` 1-hour cooldown sleeps. Gamification Phase 1: State Emitter broadcasts (`working`, `sleeping`, `coffee_break`) to WebSockets. |
| `memory.py` | **`Memory`** (561 lines) — SQLite persistence. 9 tables: `repos`, `prs`, `findings`, `run_log`, `pr_outcomes`, `repo_preferences`, `blacklist`, `api_usage_log`, `ci_fix_attempts`. Tracks CI auto-heal counters, discussion reply counts, Minimax sliding-window quota (1000/5h, 10000/7d) |

### `pr/` — Pull Request Management (2 modules, 1860 lines core)

| File | Responsibility |
|---|---|
| `manager.py` | **`PRManager`** — git operations (clone, branch, commit, push), PR creation via GitHub API, DCO sign-off |
| `patrol.py` | **`PRPatrol`** (1860 lines) — Deep Turing-passable feedback engine. Features Notification Lag (10m-2h), Probabilistic Ghosting (10% chance), Contextual Small Talk, and WPM-based typing simulation. Classifies maintainer comments, auto-heals CI with sandbox validation, handles CLA re-signing, and includes Fail-safe killswitches. |

### `scheduler/` — Background Scheduling

| File | Responsibility |
|---|---|
| `scheduler.py` | Cron-based scheduler for periodic pipeline runs |

### `tools/` — Tool Registry

| File | Responsibility |
|---|---|
| `protocol.py` | DeerFlow-pattern tool definitions. `GitHubTool` (file reader via GitHub API), `READ_FILE_TOOL_SCHEMA` (OpenAI-compatible function calling schema) |

### `web/` — Web Dashboard (4 modules)

| File | Responsibility |
|---|---|
| `server.py` | FastAPI-based REST API server with a new WebSocket endpoint (`/ws/bot-state`) for real-time frontend gamification |
| `dashboard.py` | Web dashboard routes (stats, PR history, run logs) |
| `auth.py` | API key authentication middleware |
| `webhooks.py` | GitHub webhook handler (PR events, review events) |

### `agents/` — Agent Registry

| File | Responsibility |
|---|---|
| `registry.py` | DeerFlow-pattern agent registry — registers and routes to specialized agents |

### `plugins/` — Plugin System

| File | Responsibility |
|---|---|
| `base.py` | Plugin base class and infrastructure for custom analysis strategies |

### `notifications/` — Notification Channels

| File | Responsibility |
|---|---|
| `notifier.py` | Multi-channel notification infrastructure (Telegram primary) |

### `templates/` — PR & Commit Templates

| File | Responsibility |
|---|---|
| (7 templates) | Jinja2/Markdown templates for PR descriptions, commit messages, and issue references |

---

## `tests/` — Test Suite (40 files)

| Directory | Coverage |
|---|---|
| `unit/` (33 files) | Unit tests for: pipeline, superhuman loop, memory, patrol, sandbox, discovery, generator, github client, LLM provider, minimax quota, config, models, middleware, registry, protocol, mapper, context, style mimicry, issue solver, scorer, strategies, skills, CLI, and phase regression tests |
| `integration/` (3 files) | Integration tests: pipeline end-to-end, sandbox lifecycle, sandbox validation loop |
| `conftest.py` | Shared pytest fixtures (mock configs, mock clients, test data factories) |

---

## Key Data Flow

```
config.yaml
    ↓
ContribAIConfig (Pydantic)
    ↓
SuperHumanLoop._do_hunt()        ← stochastic daily PR target (1-5)
    ↓
ContribPipeline.hunt()
    ├── RepoDiscovery.discover()          → GitHub Search API
    ├── Memory.has_analyzed()             → SQLite check
    ├── CodeAnalyzer.analyze()            → MiniMax M2.7
    ├── ContributionGenerator.generate()  → MiniMax M2.7 (agentic loop)
    │       ├── _agentic_generate()       → tool calls (read_file)
    │       ├── _parse_changes()          → 4-tier matching engine
    │       └── patch-correction retry    → up to 2 LLM re-prompts
    ├── DockerSandbox.run_in_sandbox()    → Docker API (shift-left test)
    └── PRManager.create_pr()             → GitHub API + git push
            ↓
    TelegramNotifier.send_message()       → Telegram Bot API
            ↓
    Memory.record_pr()                    → SQLite persist

SuperHumanLoop._do_patrol()
    ↓
PRPatrol.patrol()
    ├── _collect_feedback()               → GitHub PR comments/reviews
    ├── _classify_feedback()              → MiniMax M2.7 (YAML classification)
    ├── _handle_code_fix()                → push code fix to fork
    ├── _handle_question()                → post human-like reply
    ├── _check_ci_failures()              → 2-pass infra filter + auto-heal
    │       ├── CI_INFRA_IGNORE_PATTERNS  → skip Vercel/secrets/CLA/etc.
    │       └── _handle_ci_failure()      → sandbox-validated CI fix
    ├── _handle_cla_recheck()             → auto re-sign CLA
    └── Fail-safe killswitches            → close PR + blacklist + Telegram
```
