# 🗺️ Project Map — ContribAI v2.5.0

> Complete annotated file tree reflecting the final production architecture.

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

---

## `contribai/` — Core Package

### `cli/` — Command-Line Interface

| File | Responsibility |
|---|---|
| `main.py` | Click-based CLI entry point. Commands: `hunt`, `run`, `patrol`, `dashboard`, `superhuman`, `analyze`, `target` |
| `tui.py` | Interactive Terminal UI (Rich-based) for real-time pipeline monitoring |

### `core/` — Shared Infrastructure

| File | Responsibility |
|---|---|
| `config.py` | Pydantic `BaseModel` configuration tree. Root: `ContribAIConfig`. Auto-resolves tokens from env vars and `gh` CLI |
| `models.py` | Domain models: `Repository`, `AnalysisResult`, `Finding`, `Contribution`, `PRResult`, `RepoContext`, `DiscoveryCriteria` |
| `exceptions.py` | Custom exception hierarchy: `ContribAIError`, `ConfigError`, `GitHubAPIError`, `LLMError`, `LLMRateLimitError` |
| `sandbox.py` | **`DockerSandbox`** — runs linters/tests in ephemeral Docker containers. Shift-left validation before PR creation |
| `notifier.py` | **`TelegramNotifier`** — async, non-blocking push notifications via Telegram Bot API |
| `daily_log.py` | `DailyMarkdownLogger` — generates daily Markdown reports (hunt results, patrol activity, errors) |
| `middleware.py` | DeerFlow-pattern middleware chain (rate limiting, quality gates, daily PR cap enforcement) |
| `logger.py` | Structured logging setup with daily file rotation and configurable retention |
| `retry.py` | Async retry decorators with exponential backoff for API calls |
| `quotas.py` | API usage quota tracking (GitHub calls, LLM tokens, daily limits) |
| `profiles.py` | Contribution profile management (per-language preferences, strategy selection) |
| `leaderboard.py` | Contribution statistics leaderboard (repos analyzed, PRs merged, success rates) |

### `analysis/` — Code Analysis Engine

| File | Responsibility |
|---|---|
| `analyzer.py` | **`CodeAnalyzer`** — orchestrates multi-strategy LLM analysis. Fetches file trees, selects key files, runs analysis prompts |
| `strategies.py` | Analysis strategy definitions: security, code quality, performance, documentation, UI/UX |
| `language_rules.py` | Language-specific analysis rules and patterns (Python, JS/TS, Go, Rust, Java, etc.) |
| `mapper.py` | Repository structure mapper — builds context maps for LLM prompts |
| `skills.py` | Skill definitions for the analysis agent (DeerFlow pattern) |

### `generator/` — Contribution Generation

| File | Responsibility |
|---|---|
| `engine.py` | **`ContributionGenerator`** — generates code fixes from findings. Respects repo guidelines, commit conventions, and style mimicry |
| `scorer.py` | Contribution quality scorer — rates generated patches on relevance, correctness, and impact |

### `github/` — GitHub Integration

| File | Responsibility |
|---|---|
| `client.py` | **`GitHubClient`** — full GitHub REST API v3 wrapper. Repos, PRs, issues, files, commits, reactions, check runs, CI logs |
| `discovery.py` | **`RepoDiscovery`** — GitHub search API integration. Builds queries from `DiscoveryCriteria`, handles pagination |
| `guidelines.py` | `fetch_repo_guidelines()` — extracts CONTRIBUTING.md, PR templates, commit conventions, and AI policy detection |

### `issues/` — Issue Solving

| File | Responsibility |
|---|---|
| `solver.py` | **`IssueSolver`** — deep multi-file issue planning. Fetches issue context, generates solution plans, produces multi-file patches |

### `llm/` — LLM Provider Layer

| File | Responsibility |
|---|---|
| `provider.py` | **`LLMProvider`** (abstract) + **`MinimaxProvider`** (sole implementation). REST API client for MiniMax M2.7 with rate limit handling |
| `router.py` | Task-based model routing (analysis → model, code_gen → model). Currently single-model passthrough |
| `agents.py` | DeerFlow-pattern agent definitions (analyzer agent, generator agent, reviewer agent) |
| `context.py` | Context building utilities — style mimicry extraction from recent merged PRs, prompt assembly |
| `models.py` | LLM-specific data models (prompt templates, response parsing) |

### `orchestrator/` — Pipeline Orchestration

| File | Responsibility |
|---|---|
| `pipeline.py` | **`ContribPipeline`** — main orchestrator. Modes: `run()`, `hunt()`, `run_single()`. Coordinates discover→analyze→generate→PR flow |
| `human.py` | **`SuperHumanLoop`** — stochastic daily routine. Random PR targets, hunt/patrol interleaving, dynamic sleep, Vietnamese developer persona |
| `memory.py` | **`Memory`** — SQLite persistence. Tables: `repos`, `prs`, `findings`, `run_log`, `pr_outcomes`, `repo_preferences`, `blacklist`, `api_usage_log`. Minimax quota tracking |

### `pr/` — Pull Request Management

| File | Responsibility |
|---|---|
| `manager.py` | **`PRManager`** — git operations (clone, branch, commit, push), PR creation via GitHub API, DCO sign-off |
| `patrol.py` | **`PRPatrol`** — 1795-line human-persona feedback engine. Classifies maintainer comments (fix_needed, question, hostile, approval). Pushes code fixes, answers questions, auto-heals CI, handles CLA re-signing. Fail-safe killswitches (3 CI retries, 3 discussion replies → graceful surrender + blacklist) |

### `scheduler/` — Background Scheduling

| File | Responsibility |
|---|---|
| `scheduler.py` | Cron-based scheduler for periodic pipeline runs |

### `tools/` — Tool Registry

| File | Responsibility |
|---|---|
| `protocol.py` | DeerFlow-pattern tool definitions (file reader, code search, repo browser) |

### `web/` — Web Dashboard

| File | Responsibility |
|---|---|
| `server.py` | FastAPI-based REST API server |
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
| (extensible) | Plugin infrastructure for custom analysis strategies |

### `notifications/` — Notification Channels

| File | Responsibility |
|---|---|
| (extensible) | Multi-channel notification infrastructure (Telegram primary, Slack/Discord stubs) |

### `templates/` — PR & Commit Templates

| File | Responsibility |
|---|---|
| (7 templates) | Jinja2/Markdown templates for PR descriptions, commit messages, and issue references |

---

## `tests/` — Test Suite

| Directory | Coverage |
|---|---|
| `unit/` | Unit tests for pipeline, superhuman loop, memory, patrol, sandbox, discovery, generator |
| `integration/` | Integration tests with mocked GitHub/LLM APIs |
| `conftest.py` | Shared pytest fixtures (mock configs, mock clients) |

---

## Key Data Flow

```
config.yaml
    ↓
ContribAIConfig (Pydantic)
    ↓
SuperHumanLoop._do_hunt()
    ↓
ContribPipeline.hunt()
    ├── RepoDiscovery.discover()     → GitHub Search API
    ├── Memory.has_analyzed()        → SQLite check
    ├── CodeAnalyzer.analyze()       → MiniMax M2.7
    ├── ContributionGenerator()      → MiniMax M2.7
    ├── DockerSandbox.run_in_sandbox() → Docker API
    └── PRManager.create_pr()        → GitHub API + git push
            ↓
    TelegramNotifier.send_message()  → Telegram Bot API
            ↓
    Memory.record_pr()               → SQLite persist
```
