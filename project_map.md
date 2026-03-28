# ContribAI — Source Code Map & Architectural Reference

**Status**: Single Source of Truth (SSOT) | **Last Updated**: 2026-03-28
**Purpose**: Exhaustive code anatomy, execution flows, data models, and edge case protocols.

---

## 1. Directory & File Anatomy

### `farm_agent/`

#### `agents/registry.py`
`AgentRegistry` — Dynamic sub-agent registry supporting registration, retrieval, and middleware chaining for each agent type. Ships with built-in stubs: `AnalyzerAgent`, `GeneratorAgent`, `PatrolAgent`, `ComplianceAgent`, `IssueSolverAgent`. Each stub logs "Not implemented" and returns an empty list by default; replaced by real implementations via registration.

#### `analysis/analyzer.py`
`CodeAnalyzer` — Executes 7 concurrent analysis strategies (security, code_quality, docs, ui_ux, performance, refactor, testing) using `asyncio.gather`. Each strategy runs its own LLM prompt through `MinimaxProvider`. `ANALYZABLE_EXTENSIONS` filters to programming files (.py, .js, .ts, .jsx, .tsx, .go, .rs, .java, .cpp, .c, .h, .hpp, .cs). Each prompt embeds Anti-Farming rules (drop LOW/MEDIUM+docstring/typo/format/kebab-case-only) and Anti-False-Positive rules (require exact line references, reject hypotheticals). `check_maintainer_vibe()` queries recent PR comments via GitHub API and classifies as WELCOMING/STRICT/HOSTILE using LLM; HOSTILE triggers permanent repo blacklist. `_parse_findings()` tries YAML block parsing first, falls back to regex extraction.

#### `analysis/skills.py`
`SkillsEngine` — Generates structured LLM prompts for each of the 7 analysis strategies. Each skill defines its own system prompt, file targeting rules, and result schema. Used exclusively by `CodeAnalyzer`.

#### `analysis/loc_counter.py`
`LocCounter` — Heuristic-based file size checker. Returns `True` (skip file) if: `loc > MAX_LOC` (configurable, default 2000), `is_binary`, or `is_test_file` (test files often have dense assertions that confuse analyzers). Prevents the LLM from wasting context on massive auto-generated files.

#### `cli/main.py`
`main()` — Click CLI entry point with 20+ subcommands: `run` (hunt pipeline), `target` (single repo), `hunt` (discovery → analyze → generate), `patrol` (PR review loop), `superhuman` (24/7 daemon), `analyze` (static only), `solve` (issue solver), `status` (today's PR count + quota), `stats` (merge rate, repo prefs), `cleanup` (remove old forks/branches), `config` (validate config), `serve` (FastAPI), `schedule` (cron scheduler), `templates` (PR template library), `profile` (select model profile), `models` (list available models), `interactive` (TUI), `leaderboard` (top repos by merge rate), `notify-test` (webhook test), `system-status` (full diagnostics). Rich-colored terminal output with emoji prefixes.

#### `cli/tui.py`
`ContribTUI` — Rich-based interactive terminal interface for `interactive` command. Uses `Live` display for real-time updates, `Table` for repo findings, `Panel` for status. Handles keyboard interrupts gracefully.

#### `core/config.py`
`FarmAgentConfig` — Root Pydantic model with 13 sub-configs. `GitHubConfig` (token, max_prs_per_day, fork_count), `DiscoveryConfig` (stars_range, topics_filter, min_issues), `PipelineConfig` (max_concurrent_repos, max_ci_retries, max_discussion_replies, max_patch_retries, commit_convention, protected_file_patterns, skip_extensions), `ModelsConfig` / `MultiModelConfig` (task-based model routing enabled/disabled), `SandboxConfig` (timeout, mem_limit, network_disabled, retries), `QuotaConfig` (github_requests_per_day, llm_tokens_per_day), `MemoryConfig` (db_path), `ScheduleConfig` (hunt_cron, patrol_cron), `NotificationsConfig` (telegram_token, telegram_chat_ids, slack_webhook, discord_webhook), `QualityConfig` (min_confidence, min_impact), `PatrolConfig` (max_review_per_repo, max_daily_reviews), `IssueSolverConfig` (enabled, label_groups), `SuperHumanConfig` (enabled, telegram_poll_interval). All secrets fall back to environment variables. `validate_config()` ensures required fields are non-null.

#### `core/exceptions.py`
Exception hierarchy: `FarmAgentError` → `RateLimitError` (GitHub 403 with remaining==0), `LLMRateLimitError` (Minimax quota exceeded), `SandboxError` (Docker exec failed), `AnalysisError`, `GenerationError`, `PatrolError`, `ComplianceError`, `BlacklistedError` (repo is blacklisted). All are instantiable with a `detail: str` field.

#### `core/leaderboard.py`
`Leaderboard` — Tracks and ranks repos by merge rate. `update()` records a PR outcome, `get_top()` returns sorted list. Persisted via JSON file at `farm_agent_data/leaderboard.json`.

#### `core/models.py`
All shared Pydantic models and enums.

**Enums**: `ImpactLevel` (CRITICAL, HIGH, MEDIUM, LOW, TRIVIAL), `FeedbackAction` (CODE_CHANGE, QUESTION, STYLE_FIX, APPROVE, REJECT, HOSTILE_REJECT, ALREADY_HANDLED, CONVERSATIONAL, FOLLOW_UP), `ContributionType` (SECURITY_FIX, CODE_QUALITY, README_FIX, UI_UX_FIX, PERFORMANCE_OPT, FEATURE_ADD, REFACTOR), `Severity` (CRITICAL, HIGH, MEDIUM, LOW, INFO), `PRStatus` (OPEN, MERGED, CLOSED, UNKNOWN).

**Models**: `FileChange` (path, original_content, new_content, is_new_file), `RepoContext` (repo, branch, file_contents dict, relevant_files dict, commit_history, recent_prs, guidelines), `Finding` (id, type, severity, impact, title, description, file_path, line_range, confidence, suggestion, priority_score). `priority_score` = severity_weights × confidence × impact_weights (computed at parse time).

#### `core/profiles.py`
`ModelProfile` — Named model configurations (e.g., "balanced", "fast", "smart"). `load_profile()` / `save_profile()` via JSON. Used by the `profile` CLI subcommand.

#### `core/quotas.py`
`UsageTracker` — In-memory per-day counters for GitHub API requests and LLM tokens. `check()` raises `QuotaExceededError` if limits are hit. Resets counters on local date change (not UTC — uses OS timezone). Tracks `llm_tokens_used`, `github_requests_made`.

#### `core/middleware.py`
`PipelineContext` — Dataclass carrying `repo`, `finding`, `changes`, `error`, `retry_count`, `metadata`. `MiddlewareChain` — Pluggable middleware executor. Built-ins: `RateLimitMiddleware` (checks `UsageTracker`), `ValidationMiddleware` (Pydantic validation), `RetryMiddleware` (exponential backoff: 1s, 2s, 4s...), `DCOMiddleware` (ensures DCO signoff on commits), `QualityGateMiddleware` (blocks if confidence < threshold).

#### `generator/engine.py`
`ContributionGenerator` — Takes `Finding` + `RepoContext`, calls LLM with structured prompt to produce code patches. `MAX_TOOL_CALLS=3` (LLM is told to solve in ≤3 passes). Prompt includes cross-file context (finds up to 3 other files with the same bug pattern via `_find_cross_file_instances()`). `_parse_changes()` — 4-pass matching: (1) exact string, (2) whitespace-normalized, (3) stripped, (4) indentation-agnostic line-by-line with re-indentation. `max_patch_retries=2`. Diff Minimizer: rejects edits where replacement >30 lines and search <5 lines (hallucination guard). `_self_review()` asks LLM APPROVE/REJECT on the generated diff; REJECT discards the contribution. `_generate_commit_message()` uses conventional commit format. `_generate_branch_name()` uses semantic prefixes (fix/, feat/, perf/, etc.) without tool branding. `_generate_pr_title()` adapts to repo guidelines if available.

#### `generator/scorer.py`
`Scorer` — Calculates `priority_score` for each `Finding` using severity × confidence × impact weights. Used by the pipeline to sort findings before generation. `score_finding()` is the main entry.

#### `github/client.py`
`GitHubAPI` (aliased as `GH`) — Async httpx wrapper with token auth. **Rate limit handling**: 403 with `remaining==0` → raise `RateLimitError` immediately. 403 abuse detection (no remaining info) → retry with 60s backoff, then 120s. **Key methods**: `get_repo()` (fetch repo metadata), `list_issues()` (open issues with pagination), `create_fork()`, `create_or_update_file()` (auto-fetches SHA, appends DCO signoff line, sets author timestamp jittered 15-45 min before push), `create_pull_request()`, `get_pull_request()`, `get_comments()`, `post_comment()`, `get_check_run_log()` (follows redirect to S3/GHA artifact URL), `fetch_recent_maintainer_comments()` (for vibe check, last 10 comments from humans), `get_recent_merged_prs()` (for style mimicry). `search_repos()` — GitHub search API with star range, topics, language filters.

#### `github/discovery.py`
`RepoDiscovery` — Star-range-based repo scoring (config `discovery.stars_range`, Shark Tank: 1000-20000). `score_repo()` awards points: star sweet-spot 100-5000 (+3), open issues (+3), has license (+1), has contributing guide (+2), fork count 10-500 (+1.5). `discover()` yields scored repos sorted by score descending. `filter_by_language()` applies optional language filter.

#### `github/guidelines.py`
`Guidelines` — Pydantic model with `has_guidelines`, `preferred_types`, `forbidden_types`, `commit_style`, `pr_title_format`, `scope_rules`. `fetch_guidelines()` hits the GitHub API to fetch CONTRIBUTING.md and parses it via LLM. `adapt_pr_title()` adapts the PR title to repo conventions. `extract_scope_from_path()` extracts scope from file path.

#### `issues/solver.py`
`IssueSolver` — `fetch_solvable_issues()` queries repos by label groups (e.g., `["good first issue", "help wanted"]`). `solve_issue_deep()` uses `RepoMapper` to build project skeleton, then LLM to generate multi-file `---FILE---` block solutions. Handles issue assignees and posts solution as a PR linked to the issue. `RepoMapper` maps directory structure and build system files.

#### `llm/models.py`
`Model` — Pydantic model for a single LLM (provider, name, temperature, max_tokens). `MultiModelConfig` for task-based routing.

#### `llm/agents.py`
`Agent` — Wraps an LLM with system prompt and tool definitions. `execute()` runs the agent loop. Used by the agent registry.

#### `llm/router.py`
`Router` — Routes tasks to the appropriate model based on `MultiModelConfig` task-to-model mapping. Falls back to the default model if no routing rule matches.

#### `notifications/notifier.py`
`Notifier` — Persistent `httpx` async client. `send_telegram()` / `send_slack()` / `send_discord()` fire webhook payloads. `send_diff()` posts a formatted diff to Telegram with file-level chunking (Telegram 4096 char limit). All sends are fire-and-forget with error logging. `TelegramNotifier` background poller is started/stopped as a separate task.

#### `orchestrator/human.py`
`SuperHumanLoop` — Stochastic 24/7 daemon. CRIT-01: `DB_LEVEL_QUOTA_CHECK` inside `_do_hunt()` — calls `get_today_pr_count()` and `get_stats()` to compare against `ABSOLUTE_MAX_PRS_PER_DAY=12`. CRIT-02: Local timezone lunch check — `local_now.hour == 12` uses OS timezone (not UTC+7). `HUNT_WEIGHT=0.60 / PATROL_WEIGHT=0.40` for mode selection. `HUMAN_THOUGHTS` — Vietnamese persona dictionary (randomly selected each iteration for Telegram context updates). Telegram poller: `PollingConsumer` with 5s poll interval, crash-restart callback, graceful stop on SIGINT/SIGTERM. Human-like WPM delay via `simulate_human_wpm()`. Random PR target: `random_daily_pr_target()` varies between 1 and `config.github.max_prs_per_day`.

#### `orchestrator/memory.py`
`Memory` — SQLite-backed persistent memory using aiosqlite. WAL journal mode enabled. 8 tables: `analyzed_repos` (full_name PK, language, stars, analyzed_at, findings, metadata JSON), `submitted_prs` (id, repo, pr_number, pr_url, title, type, status, branch, fork, created_at, updated_at, ci_fix_attempts, discussion_replies), `findings_cache` (id, repo, type, severity, title, file_path, status, created_at), `run_log` (id, started_at, finished_at, repos_analyzed, prs_created, findings, errors, metadata JSON), `pr_outcomes` (id, repo, pr_number, pr_url, pr_type, outcome, feedback, time_to_close_hours, recorded_at), `repo_preferences` (repo PK, preferred_types JSON, rejected_types JSON, merge_rate, avg_review_hours, notes, updated_at), `blacklisted_repos` (repo PK, reason, pr_number, blacklisted_at), `api_usage_log` (id, timestamp, provider). `check_and_record_llm_quota()` — sliding-window rate limiter for Minimax (1000 req/5h, 10000 req/7 days, 95% safety buffer). Periodic cleanup deletes entries older than 7 days every 1 hour. Auto-migration adds missing columns (`ci_fix_attempts`, `discussion_replies`) to existing databases.

#### `orchestrator/pipeline.py`
`ContribPipeline` — Main hunting pipeline. `run()` drives discovery → repos; `hunt()` runs `run_single()` per repo concurrently. `run_single()` calls `_process_repo()` on each discovered repo. `analyze_only()` skips PR creation.

**`PROTECTED_META_FILES`**: CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE*, FUNDING.yml, CODEOWNERS, .github/CODEOWNERS, SECURITY.md, SUPPORT.md, MAINTAINERS.md, CONTRIBUTORS.md — never modified.

**`SKIP_EXTENSIONS`**: .md, .txt, .rst, .yml, .yaml, .toml, .cfg, .ini, .json, .lock, .sum, .map — never analyzed.

**`_process_repo()` — 10-stage per-repo flow**:
1. AI policy check (is repo farm-agent or AI-hunting-target?)
2. Interaction limit check (has repo been analyzed too recently?)
3. Maintainer vibe check (LLM classify comments as WELCOMING/STRICT/HOSTILE → blacklist if HOSTILE)
4. Guidelines fetch (CONTRIBUTING.md parsed into `Guidelines`)
5. Analyze (7 concurrent strategies via `CodeAnalyzer`)
6. Pre-filter (drop findings without exact file_path or line_range)
7. Anti-farming gate (only CRITICAL/HIGH impact pass; LOW/MEDIUM + farming keywords → dropped)
8. Duplicate detection (skip if `has_analyzed()` from memory)
9. Validate findings (confidence ≥ `config.quality.min_confidence`, impact ≥ `config.quality.min_impact`)
10. Generate (for each validated finding → `ContributionGenerator.create_contribution()`)
    - Sandbox validation (`DockerSandbox.execute()` 60s timeout, exit code 137 = SIGKILL, 3 retries)
    - Human delay (WPM simulation before git push)
    - PR creation (`GitHubAPI.create_pull_request()`)
    - Compliance check (`PRManager.check_compliance_and_fix()`)
    - CI wait (`PRManager.wait_for_ci()` up to `max_ci_retries`)
11. Record to memory

#### `pr/manager.py`
`PRManager` — Full PR lifecycle. `create_pr()` calls `create_pull_request()` → records in memory. `check_ci_status()` polls check runs, returns aggregated status. `wait_for_ci()` polls every 15s up to `max_ci_retries`. `auto_check_pr_template()` counts deterministic checkboxes (unchecked = 0). `check_compliance_and_fix()` — after 15s delay, fetches bot comments (coderabbitai, copilot, github-actions, dependabot, renovate, sweep-ai), auto-fixes title/issue-ref, signs CLA. `_human_branch_name()` generates semantic prefixes (fix/, feat/, perf/, docs/, refactor/, improve/) without any tool branding. `_handle_cla_signing()` — CLAAssistant: bot edits CLA.yml file directly to add author; EasyCLA: posts "I have signed the CLA" comment.

#### `pr/patrol.py`
`PRPatrol` — Patrol loop for reviewing and interacting with existing PRs. `REVIEW_BOT_LOGINS`: coderabbitai, copilot, github-actions, dependabot, renovate, sweep-ai, SocketRT, ResolverBot, Mounted.ai, Pull, Lego, Terra, Octomerge, Mergify, Auto-PR. `CI_INFRA_IGNORE_PATTERNS`: vercel, cloudflare, pages, netlify, codecov, cla/, license/, dependabot/, renovate/. `GITHUB_REPLIES` — human-like response dictionary keyed by action type. `review_and_respond()` — WPM delay simulation, generates LLM response using `GITHUB_REPLIES` as injection examples. `should_surrender()` — if `max_review_per_repo` exhausted, posts farewell comment and exits. Handles issue-like comments (links existing issues to PR). Maintains `reviewed_prs` set to avoid re-reviewing.

#### `scheduler/scheduler.py`
`ContribScheduler` — APScheduler wrapper using `AsyncIOScheduler` with `CronTrigger`. `add_hunt_job()` / `add_patrol_job()` schedule recurring tasks. SIGINT/SIGTERM graceful shutdown (waits for running jobs via `shutdown(wait=True)`). Used by the `schedule` CLI subcommand.

#### `tools/protocol.py`
`ToolRegistry` — Registers and executes tools. `GitHubTool` (BLOCKED_EXTENSIONS: .zip, .png, .jpg, .gif, .pdf; MAX_FILE_SIZE=100000 bytes; methods: read_file, search_code, list_directory, get_file_history). `READ_FILE_TOOL_SCHEMA` — JSON schema for the read_file tool used in function calling. `LLMTool` — wrapper for LLM calls. Tools can be registered and retrieved by name.

#### `web/api.py`
`APIRouter` — FastAPI router with endpoints: `GET /repos`, `GET /repos/{owner}/{repo}`, `POST /analyze`, `GET /prs`, `GET /prs/{pr_id}`, `POST /notify`. Mounted by `app.py`.

#### `web/app.py`
`create_app()` — FastAPI factory. Mounts `APIRouter` at `/api`. Includes lifespan context manager for startup/shutdown. CORS middleware configured.

#### `web/dashboard.py`
`Dashboard` — Rich HTML dashboard served at `/`. Lists analyzed repos, submitted PRs, stats. Rendered as aiohttp response.

---

### `tests/`

#### `tests/test_analyzer.py`
Unit tests for `CodeAnalyzer`. Tests YAML finding parsing, regex fallback, empty results handling.

#### `tests/test_generator.py`
Unit tests for `ContributionGenerator`. Tests patch parsing (exact, fuzzy, indentation-agnostic), Diff Minimizer rejection, self-review loop, commit/PR title generation.

#### `tests/test_memory.py`
Unit tests for `Memory`. Tests `record_pr`, `update_pr_status`, `has_analyzed`, `get_today_pr_count`, `blacklist_repo`, `api_usage_log` sliding window quota.

#### `tests/test_middleware.py`
Unit tests for `MiddlewareChain`. Tests `RateLimitMiddleware`, `ValidationMiddleware`, `RetryMiddleware`, `DCOMiddleware`.

#### `tests/test_discovery.py`
Unit tests for `RepoDiscovery`. Tests star-range filtering, repo scoring, `discover()` ordering.

#### `tests/test_patrol.py`
Unit tests for `PRPatrol`. Tests surrender logic, WPM delay, `GITHUB_REPLIES` lookup, `CI_INFRA_IGNORE_PATTERNS`.

#### `tests/test_compliance.py`
Unit tests for `PRManager`. Tests checkbox counting, title formatting, branch naming (no tool branding), CLA detection (CLAAssistant vs EasyCLA).

---

### Root Files

#### `Dockerfile.superhuman`
Multi-stage build on `python:3.11-slim-bookworm`. Installs `git` and `docker.io`. No code caching layer. CMD `["farm_agent", "superhuman"]`.

#### `docker-compose.superhuman.yml`
Single service `agent`. Builds from `Dockerfile.superhuman`. Container name `farm_agent_core`. `restart: unless-stopped`. Mounts `config.yaml` (ro), `farm_agent_data` (/root/.farm_agent:rw), `logs` (/app/logs:rw), and Docker socket (`/var/run/docker.sock:rw`). Timezone set to `Asia/Ho_Chi_Minh`.

#### `config.example.yaml`
Full 13-section config template. Key values: `github.max_prs_per_day: 10`, `discovery.stars_range: [1000, 20000]`, `pipeline.max_concurrent_repos: 3`, `pipeline.max_ci_retries: 3`, `multi_model.enabled: false`.

#### `pyproject.toml`
Hatchling build config. Dependencies: `httpx`, `pydantic`, `pydantic-settings`, `aiosqlite`, `docker`, `APScheduler`, `click`, `rich`, `PyYAML`, `ruff`, `pytest`, `fastapi`, `uvicorn`. Scripts: `farm_agent`.

#### `.pre-commit-config.yaml`
Pre-commit hooks: `ruff` (lint), `ruff-format` (format), `mypy` (type check), `pytest` (unit tests). Excludes `tests/`, `farm_agent_data/`, `logs/`.

---

## 2. Core Execution Flows

### SuperHuman Loop (`farm_agent/orchestrator/human.py`)

```
Entry: farm_agent superhuman
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  SuperHumanLoop.run()  [infinite while True]           │
│                                                         │
│  CRIT-01: DB-level quota check                          │
│    get_today_pr_count() + get_stats()                  │
│    if count >= ABSOLUTE_MAX_PRS_PER_DAY (12):          │
│       sleep 5 min, continue                            │
│                                                         │
│  Mode selection: random() < HUNT_WEIGHT (0.60)          │
│    → HUNT  (60%): _do_hunt()                            │
│    → PATROL (40%): _do_patrol()                         │
│                                                         │
│  CRIT-02: Local timezone lunch                          │
│    if local_now.hour == 12:  # OS timezone, not UTC    │
│       lunch delay (30-90 min)                           │
│                                                         │
│  Human-like delays:                                     │
│    Productive:  30-90 min  (80% of iterations)         │
│    Patrol-only: 1-3 hours  (20%)                       │
│    Dry retry:   2-5 minutes                             │
│                                                         │
│  Telegram poller (background task):                     │
│    PollingConsumer(consumer, poll_interval=5s)         │
│    crash → restart with exponential backoff             │
└─────────────────────────────────────────────────────────┘
         │
         ▼
   TelegramNotifier
   (sends webhook payloads on new PRs,
    receives commands via polling)
```

### Hunting Pipeline (`farm_agent/orchestrator/pipeline.py`)

```
Entry: farm_agent run / farm_agent hunt
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  ContribPipeline.run()                                  │
│    RepoDiscovery.discover()  → scored repo list         │
│    asyncio.gather(run_single(repo) for repo in repos)  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  ContribPipeline.run_single(repo)                       │
│    _process_repo(repo) for each scored repo            │
│    max_concurrent_repos controls parallelism           │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  _process_repo(repo) — 10 stages                        │
│                                                         │
│  1. AI policy check  ─ is this farm-agent itself?      │
│     → skip if owner matches github.username             │
│                                                         │
│  2. Interaction limit  ─ has_analyzed() from memory?    │
│     → skip if analyzed recently (configurable window)   │
│                                                         │
│  3. Maintainer vibe check                              │
│     fetch_recent_maintainer_comments() → LLM classify  │
│     HOSTILE → blacklist_repo() → skip                   │
│                                                         │
│  4. Fetch guidelines                                    │
│     fetch_guidelines(CONTRIBUTING.md)                   │
│                                                         │
│  5. Analyze                                             │
│     CodeAnalyzer.analyze(repo)                          │
│     7 strategies in parallel via asyncio.gather        │
│     → list[Finding]                                     │
│                                                         │
│  6. Pre-filter                                          │
│     drop any finding without exact file_path           │
│                                                         │
│  7. Anti-farming gate                                   │
│     if finding.impact not in (CRITICAL, HIGH): drop   │
│     if farming_keyword in description: drop            │
│     (keywords: docstring, typo, format, kebab-case)    │
│                                                         │
│  8. Duplicate detection                                 │
│     if has_analyzed(repo): skip remaining              │
│                                                         │
│  9. Validate findings                                   │
│     confidence >= min_confidence?                       │
│     impact >= min_impact?                              │
│     → drop failing                                      │
│                                                         │
│ 10. Generate (per validated finding)                   │
│     ContributionGenerator.create_contribution()       │
│         │                                               │
│         ▼                                               │
│     ┌───────────────────────────────────────────────┐  │
│     │ Sandbox Guillotine                            │  │
│     │ DockerSandbox.execute()                       │  │
│     │ timeout=60s, mem_limit=512m                   │  │
│     │ exit_code=137 → SIGKILL → retry (max 3)       │  │
│     │ → all fail: skip this finding, no PR created  │  │
│     └───────────────────────────────────────────────┘  │
│         │                                               │
│         ▼                                               │
│     Human WPM delay (bimodal: 30-300s or 3600-28800s)  │
│         │                                               │
│         ▼                                               │
│     GitHubAPI.create_or_update_file() (DCO signed)     │
│         │                                               │
│         ▼                                               │
│     GitHubAPI.create_pull_request()                    │
│         │                                               │
│         ▼                                               │
│     PRManager.check_compliance_and_fix()               │
│         (auto-fix title, issue-ref, CLA sign)          │
│         │                                               │
│         ▼                                               │
│     PRManager.wait_for_ci()                            │
│         (poll check runs, max max_ci_retries)           │
│         → CI auto-heal on infra errors                 │
│         │                                               │
│         ▼                                               │
│     Memory.record_pr()                                 │
│     Memory.record_analysis()                            │
└─────────────────────────────────────────────────────────┘
```

### Patrol & Auto-Heal Loop (`farm_agent/pr/patrol.py`)

```
Entry: farm_agent patrol
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  PRPatrol.run()                                         │
│    PRManager.get_open_prs()  ← repos from memory        │
│    For each PR (up to max_review_per_repo):            │
│                                                         │
│      WPM delay simulation (bimodal)                    │
│                                                         │
│      review_and_respond(pr)                             │
│        fetch_comments(pr)                              │
│        filter out REVIEW_BOT comments                   │
│        build context from GITHUB_REPLIES examples       │
│        LLM generate response                           │
│        post_comment()                                   │
│                                                         │
│      check_ci_status(pr)                               │
│        CI_INFRA_IGNORE_PATTERNS filter                 │
│        (vercel, netlify, codecov, CLA bots → ignored)   │
│        → infra error → CI auto-heal (up to 3 retries)  │
│                                                         │
│      should_surrender(pr)                               │
│        if max_review_per_repo exhausted:                │
│          post farewell comment → exit loop              │
└─────────────────────────────────────────────────────────┘
         │
         ▼
   PRManager.wait_for_ci()  ←  CI auto-heal loop
     download_check_run_log() → parse for infra errors
     filter CI_INFRA_IGNORE_PATTERNS
     if fixable: generate corrective commit → force-push
     if surrender: close PR with explanation
```

---

## 3. Data Flows & State Management

### GitHub API → memory → LLM → sandbox → git push

```
GitHub API (httpx async)
    │
    ├── GET /repos/{owner}/{repo}        → repo metadata (stars, language)
    ├── GET /search/repos                → discovery results
    ├── GET /repos/{owner}/{repo}/issues → open issues
    ├── GET /repos/{owner}/{repo}/comments → PR comments (vibe check)
    ├── GET /repos/{owner}/{repo}/pulls  → open PRs (patrol)
    ├── GET /repos/{owner}/{repo}/commits → commit history (style mimicry)
    └── GET /repos/{owner}/{repo}/commits/{ref}/check-runs → CI status

GitHubAPI.create_or_update_file()
    │
    ├── fetch current SHA
    ├── append DCO signoff line
    ├── set author timestamp: now - random(15..45) minutes
    └── PUT /repos/{owner}/{repo}/contents/{path}
            │
            ▼
Memory (SQLite WAL)
    │
    ├── analyzed_repos     ← record_analysis()
    ├── submitted_prs      ← record_pr() / update_pr_status()
    ├── blacklisted_repos  ← blacklist_repo()
    ├── api_usage_log      ← check_and_record_llm_quota()
    ├── run_log           ← start_run() / finish_run()
    └── pr_outcomes       ← record_outcome()
            │
            ▼
LLM (MinimaxProvider / MiniMax M2.7)
    │
    ├── CodeAnalyzer        → 7 strategy prompts → Finding[]
    ├── ContributionGenerator → Finding + RepoContext → FileChange[]
    ├── check_maintainer_vibe() → WELCOMING/STRICT/HOSTILE
    ├── _self_review()     → APPROVE/REJECT
    └── PatrolAgent        → PR response text
            │
            ▼
DockerSandbox (ephemeral container)
    │
    ├── volume mount /workspace with generated files
    ├── mem_limit="512m", network_disabled=True
    ├── pids_limit=128, cap_drop=["ALL"]
    ├── timeout=60s
    ├── exit_code=137 → SIGKILL → retry
    └── stdout/stderr → sandbox result dict
            │
            ▼
Git push (via GitHubAPI.create_or_update_file)
    │
    ├── DCO signoff line appended to commit message
    ├── Author timestamp jittered 15-45 min before push
    └── PR created with compliance check + CI wait
```

### SQLite `memory.db` Schema

```sql
-- WAL journal mode (set at connection time)
PRAGMA journal_mode=WAL;

CREATE TABLE analyzed_repos (
    full_name   TEXT PRIMARY KEY,
    language    TEXT,
    stars       INTEGER,
    analyzed_at TEXT,           -- ISO UTC
    findings    INTEGER DEFAULT 0,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE submitted_prs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    pr_number   INTEGER NOT NULL,
    pr_url      TEXT NOT NULL,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL,
    status      TEXT DEFAULT 'open',   -- open|merged|closed
    branch      TEXT,
    fork        TEXT,
    created_at  TEXT,                   -- ISO UTC
    updated_at  TEXT,
    ci_fix_attempts INTEGER DEFAULT 0,
    discussion_replies INTEGER DEFAULT 0,
    UNIQUE(repo, pr_number)
);

CREATE TABLE findings_cache (
    id          TEXT PRIMARY KEY,
    repo        TEXT NOT NULL,
    type        TEXT NOT NULL,
    severity    TEXT NOT NULL,
    title       TEXT NOT NULL,
    file_path   TEXT,
    status      TEXT DEFAULT 'new',
    created_at  TEXT
);

CREATE TABLE run_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    repos_analyzed INTEGER DEFAULT 0,
    prs_created  INTEGER DEFAULT 0,
    findings     INTEGER DEFAULT 0,
    errors       INTEGER DEFAULT 0,
    metadata     TEXT DEFAULT '{}'
);

CREATE TABLE pr_outcomes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    pr_number   INTEGER NOT NULL,
    pr_url      TEXT NOT NULL,
    pr_type     TEXT NOT NULL,
    outcome     TEXT NOT NULL,   -- merged|closed|rejected
    feedback    TEXT DEFAULT '',
    time_to_close_hours REAL DEFAULT 0,
    recorded_at TEXT,
    UNIQUE(repo, pr_number)
);

CREATE TABLE repo_preferences (
    repo        TEXT PRIMARY KEY,
    preferred_types TEXT DEFAULT '[]',  -- JSON list
    rejected_types  TEXT DEFAULT '[]',  -- JSON list
    merge_rate  REAL DEFAULT 0.0,
    avg_review_hours REAL DEFAULT 0.0,
    notes       TEXT DEFAULT '',
    updated_at  TEXT
);

CREATE TABLE blacklisted_repos (
    repo            TEXT PRIMARY KEY,
    reason          TEXT NOT NULL,
    pr_number       INTEGER,           -- nullable
    blacklisted_at  TEXT NOT NULL
);

CREATE TABLE api_usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,         -- Unix epoch
    provider    TEXT NOT NULL
);

-- Index for sliding-window quota queries
CREATE INDEX idx_api_usage ON api_usage_log(provider, timestamp);
```

### Key Pydantic Models

| Model | Module | Fields |
|---|---|---|
| `Finding` | `core/models.py` | id, type (ContributionType), severity (Severity), impact (ImpactLevel), title, description, file_path, line_range, confidence (float 0-1), suggestion, priority_score |
| `FileChange` | `core/models.py` | path, original_content, new_content, is_new_file |
| `RepoContext` | `core/models.py` | repo, branch, file_contents dict, relevant_files dict, commit_history, recent_prs, guidelines |
| `FarmAgentConfig` | `core/config.py` | 13 sub-configs: github, discovery, pipeline, models, multi_model, sandbox, quota, memory, schedule, notifications, quality, patrol, issue_solver, superhuman |
| `Model` | `llm/models.py` | provider, name, temperature, max_tokens |
| `Guidelines` | `github/guidelines.py` | has_guidelines, preferred_types, forbidden_types, commit_style, pr_title_format, scope_rules |
| `PipelineContext` | `core/middleware.py` | repo, finding, changes, error, retry_count, metadata |

---

## 4. Edge Cases & Fallback Protocols

### Edge Case 1: Sandbox Guillotine (All Retries Fail)
**Trigger**: `DockerSandbox.execute()` returns `exit_code=137` (SIGKILL) on all 3 attempts.
**Flow**:
```
DockerSandbox.execute() → exit_code=137 → retry 1
DockerSandbox.execute() → exit_code=137 → retry 2
DockerSandbox.execute() → exit_code=137 → retry 3
→ log "All sandbox retries exhausted, skipping finding"
→ NO PR created for this finding
→ Memory.record_analysis() with findings_count=0
→ Continue to next finding
```
**Why it matters**: Prevents hallucinated code from being pushed. Exit 137 means the container was killed by the OOM killer or the 60s wall-clock limit.

---

### Edge Case 2: Anti-Farming Gate Blocks Everything
**Trigger**: All findings from a repo are dropped by the anti-farming gate (LOW/MEDIUM impact + farming keywords detected).
**Flow**:
```
CodeAnalyzer.analyze() → 5 findings
Anti-farming gate → all 5 dropped (impact=LOW, farming keywords found)
Memory.record_analysis(repo, findings_count=0)
No PR created
```
**Why it matters**: Prevents noise PRs on repos that only have documentation issues or trivial typos. CRITICAL/HIGH findings bypass this gate entirely.

---

### Edge Case 3: HOSTILE Maintainer Vibe
**Trigger**: LLM classifies recent PR comments as HOSTILE.
**Flow**:
```
fetch_recent_maintainer_comments() → [comments]
check_maintainer_vibe(comments) → "HOSTILE"
blacklist_repo(owner, repo, "HOSTILE maintainer")
Memory.blacklisted_repos INSERT
Next _process_repo() call → is_blacklisted() → skip immediately
```
**Why it matters**: Permanent protection against hostile communities. The bot never targets a HOSTILE repo again.

---

### Edge Case 4: Minimax LLM Rate Limit
**Trigger**: `api_usage_log` count ≥ 950 in 5-hour window OR ≥ 9500 in 7-day window.
**Flow**:
```
check_and_record_llm_quota() → LLMRateLimitError raised
    in ContributionGenerator.create_contribution():
        except LLMRateLimitError:
            logger.warning("LLM quota exhausted, sleeping 30 min")
            await asyncio.sleep(1800)
            retry
    in SuperHumanLoop:
        except LLMRateLimitError:
            logger.warning("Quota hit, entering long cooldown")
            sleep until quota window resets (up to 5 hours)
```
**Why it matters**: Prevents hitting Minimax hard limits which would block the API key entirely.

---

### Edge Case 5: GitHub Rate Limit (Secondary Abuse Detection)
**Trigger**: 403 response with no `X-RateLimit-Remaining` header (abuse detection, not primary rate limit).
**Flow**:
```
GitHubAPI.request() → 403 no remaining header
→ sleep 60s → retry
→ 403 again → sleep 120s → retry
→ still failing → raise RateLimitError
Pipeline retries with exponential backoff via RetryMiddleware
```
**Why it matters**: Distinguishing abuse 403 (retryable) from hard rate limit 403 (remaining==0, immediate fail) is critical for reliability.

---

### Edge Case 6: CLA Signing — EasyCLA (Manual)
**Trigger**: CLA check returns EasyCLA provider type.
**Flow**:
```
check_compliance_and_fix() → detect EasyCLA
post_comment("I have read the CLA and I hereby sign the CLA")
PR remains open
Maintainer must manually verify and approve
```
**Why it matters**: EasyCLA requires human-authorized signing. The bot posts the acknowledgment but cannot auto-sign.

---

### Edge Case 7: CI Auto-Heal Surrender
**Trigger**: CI fails with an infra error after `max_ci_retries` (default 3) repair attempts.
**Flow**:
```
wait_for_ci() → CI check run shows infra error
CI auto-heal loop (max 3 retries):
    download_check_run_log()
    filter CI_INFRA_IGNORE_PATTERNS
    generate corrective commit
    force-push to PR branch
    re-run CI
If all 3 heal attempts fail:
    post_comment("CI infrastructure error, surrendering")
    close_pr()
    Memory.record_outcome(repo, pr_number, "closed", "ci_surrender")
```
**Why it matters**: The bot does not waste cycles on unrepairable infra issues (vercel misconfiguration, missing env vars, etc.).

---

### Edge Case 8: Patch Parsing — All 4 Passes Fail
**Trigger**: LLM returns a patch that fails all 4 matching passes in `_parse_changes()`.
**Flow**:
```
_parse_changes() → Try exact → Try whitespace-normalized
→ Try stripped → Try indentation-agnostic
→ all fail → logger.warning("Search text not found")
→ edits_applied = 0 → file skipped
No FileChange appended to changes list
Contribution discarded
```
**Why it matters**: The Diff Minimizer + 4-pass parser together form a strong hallucination guard. If the LLM's own output cannot be matched back to the input, the change is discarded rather than applied blindly.

---

### Edge Case 9: Duplicate PR (Already Analyzed)
**Trigger**: `has_analyzed()` returns `True` for a repo in the current run.
**Flow**:
```
_process_repo(repo):
    if await memory.has_analyzed(repo):
        logger.info("Repo %s already analyzed, skipping", repo)
        return  # skip all remaining stages
Memory.record_analysis() called at end of successful run
```
**Why it matters**: Prevents the same finding from generating multiple PRs against the same repo within the same run. `has_analyzed()` is also checked in the anti-duplicate gate.

---

### Edge Case 10: Fork Exhaustion
**Trigger**: User hits `fork_count` limit (default: all forks used).
**Flow**:
```
create_fork() → GitHub API returns 403 or 404
→ log "Fork limit reached or fork unavailable"
→ skip this repo, continue to next in discovery list
get_stats() → used in CRIT-01 quota check
```
**Why it matters**: GitHub has per-user/organization fork limits (~100 for free, 250 for paid). The bot gracefully skips repos it cannot fork rather than crashing.
