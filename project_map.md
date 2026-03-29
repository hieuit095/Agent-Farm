# ContribAI — Source Code Map & Architectural Reference

**Status**: Single Source of Truth (SSOT) | **Last Updated**: 2026-03-29
**Purpose**: Exhaustive code anatomy, execution flows, data models, and edge case protocols.
**Architecture Version**: 2.0.0 — 7 Enterprise-Grade Protocols Injected

---

## 1. Directory & File Anatomy

### `farm_agent/` — Core Package

#### `agents/registry.py`
`AgentRegistry` — Dynamic sub-agent registry supporting registration, retrieval, and middleware chaining for each agent type. Ships with built-in stubs: `AnalyzerAgent`, `GeneratorAgent`, `PatrolAgent`, `ComplianceAgent`, `IssueSolverAgent`. Each stub logs "Not implemented" and returns an empty list by default; replaced by real implementations via registration.

#### `analysis/analyzer.py`
`CodeAnalyzer` — Executes multiple analysis strategies (security, code_quality, docs, ui_ux, performance, refactor, testing) using `asyncio.gather`. Each strategy runs its own LLM prompt through `MinimaxProvider`. `ANALYZABLE_EXTENSIONS` filters to programming files (.py, .js, .ts, .jsx, .tsx, .go, .rs, .java, .cpp, .c, .h, .hpp, .cs, .swift, .kt, .html, .css, .scss, .vue, .svelte, .md, .rst, .txt, .yaml, .yml, .json, .toml). Each prompt embeds Anti-Farming rules (drop LOW/MEDIUM+docstring/typo/format/kebab-case-only) and Anti-False-Positive rules (require exact line references, reject hypotheticals). `_detect_project_profile()` queries the file tree to classify the project as web_app, api_server, cli_tool, data_pipeline, or library. `_build_style_guide()` extracts naming conventions, error handling patterns, docstring format, import style, and logging patterns from sample files. `_prioritize_files()` scores files by entry-point proximity, core-module proximity, test/vendor penalty, and size heuristics. `check_maintainer_vibe()` queries recent PR review comments via GitHub API and classifies as WELCOMING/STRICT/HOSTILE using LLM; HOSTILE triggers permanent repo blacklist. `_parse_findings()` tries YAML block parsing first, falls back to regex extraction. The analyzer produces `AnalysisResult` objects containing `Finding[]`, `analyzed_files` count, `skipped_files` count, and `analysis_duration_sec`.

#### `analysis/skills.py`
`SkillsEngine` — Generates structured LLM prompts for each of the analysis strategies. Each skill defines its own system prompt, file targeting rules, and result schema. Used exclusively by `CodeAnalyzer`.

#### `analysis/strategies.py`
`AnalysisStrategy` — Pluggable strategy pattern for adding new analysis dimensions. Defines the interface `_run_strategy(ctx: RepoContext) -> list[Finding]`. Built-in strategies registered by name in `CodeAnalyzer._run_analyzer()`.

#### `analysis/mapper.py`
`RepoMapper` — Maps directory structure and build system files of a repository. Used by the issue solver to build a project skeleton before generating multi-file solutions. Identifies build files (setup.py, pyproject.toml, Cargo.toml, go.mod, package.json, pom.xml) and entry points.

#### `analysis/language_rules.py`
Language-specific analysis rules that calibrate what constitutes a real bug per language. For example, in Python it penalizes `except Exception: pass` bare catches, in Rust it flags unsafe blocks without safety comments, in Go it flags missing error propagation.

#### `cli/main.py`
`main()` — Click CLI entry point with subcommands: `run` (hunt pipeline), `target` (single repo), `hunt` (discovery → analyze → generate), `patrol` (PR review loop), `superhuman` (24/7 daemon), `analyze` (static only), `solve` (issue solver), `status` (today's PR count + quota), `stats` (merge rate, repo prefs), `cleanup` (remove old forks/branches), `config` (validate config), `serve` (FastAPI), `schedule` (cron scheduler), `templates` (PR template library), `profile` (select model profile), `models` (list available models), `interactive` (TUI), `leaderboard` (top repos by merge rate), `notify-test` (webhook test), `system-status` (full diagnostics), `janitor` (sweep and destroy garbage PRs). Rich-colored terminal output with emoji prefixes.

#### `cli/tui.py`
`ContribTUI` — Rich-based interactive terminal interface for `interactive` command. Uses `Live` display for real-time updates, `Table` for repo findings, `Panel` for status. Handles keyboard interrupts gracefully.

#### `core/config.py`
`FarmAgentConfig` — Root Pydantic model with sub-configs: `GitHubConfig` (token, max_prs_per_day, fork_count, min_daily_prs, max_daily_prs, rate_limit_buffer, dco_signoff), `LLMConfig` (provider=minimax, model=MiniMax-M2.7, api_key, temperature, max_tokens, base_url, minimax_group_id), `AnalysisConfig` (enabled_analyzers, severity_threshold, max_file_size_kb, skip_patterns), `ContributionConfig` (enabled_types, max_files_per_pr, run_tests_before_pr, commit_convention, pr_description_style, max_review_retries), `DiscoveryConfig` (languages, stars_range, min_last_activity_days, require_contributing_guide, topics), `StorageConfig` (db_path, cache_ttl_hours, resolved_db_path property), `SchedulerConfig` (enabled, cron, timezone, max_concurrent), `WebConfig` (host, port, enabled, api_keys, webhook_secret), `PipelineConfig` (max_concurrent_repos, timeout_per_repo_sec, max_ci_retries, max_discussion_replies, max_patch_retries, max_review_retries), `QuotaConfig` (github_daily_limit, llm_daily_limit, llm_daily_tokens), `NotificationConfig` (slack_webhook, discord_webhook, telegram_token, telegram_chat_id, on_merge, on_close, on_run_complete), `LogConfig` (level, log_dir, keep_days), `MultiModelConfig` (enabled, strategy, model_overrides). `StorageConfig.resolved_db_path` defaults to `data/memory.db`. All secrets fall back to environment variables. `GitHubConfig.resolve_token()` falls back to `gh auth token` CLI. `load_config()` searches: explicit path → ./config.yaml → ~/.farm_agent/config.yaml → defaults.

#### `core/models.py`
All shared Pydantic models and enums.

**Enums**: `ImpactLevel` (CRITICAL, HIGH, MEDIUM, LOW, TRIVIAL), `FeedbackAction` (CODE_CHANGE, QUESTION, STYLE_FIX, APPROVE, REJECT, HOSTILE_REJECT, ALREADY_HANDLED, CONVERSATIONAL, FOLLOW_UP), `ContributionType` (SECURITY_FIX, CODE_QUALITY, README_FIX, UI_UX_FIX, PERFORMANCE_OPT, FEATURE_ADD, REFACTOR), `Severity` (CRITICAL, HIGH, MEDIUM, LOW, INFO), `PRStatus` (OPEN, MERGED, CLOSED, UNKNOWN).

**Models**: `FileChange` (path, original_content, new_content, is_new_file), `RepoContext` (repo, branch, file_tree, readme_content, contributing_guide, relevant_files dict, commit_history, recent_prs, guidelines, coding_style), `Finding` (id, type, severity, impact_level, title, description, file_path, line_start, line_end, suggestion, priority_score), `Repository` (owner, name, full_name, description, language, stars, forks, open_issues, topics, default_branch, html_url, clone_url, has_license), `FileNode` (path, type, size, sha), `Issue` (number, title, body, labels, state, html_url), `AnalysisResult` (repo, findings, analyzed_files, skipped_files, analysis_duration_sec), `Contribution` (finding, contribution_type, title, description, changes list[FileChange], commit_message, branch_name), `PRResult` (pr_number, pr_url, branch_name, fork_full_name).

#### `core/exceptions.py`
Exception hierarchy: `FarmAgentError` → `RateLimitError` (GitHub 403 with remaining==0), `LLMRateLimitError` (Minimax quota exceeded), `SandboxError` (Docker exec failed), `AnalysisError`, `GenerationError`, `PatrolError`, `ComplianceError`, `BlacklistedError` (repo is blacklisted), `GitHubAPIError`. All are instantiable with a `detail: str` field.

#### `core/leaderboard.py`
`Leaderboard` — Tracks and ranks repos by merge rate. `update()` records a PR outcome, `get_top()` returns sorted list. Persisted via JSON file at `farm_agent_data/leaderboard.json`.

#### `core/middleware.py`
`PipelineContext` — Dataclass carrying `repo`, `finding`, `changes`, `error`, `retry_count`, `metadata`. `MiddlewareChain` — Pluggable middleware executor. Built-ins: `RateLimitMiddleware` (checks `UsageTracker`), `ValidationMiddleware` (Pydantic validation), `RetryMiddleware` (exponential backoff: 1s, 2s, 4s...), `DCOMiddleware` (ensures DCO signoff on commits), `QualityGateMiddleware` (blocks if confidence < threshold). `build_default_chain()` constructs the chain from config.

#### `core/quotas.py`
`UsageTracker` — In-memory per-day counters for GitHub API requests and LLM tokens. `check()` raises `QuotaExceededError` if limits are hit. Resets counters on local date change (not UTC — uses OS timezone). Tracks `llm_tokens_used`, `github_requests_made`.

#### `core/profiles.py`
`ModelProfile` — Named model configurations (e.g. "balanced", "fast", "smart"). `load_profile()` / `save_profile()` via JSON. Used by the `profile` CLI subcommand.

#### `core/retry.py`
Retry utilities with exponential backoff: `exponential_backoff_async(fn, max_retries, base_delay)`. Used by pipeline and patrol for transient failures.

#### `core/daily_log.py`
`DailyMarkdownLogger` — Appends a daily rolling log entry to `logs/daily/YYYY-MM-DD.md`. Records: new day targets, hunt successes (with PR URL), patrol results, quota met events, errors. Used by `SuperHumanLoop` to maintain a human-readable daily journal.

#### `core/notifier.py`
`TelegramNotifier` — Sends formatted Telegram messages. `start_polling(memory)` starts a background `PollingConsumer` that listens for commands (ping, status, stats, quit). `send_message()` fires a Telegram API call. `send_diff()` posts a formatted diff to Telegram with file-level chunking (Telegram 4096 char limit). `close()` shuts down the poller gracefully. All sends are fire-and-forget with error logging. The background poller has a crash-restart callback with exponential backoff.

#### `core/sandbox.py` — **Protocol 5: Polyglot Guillotine**
`DockerSandbox` — Runs commands inside ephemeral Docker containers. **LANGUAGE_ENVIRONMENTS** dict maps languages to Docker images and test commands: `python` → `python:3.11-alpine` + `pip install -q pytest && pytest`, `javascript/typescript` → `node:20-alpine` + `npm install && npm test`, `rust` → `rust:1.75-alpine` + `cargo test`, `go` → `golang:1.21-alpine` + `go test`, `java` → `eclipse-temurin:21-jdk-alpine` + `mvn test`, `ruby` → `ruby:3.3-alpine` + `bundle install && bundle exec rake test`, `php` → `php:8.2-cli-alpine` + `composer install && phpunit`, `c/cpp` → `gcc:14-bookworm` + `make test`, `csharp` → `mcr.microsoft.com/dotnet/sdk:8.0-alpine` + `dotnet test`. **EXTENSION_TO_LANGUAGE** maps file extensions to language keys (`.py`→python, `.rs`→rust, `.go`→go, `.java`→java, `.rb`→ruby, `.php`→php, `.c`/`.h`→c, `.cpp`/`.hpp`→cpp, `.cs`→csharp, `.swift`→swift, `.kt`→kotlin). `detect_language_from_extensions(repo_path)` walks the directory tree counting extensions and returns the most common language. `detect_language_from_repo_info(repo_info)` extracts language from GitHub API metadata and normalizes to the internal language key. `get_environment_for_language(language)` returns the image+commands dict, falling back to Python. `run_in_sandbox()` is the main entry: resolves language → environment → image → command, creates an ephemeral container with `mem_limit="512m"`, `network_disabled=True`, `cap_drop=["ALL"]`, `pids_limit=128`, mounts the repo at `/workspace`, runs the language-specific test command with a configurable timeout (default 60s), captures stdout/stderr via Docker attach API. `exit_code=137` means SIGKILL (OOM or timeout). Container is force-removed in the `finally` block. `ImageNotFound` triggers an automatic `client.images.pull()` before retry. Container labels include `farm_agent.sandbox=true` and `farm_agent.sandbox.run_id` for cleanup tracking. `_wait_for_container_removal()` polls the daemon until containers with the matching run_id label are gone.

#### `core/rag.py` — **Protocol 6: X-Ray Vision (ChromaDB RAG)**
`RepoIndexer` — In-memory RAG indexer for a single repository. Uses ChromaDB `EphemeralClient` (RAM-only, no disk persistence). `_init_chroma()` lazily creates the ChromaDB collection with `hnsw:space=cosine`. If ChromaDB is not installed, silently falls back to `None`. `index_repo(repo_name, file_contents)` indexes all files using sliding-window chunking: `DEFAULT_CHUNK_SIZE=1200` characters, `DEFAULT_CHUNK_OVERLAP=200`. `chunk_file()` breaks content at line boundaries to keep code intact. Files larger than `MAX_FILE_SIZE_BYTES=200KB` are skipped. Files matching `EXCLUDE_PATTERNS` (node_modules, `.git`, `__pycache__`, `.min.js`, `.map.js`, `.pyc`, `dist/`, `build/`, `target/`, `vendor/`, `.lock`, `package-lock.json`, `.wasm`, `.bin`, `.so`, `.dll`) are excluded. `_embed_texts_fallback()` generates fixed 128-dim word-frequency vector embeddings with L2 normalization — deterministic regardless of collection order (sorted alphabetically). `query_context(query, n_results)` returns semantically similar code chunks with `content`, `file_path`, `distance` (cosine), `chunk_index`. `destroy()` deletes the ChromaDB collection to free RAM. `__del__` guarantees cleanup on object destruction. `EMBEDDING_DIM=128` satisfies ChromaDB's collection-wide embedding dimension invariant.

**The `ContributionGenerator` in `generator/engine.py`** calls `_find_cross_file_instances()` which uses `RepoIndexer` to perform semantic cross-file search for the same bug pattern. It indexes all `context.relevant_files`, queries with the finding title+description+suggestion concatenated, groups results by file, and returns up to 3 related files with their chunk content. This provides "X-Ray Vision" — seeing how the same pattern manifests across the entire codebase before generating the fix. If ChromaDB is unavailable, falls back to regex-based keyword extraction (`_extract_search_patterns()`).

#### `core/logger.py`
`setup_logging()` — Configures Python `logging` with a coloredformatter for console and a rotating file handler for `logs/farm_agent.log`. Log level and directory controlled by `LogConfig`.

#### `generator/engine.py`
`ContributionGenerator` — Takes `Finding` + `RepoContext`, calls LLM with structured prompt to produce code patches. `MAX_TOOL_CALLS=3`. Prompt includes cross-file context from `_find_cross_file_instances()` (X-Ray Vision). `_parse_changes()` — 4-pass matching: (1) exact string, (2) whitespace-normalized, (3) stripped, (4) indentation-agnostic line-by-line with re-indentation. Diff Minimizer: rejects edits where replacement >30 lines and search <5 lines. `_self_review()` asks LLM APPROVE/REJECT on the generated diff; REJECT discards the contribution. `_generate_commit_message()` uses conventional commit format. `_generate_branch_name()` uses semantic prefixes (fix/, feat/, perf/, etc.) without tool branding. `_generate_pr_title()` adapts to repo guidelines if available. `_build_review_snippet()` builds compact diff-oriented snippets using `difflib.unified_diff`. The generator integrates with the `ReviewerAgent` (Protocol 7) when configured.

#### `generator/scorer.py`
`Scorer` — Calculates `priority_score` for each `Finding` using severity × confidence × impact weights. Used by the pipeline to sort findings before generation. `score_finding()` is the main entry.

#### `generator/reviewer.py` — **Protocol 7: Red Team Adversarial Review**
`ReviewerAgent` — Independent adversarial reviewer that acts as a paranoid Senior Security Auditor. Completely separate LLM instance from the Generator (no shared conversational history, no shared system prompt). `SYSTEM_PROMPT` instructs the agent to find HALLUCINATED VARIABLES, INCOMPLETE FIX, REGRESSIONS, LOGIC ERRORS, STYLE VIOLATIONS, and INCORRECT SCOPE. `review(contribution, context)` returns `{"decision": "APPROVE"|"REJECT", "critique": "..."}`. The prompt includes all changed files with original and proposed content, the finding type/severity/description/suggestion, and the primary file path. `_parse_verdict()` handles JSON with/without markdown fences, trailing commas, and response prefixes. On parse failure, falls back to keyword search for REJECT/APPROVE. On any exception, defaults to APPROVE (fail-open for robustness). Temperature is set to 0.05 for consistent JSON output. Max review tokens: 800.

The adversarial loop works as follows: Generator produces a `Contribution` → Pipeline calls `ReviewerAgent.review()` → if `REJECT`, the critique is fed back to the Generator for rewrite → Generator rewrites using the critique → `ReviewerAgent.review()` is called again → up to `max_review_retries` (default 2 from `ContributionConfig`) iterations. If the ReviewerAgent still rejects after all retries, the contribution is discarded and no PR is created.

#### `github/client.py`
`GitHubClient` — Async httpx wrapper with token auth. **Rate limit handling**: 403 with `remaining==0` → raise `RateLimitError` immediately. 403 abuse detection (no remaining header) → retry with 60s backoff, then 120s. **Key methods**: `get_repo_details()` (fetch repo metadata), `search_repositories()` (GitHub search API), `get_file_tree()` (recursive tree via git trees API), `get_file_content()` (base64 decode), `get_open_issues()` (issues only, no PRs), `fork_repository()`, `create_branch()`, `create_or_update_file()` (auto-fetches SHA, appends DCO signoff line, sets author timestamp jittered 15-45 min before push), `create_pull_request()`, `update_pull_request()`, `create_issue()`, `get_pr_comments()`, `create_pr_comment()`, `get_pr_reviews()`, `get_pr_review_comments()`, `create_pr_review_comment_reply()`, `get_pr_diff()`, `get_pr_commits()`, `get_commit_diff()`, `get_combined_status()` (aggregates check runs from GitHub Actions), `get_pr_check_runs()`, `download_check_run_log()` (follows redirect to S3/GHA artifact URL), `get_recent_merged_prs()` (for style mimicry, skips bot PRs), `fetch_recent_maintainer_comments()` (for vibe check, last 3 comments from OWNER/COLLABORATOR/MEMBER), `check_interaction_limits()` (checks if repo restricts to prior contributors), `list_pull_requests()` (state=all/open/closed), `list_issues()` (with label and assignee filters), `get_assigned_issues()`, `get_issue_comments()`, `get_issue_timeline()`, `fetch_user_merged_prs()` (GET /search/issues?q=author:{username}+is:pr+is:merged — paginates up to 10 pages), `fetch_user_open_prs()` (GET /search/issues?q=author:{username}+is:pr+is:open), `get_authenticated_user()`, `close_pull_request()`, `delete_branch()`, `add_comment_reaction()` (for issue comments and review comments). `_parse_repo()` parses raw API response into `Repository` model.

#### `github/discovery.py`
`RepoDiscovery` — Star-range-based repo scoring (config `discovery.stars_range`, Shark Tank: 1000-20000). `score_repo()` awards points: star sweet-spot 100-5000 (+3), open issues (+3), has license (+1), has contributing guide (+2), fork count 10-500 (+1.5). `discover()` yields scored repos sorted by score descending. `filter_by_language()` applies optional language filter. Uses `search_repositories()` with GitHub search API.

#### `github/guidelines.py`
`Guidelines` — Pydantic model with `has_guidelines`, `preferred_types`, `forbidden_types`, `commit_format`, `pr_title_format`, `scope_rules`, `required_sections`. `fetch_repo_guidelines()` hits the GitHub API to fetch CONTRIBUTING.md and parses it via LLM. `adapt_pr_title()` adapts the PR title to repo conventions. `extract_scope_from_path()` extracts scope from file path. `adapt_pr_title()` and `extract_scope_from_path()` are also imported by `generator/engine.py`.

#### `issues/solver.py`
`IssueSolver` — `fetch_solvable_issues()` queries repos by label groups (e.g. `["good first issue", "help wanted"]`). `solve_issue_deep()` uses `RepoMapper` to build project skeleton, then LLM to generate multi-file `---FILE---` block solutions. Handles issue assignees and posts solution as a PR linked to the issue. `RepoMapper` maps directory structure and build system files.

#### `llm/provider.py`
`MinimaxProvider` — Async LLM provider for MiniMax API. `complete(prompt, system, temperature, max_tokens)` makes HTTP POST to MiniMax endpoint with JSON body containing messages array. `memory` attribute is set by `ContribPipeline._init_components()` for quota tracking. `set_task(task_type)` sets current task context for multi-model routing. `close()` closes the HTTP client. `create_llm_provider()` factory function constructs the appropriate provider from config.

#### `llm/models.py`
`Model` — Pydantic model for a single LLM (provider, name, temperature, max_tokens). `MultiModelConfig` for task-based routing. `TaskType` enum for routing tasks (analysis, code_gen, validation, patrol).

#### `llm/agents.py`
`Agent` — Wraps an LLM with system prompt and tool definitions. `execute()` runs the agent loop. Used by the agent registry.

#### `llm/context.py`
`ContextBuilder` — Builds structured context for LLM prompts. Aggregates repo metadata, recent PRs, style guide, and contribution guidelines into a compact prompt segment.

#### `llm/router.py`
`Router` — Routes tasks to the appropriate model based on `MultiModelConfig` task-to-model mapping. Falls back to the default model if no routing rule matches.

#### `orchestrator/memory.py` — **Protocol 3: Immortal Memory (Persistent SQLite DB)**
`Memory` — SQLite-backed persistent memory using aiosqlite with WAL journal mode. **`db_path`** defaults to `data/memory.db` via `StorageConfig.resolved_db_path`. WAL mode enabled at connection time. Schema consists of 8 tables:

- `analyzed_repos` (full_name PK, language, stars, analyzed_at, findings, metadata JSON) — records repos that have been scanned.
- `submitted_prs` (id, repo, pr_number PK UNIQUE, pr_url, title, type, status, branch, fork, created_at, updated_at, ci_fix_attempts, discussion_replies) — all PRs ever submitted, including merged, closed, and issue-first proposals.
- `findings_cache` (id PK, repo, type, severity, title, file_path, status, created_at) — cached finding IDs to avoid duplicate submissions.
- `run_log` (id PK, started_at, finished_at, repos_analyzed, prs_created, findings, errors, metadata JSON) — pipeline run history.
- `pr_outcomes` (id PK, repo, pr_number UNIQUE, pr_url, pr_type, outcome, feedback, time_to_close_hours, recorded_at) — PR outcomes for learning.
- `repo_preferences` (repo PK, preferred_types JSON, rejected_types JSON, merge_rate, avg_review_hours, notes, updated_at) — learned per-repo preferences.
- `blacklisted_repos` (repo PK, reason, pr_number, blacklisted_at) — permanently blocked repos.
- `api_usage_log` (id PK, timestamp REAL, provider) with index `idx_api_usage(provider, timestamp)` — sliding-window quota tracking.

**Key methods**: `record_pr()` (INSERT OR REPLACE into submitted_prs), `record_issue_proposal()` (records Route B proposals with type='issue_proposal'), `update_pr_status()` (updates status on submitted_prs), `get_today_pr_count()` (counts PRs by local date — uses OS timezone not UTC), `get_friendly_repos_for_hunting(limit, cooldown_days)` (returns merged repos off cooldown for re-hunting via JOIN of submitted_prs and analyzed_repos), `has_analyzed()` (checks analyzed_repos), `record_analysis()`, `get_prs(status, limit)`, `get_repo_prs(repo)`, `record_outcome()` (records merged/closed/rejected and auto-updates repo_preferences), `blacklist_repo()`, `is_blacklisted()`, `check_and_record_llm_quota()` (sliding window: 950 req/5h, 9500 req/7 days; raises LLMRateLimitError on breach; hourly cleanup of old entries), `increment_ci_fix_attempts()`, `increment_discussion_replies()`, `get_discussion_replies()`, `get_ci_fix_attempts()`. `init()` auto-migrates existing databases by adding missing columns (`ci_fix_attempts`, `discussion_replies`) via `ALTER TABLE`.

#### `orchestrator/pipeline.py` — **Protocols 1, 2, 6: Hybrid Router + Familiar Grounds + X-Ray Vision**
`ContribPipeline` — Main hunting pipeline orchestrator. **`PROTECTED_META_FILES`** set prevents modification of: CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE*, FUNDING.yml, CODEOWNERS, .github/CODEOWNERS, SECURITY.md, SUPPORT.md, MAINTAINERS.md, CONTRIBUTORS.md. **`SKIP_EXTENSIONS`** set prevents analysis of: .md, .txt, .rst, .yml, .yaml, .toml, .cfg, .ini, .json.

**`run()`** drives discovery → parallel repo processing via `asyncio.Semaphore`. **`hunt()`** runs multiple discovery rounds with varied star tiers, interleaving `Familiar Grounds` (friendly repos) before wild discovery. The `Familiar Grounds` logic inside `hunt()` calls `memory.get_friendly_repos_for_hunting(limit=min(remaining,2), cooldown_days=7)` and prepends those repos to the target list before spending API tokens on new discoveries. `mode` parameter: 'analysis' (static scan), 'issues' (issue solving), 'both'. **CRIT-03 fix**: Minimax mode caps `max_concurrent_repos` to 5 to prevent GitHub secondary rate limit thundering herd.

**`run_single(repo_url, max_prs, allow_duplicate_prs)`** processes one specific repo.

**`_process_repo(repo, dry_run, max_prs, allow_duplicate_prs)`** — The full 12-stage per-repo flow:

1. **AI Policy Check** — checks for AI_POLICY.md or anti-AI keywords in CONTRIBUTING.md. Returns immediately if AI PRs are banned.
2. **Interaction Limit Check** — `github.check_interaction_limits()` detects if repo restricts to prior contributors (returns 422 on PR creation).
3. **Maintainer Vibe Check** — `fetch_recent_maintainer_comments()` → `CodeAnalyzer.check_maintainer_vibe()` → WELCOMING/STRICT/HOSTILE. HOSTILE → `memory.blacklist_repo()` → skip.
4. **Guidelines Fetch** — `fetch_repo_guidelines()` → `Guidelines` object with commit format, PR title format, required sections.
5. **Analyze** — `CodeAnalyzer.analyze(repo)` → 7 concurrent strategies → `list[Finding]`.
6. **Pre-Filter (Non-Code)** — drops findings on files with SKIP_EXTENSIONS or matching PROTECTED_META_FILES.
7. **Anti-Farming Gate** — ONLY CRITICAL/HIGH impact pass (MEDIUM/LOW/TRIVIAL always dropped). Farming keyword blacklist checked against title+description combined (docstring, typo, format, whitespace, indent, naming convention, understand, explore, read, look at, investigate, test, testing, todo, fixme, chore, typo in, grammar, missing type hint, unused import).
8. **Duplicate Detection** — checks both local `memory.get_repo_prs()` AND GitHub API `list_pull_requests(state=all)` for similar titles (keyword overlap >50%) or same file paths mentioned in PR bodies.
9. **Findings Validation** — `_validate_findings()` re-examines each finding against full file content via LLM: is the code already protected by try/except/circuit breakers? Is the data source bounded? Is the function only called from safe contexts? INVALID findings are dropped.
10. **Hybrid Contribution Router** — inside the validated findings loop:
    - **Route A (Direct PR / Firefighter)**: `finding.type == SECURITY_FIX` OR `finding.severity in (CRITICAL, HIGH)` → generate code immediately.
    - **Route B (Issue-First / Polite Senior)**: everything else → `_propose_issue_first()` creates a GitHub Issue with a polite body, labels=["enhancement"], and records it in `memory.record_issue_proposal()`.
11. **Sandbox Guillotine** — if `self._sandbox` is set, runs `DockerSandbox.run_in_sandbox()` up to `max_retries` times. If sandbox fails all retries, PR creation is blocked and the finding is skipped.
12. **PR Creation** — `PRManager.create_pr()` → DCO-signed commit → branch → fork → `create_or_update_file()` → `create_pull_request()` → `memory.record_pr()` → Telegram notification → `_pr_manager.check_compliance_and_fix()` → `_check_ci_and_close_if_failed()`.

**`_process_repo_issues(repo, dry_run, max_prs)`** — Issue-driven mode: fetches solvable issues (label groups), calls `IssueSolver.solve_issue_deep()` for multi-file changes, generates contributions, creates PRs with "Closes #N" in body. Skips analysis stage after producing ≥1 issue-based PR to avoid spamming maintainers.

**`_propose_issue_first(finding, repo, context)`** — Route B implementation: generates a minimal `Contribution` with empty changes list, builds an issue title, generates issue body (polite senior dev style), calls `github.create_issue()`, records in `memory.record_issue_proposal()`.

**`_hunt_process_repo(repo, mode, dry_run, remaining, sem)`** — parallel repo handler for hunt mode. Issues-first (higher value), then static analysis (only if no issue-based PRs were created).

#### `orchestrator/human.py` — **Protocol 4: Alumni Sync (24h Background Sync) + SuperHuman Loop**
`SuperHumanLoop` — Stochastic 24/7 daemon. **ABSOLUTE_MAX_PRS_PER_DAY = 12** hard cap. **HUNT_WEIGHT = 0.60 / PATROL_WEIGHT = 0.40** for mode selection. Delay ranges: HUNT 30-90 min, DRY_HUNT 2-5 min, PATROL 10-30 min, PATROL_ONLY 1-3 hours. Stress break: 15 minutes. Time-warp mode: 1-3 second delays, auto-exits after 10 iterations.

**CRIT-01 fix**: `_do_hunt()` calls `memory.get_today_pr_count()` (DB-level check) before attempting to hunt, preventing post-restart over-creation.

**CRIT-02 fix**: Lunch check uses `datetime.now()` (local OS timezone) not UTC. Lunch runs from 12:00-13:01 local time. `_took_lunch_today` guard prevents re-trigger.

**`_sync_historical_friendly_repos()`** — Protocol 4 implementation. Runs on startup and every 24 hours. Calls `github.fetch_user_merged_prs(username)` → paginated GitHub search API (up to 1000 results). Filters by `config.discovery.stars_range` (checks each repo's star count via `github.get_repo_details()`). Deduplicates by repo (one entry per repo, most recent merged PR wins). Inserts into `submitted_prs` with status='merged' using `INSERT OR IGNORE` (idempotent). Returns count of newly inserted repos. This populates the "Familiar Grounds" — repos where we have a successful merged PR and can be safely re-targeted after a 7-day cooldown.

**`run_daily_routine()`** — The main loop:
1. On startup: sync PR counter from DB (CRIT-01), start Telegram poller with crash-restart callback, run `_sync_historical_friendly_repos()` on startup.
2. Every 24 hours: run `_sync_historical_friendly_repos()`.
3. Dice roll: if `random() < 0.60` → HUNT, else → PATROL.
4. Under quota: normal stochastic mode selection. Over quota: patrol-only mode (long 1-3h delays between cycles).
5. Smart fallback: if `prs_created_today >= max_prs_per_day` config ceiling, force-switch to patrol even below the daily target.
6. Lunch break at 12:00-13:01 local time.
7. Telegram background poller listens for commands (ping, status, stats, quit) and responds with Vietnamese human thoughts.

**`HUMAN_THOUGHTS`** — Vietnamese persona dictionary with categories: WAKE_UP, START_HUNT, HUNT_DONE, REST_HUNT, REST_HUNT_DRY, START_PATROL, PATROL_EMPTY, PATROL_DONE, REST_PATROL, QUOTA_MET, REST_PATROL_ONLY, API_ERROR, ACTION_ROLL, ITERATION, TIME_WARP_START, GOODBYE. Each iteration randomly selects a thought for Telegram context updates, making the bot appear human.

#### `pr/manager.py`
`PRManager` — Full PR lifecycle. `create_pr()` calls `create_pull_request()` → records in memory. `check_ci_status()` polls check runs, returns aggregated status. `wait_for_ci()` polls every 15s up to `max_ci_retries`. `auto_check_pr_template()` counts deterministic checkboxes (unchecked = 0). `check_compliance_and_fix()` — after 15s delay, fetches bot comments (coderabbitai, copilot, github-actions, dependabot, renovate, sweep-ai), auto-fixes title/issue-ref, signs CLA. `_human_branch_name()` generates semantic prefixes (fix/, feat/, perf/, docs/, refactor/, improve/) without any tool branding. `_handle_cla_signing()` — CLAAssistant: bot edits CLA.yml file directly to add author; EasyCLA: posts "I have signed the CLA" comment. `_generate_issue_body()` generates the body for issue-first proposals. `close_pr()` closes a PR with an explanation.

#### `pr/patrol.py`
`PRPatrol` — Patrol loop for reviewing and interacting with existing PRs. `REVIEW_BOT_LOGINS`: coderabbitai, copilot, github-actions, dependabot, renovate, sweep-ai, SocketRT, ResolverBot, Mounted.ai, Pull, Lego, Terra, Octomerge, Mergify, Auto-PR. `CI_INFRA_IGNORE_PATTERNS`: vercel, cloudflare, pages, netlify, codecov, cla/, license/, dependabot/, renovate/. `GITHUB_REPLIES` — human-like response dictionary keyed by action type. `review_and_respond()` — WPM delay simulation, generates LLM response using `GITHUB_REPLIES` as injection examples. `should_surrender()` — if `max_review_per_repo` exhausted, posts farewell comment and exits. `patrol(pr_records, dry_run)` iterates over open and pending PRs from memory. Handles issue-like comments (links existing issues to PR). `reviewed_prs` set avoids re-reviewing. Tracks `discussion_replies` via `memory.increment_discussion_replies()`. CI auto-heal: if infra error detected, downloads check run logs, generates corrective commit, force-pushes. Increments `ci_fix_attempts` via `memory.increment_ci_fix_attempts()`.

#### `pr/janitor.py` — **The Ruthless Janitor (Independent Protocol)**
`PRJanitor` — Independent of the main pipeline. Operates purely on live GitHub state. `sweep_and_destroy()` fetches all open PRs via `github.fetch_user_open_prs(username)`, classifies each via LLM as GARBAGE or CRITICAL. **SYSTEM_PROMPT** classifies GARBAGE if: (1) Exploratory — title says understand, explore, read, investigate, look at, see current, (2) Documentation — typo fixes, README updates, docstring improvements, (3) Formatting — whitespace, indentation, PEP8, Prettier, linting, (4) Low-impact — purely cosmetic, renaming, chore, refactor with no logic/security fix, (5) Test-only. CRITICAL only if real logic bug fix, proven security vulnerability, memory/leak/race-condition fix, or critical architectural correction. Returns summary dict: total_scanned, garbage_closed, critical_spared, errors, details. On GARBAGE verdict: calls `github.close_pull_request()` with Janitor comment, attempts `github.delete_branch()`. On CRITICAL: spares the PR and logs it. Idempotent: re-running marks previously closed PRs as already-closed (GitHub API handles gracefully). Used by the `farm_agent janitor` CLI command.

#### `scheduler/scheduler.py`
`ContribScheduler` — APScheduler wrapper using `AsyncIOScheduler` with `CronTrigger`. `add_hunt_job()` / `add_patrol_job()` schedule recurring tasks. SIGINT/SIGTERM graceful shutdown (waits for running jobs via `shutdown(wait=True)`). Used by the `schedule` CLI subcommand.

#### `templates/registry.py`
`TemplateRegistry` — Manages PR template library. Loads templates from `farm_agent/templates/`. Used by the `templates` CLI subcommand.

#### `plugins/base.py`
`PluginRegistry` — Base plugin system for extensibility. Plugins can register new analyzers, generators, or notification channels.

#### `notifications/notifier.py`
`Notifier` — Persistent httpx async client. `send_telegram()` / `send_slack()` / `send_discord()` fire webhook payloads. `send_diff()` posts formatted diffs with file-level chunking. All sends are fire-and-forget with error logging. `TelegramNotifier` background poller started/stopped as separate task.

#### `tools/protocol.py`
`ToolRegistry` — Registers and executes tools. `GitHubTool` (BLOCKED_EXTENSIONS: .zip, .png, .jpg, .gif, .pdf; MAX_FILE_SIZE=100000 bytes; methods: read_file, search_code, list_directory, get_file_history). `READ_FILE_TOOL_SCHEMA` — JSON schema for the read_file tool used in function calling. `LLMTool` — wrapper for LLM calls. Tools can be registered and retrieved by name. `create_default_tools()` constructs the default tool set.

---

## 2. Core Execution Flows

### Protocol 4: SuperHuman Loop with Alumni Sync (`farm_agent/orchestrator/human.py`)

```
Entry: farm_agent superhuman
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  SuperHumanLoop.run_daily_routine()                     │
│                                                         │
│  [STARTUP]                                              │
│  1. Sync RAM counter from DB via get_today_pr_count()  │
│  2. Start Telegram poller (background, crash-restart)   │
│  3. _sync_historical_friendly_repos() — FIRST RUN      │
│     └─ fetch_user_merged_prs(username)                 │
│     └─ filter by stars_range (e.g. 1000-20000)         │
│     └─ INSERT OR IGNORE into submitted_prs (merged)    │
│                                                         │
│  [EVERY 24 HOURS]                                       │
│  _sync_historical_friendly_repos()                      │
│                                                         │
│  [EVERY ITERATION]                                      │
│  Mode dice roll: random() < 0.60 → HUNT else PATROL    │
│                                                         │
│  [HUNT PATH]                                            │
│  _do_hunt()                                             │
│    DB check: get_today_pr_count() ≥ daily_target?      │
│      → skip hunt, go to patrol                          │
│    └─ hunt() → discovery + Familiar Grounds first       │
│       └─ memory.get_friendly_repos_for_hunting()        │
│          (merged repos off 7-day cooldown)              │
│       └─ RepoDiscovery.discover()                       │
│       └─ _process_repo() (up to 2 PRs per repo)       │
│    Counter only increments on ACTUAL PR creations        │
│    After PR: sleep 15-45 min before next action        │
│                                                         │
│  [PATROL PATH]                                          │
│  _do_patrol()                                           │
│    memory.get_prs(status=open/pending)                  │
│    PRPatrol.patrol(pr_records)                          │
│                                                         │
│  [QUOTA MET → PATROL-ONLY MODE]                         │
│  prs_created_today ≥ daily_target                       │
│    → long 1-3h delays between patrol cycles             │
│    → no more hunting until new local day                │
│                                                         │
│  [MANDATORY LUNCH BREAK]                                │
│  local_now.hour == 12 and not _took_lunch_today        │
│    → sleep from 12:00 to 13:01 local time              │
└─────────────────────────────────────────────────────────┘
```

### Protocol 1+2+6: The Hunting Pipeline (`farm_agent/orchestrator/pipeline.py`)

```
Entry: farm_agent hunt / farm_agent run
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  ContribPipeline.hunt()  (multi-round)                 │
│                                                         │
│  [FAMILIAR GROUNDS — Protocol 2]                        │
│  Before wild discovery, query:                           │
│    memory.get_friendly_repos_for_hunting(               │
│      limit=min(remaining,2), cooldown_days=7)           │
│  Prepend friendly repos to target list (trusted first)   │
│                                                         │
│  [WILD DISCOVERY — varied star tiers per round]        │
│  RepoDiscovery.discover()                                │
│  └─ Star tiers: cfg_range, 100-1k, 1k-5k, 5k-20k, 500-3k│
│                                                         │
│  [PARALLEL REPO PROCESSING]                             │
│  asyncio.gather(_hunt_process_repo(repo) for repo ...)  │
│  max_concurrent = min(config, 5) [CRIT-03 fix]          │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  _hunt_process_repo(repo)                              │
│                                                         │
│  [ISSUE-FIRST] mode=issues/both (higher value)         │
│    └─ _process_repo_issues(repo)                       │
│       └─ IssueSolver.fetch_solvable_issues()            │
│       └─ IssueSolver.solve_issue_deep()                │
│       └─ Generator.generate()                          │
│       └─ PRManager.create_pr(closes_issue=N)           │
│       If ≥1 issue-based PR created → SKIP static analysis│
│                                                         │
│  [STATIC ANALYSIS] mode=analysis/both                  │
│    └─ _process_repo(repo)                              │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  _process_repo(repo) — 12 stages                       │
│                                                         │
│  1. AI Policy Check  ─ AI_POLICY.md or anti-AI in     │
│     CONTRIBUTING.md → skip if banned                    │
│                                                         │
│  2. Interaction Limits  ─ check_interaction_limits()   │
│     (prior-contributor-only repos → 422 → skip)        │
│                                                         │
│  3. Maintainer Vibe Check                             │
│     fetch_recent_maintainer_comments()                 │
│     → LLM classify → HOSTILE → blacklist → skip        │
│                                                         │
│  4. Fetch Guidelines                                  │
│     fetch_repo_guidelines(CONTRIBUTING.md)             │
│                                                         │
│  5. Analyze  ─ CodeAnalyzer.analyze(repo)             │
│     7 strategies via asyncio.gather                    │
│     → list[Finding]                                   │
│                                                         │
│  6. Pre-Filter (Non-Code)                             │
│     SKIP_EXTENSIONS + PROTECTED_META_FILES            │
│                                                         │
│  7. Anti-Farming Gate                                 │
│     Only CRITICAL/HIGH impact survive                  │
│     Farming keyword blacklist (docstring, typo, format, │
│     understand, explore, read, look at, investigate,   │
│     test, testing, todo, fixme, chore, unused import) │
│                                                         │
│  8. Duplicate Detection                               │
│     memory.get_repo_prs() + github.list_pull_requests()│
│     Title similarity (>50% keyword overlap)             │
│     Same file paths in PR bodies                       │
│                                                         │
│  9. Validate Findings (False Positive Filter)         │
│     LLM re-examines each finding against full file     │
│     content: is code already protected? Is data bounded?│
│     Is function only called from safe contexts?        │
│                                                         │
│  10. Hybrid Contribution Router (Protocol 1)           │
│      Route A (Direct PR / Firefighter):                │
│        SECURITY_FIX OR severity CRITICAL/HIGH          │
│        → generate code immediately                     │
│      Route B (Issue-First / Polite Senior):            │
│        everything else                                  │
│        → create_issue() → memory.record_issue_proposal()│
│                                                         │
│  11. [For Route A] Generator.generate()                │
│      ├─ X-Ray Vision (Protocol 6)                     │
│      │   └─ RepoIndexer.index_repo() (ChromaDB)       │
│      │   └─ RepoIndexer.query_context()               │
│      │   └─ Returns semantically related code chunks  │
│      ├─ ContributionGenerator                          │
│      │   └─ 4-pass patch parser (exact, fuzzy, strip, │
│      │      indent-agnostic)                           │
│      │   └─ Diff Minimizer (reject >30 lines if       │
│      │      search <5 lines)                           │
│      │   └─ _self_review() → APPROVE/REJECT            │
│      ├─ Red Team Adversarial Loop (Protocol 7)        │
│      │   └─ ReviewerAgent.review()                    │
│      │   └─ if REJECT → Generator rewrites with       │
│      │      critique → ReviewerAgent.review() again   │
│      │   └─ up to max_review_retries (default 2)      │
│      │   └─ if still reject → discard contribution    │
│      │                                                 │
│      ├─ Polyglot Sandbox (Protocol 5)                 │
│      │   └─ DockerSandbox.run_in_sandbox()            │
│      │   └─ language auto-detected (ext or API)       │
│      │   └─ LANGUAGE_ENVIRONMENTS[lang]["test_cmd"]  │
│      │   └─ timeout=60s, mem_limit=512m, cap_drop=ALL │
│      │   └─ exit_code=137 → retry (max 3)            │
│      │   └─ all fail → PR creation blocked            │
│      │                                                 │
│      ├─ Human WPM Delay                               │
│      │   └─ base 300-900s + patch_length/3.75s       │
│      │   └─ max 3600s total                           │
│      │                                                 │
│      ├─ GitHub PR Creation                             │
│      │   └─ fork → branch → create_or_update_file()  │
│      │   └─ DCO signoff, author timestamp jitter     │
│      │   └─ create_pull_request()                    │
│      │                                                 │
│      ├─ Compliance Check                              │
│      │   └─ auto-fix title, issue-ref, CLA sign     │
│      │                                                 │
│      └─ CI Wait                                       │
│          └─ poll check runs (15s interval)            │
│          └─ failure → leave open for Patrol auto-heal │
│                                                         │
│  12. Record to Memory                                  │
│      memory.record_pr() / memory.record_issue_proposal()│
│      memory.record_analysis()                          │
└─────────────────────────────────────────────────────────┘
```

### Patrol & Auto-Heal Loop (`farm_agent/pr/patrol.py`)

```
Entry: farm_agent patrol
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  PRPatrol.patrol(pr_records)                           │
│    memory.get_prs(status=open/pending)                 │
│    For each PR (up to max_review_per_repo):           │
│                                                         │
│      WPM delay simulation (bimodal)                   │
│                                                         │
│      review_and_respond(pr)                             │
│        fetch_comments(pr)                              │
│        filter out REVIEW_BOT comments                   │
│        build context from GITHUB_REPLIES examples       │
│        LLM generate response                           │
│        post_comment()                                   │
│        memory.increment_discussion_replies()            │
│                                                         │
│      check_ci_status(pr)                               │
│        CI_INFRA_IGNORE_PATTERNS filter                 │
│        (vercel, netlify, codecov, CLA bots → ignored)   │
│        → infra error → CI auto-heal                    │
│          └─ download_check_run_log()                   │
│          └─ generate corrective commit                 │
│          └─ force-push to PR branch                   │
│          └─ memory.increment_ci_fix_attempts()        │
│                                                         │
│      should_surrender(pr)                               │
│        if max_review_per_repo exhausted:                │
│          post farewell comment → exit loop              │
└─────────────────────────────────────────────────────────┘
```

---

## 3. The 7 Enterprise-Grade Protocols

### Protocol 1: Hybrid Approach — Issue-First vs Direct PR Routing
**Location**: `farm_agent/orchestrator/pipeline.py` lines 984-996 (`_process_repo()`) and lines 1120-1215 (`_propose_issue_first()`).

**Decision logic**:
```python
is_direct_pr = (
    finding.type == ContributionType.SECURITY_FIX
    or finding.severity in (Severity.CRITICAL, Severity.HIGH)
)
```
- **Route A (Direct PR / Firefighter)**: SECURITY_FIX or CRITICAL/HIGH severity → immediate code generation → PR creation. Treats the finding as an emergency requiring instant action.
- **Route B (Issue-First / Polite Senior)**: everything else (CODE_QUALITY, PERFORMANCE_OPT, REFACTOR, FEATURE_ADD, UI_UX_FIX) → polite GitHub Issue proposal → wait for maintainer buy-in → no code generated until maintainer responds.

**Why it matters**: Prevents aggressive, large-diff PRs for subjective improvements on repos where maintainers prefer discussion first. Routes lower-risk changes through an opt-in issue channel rather than an unsolicited PR.

### Protocol 2: Familiar Grounds — Prioritizing Alumni Repos
**Location**: `farm_agent/orchestrator/pipeline.py` lines 369-437 (`hunt()` method) and `farm_agent/orchestrator/memory.py` lines 282-324 (`get_friendly_repos_for_hunting()`).

**Logic**: Before spending API tokens on new discoveries, query `submitted_prs` for repos where we have `status='merged'` and the repo is off-cooldown (not analyzed in last 7 days). These repos have proven they accept our PRs. Prepend them to the discovery target list with priority. Star-filter applied against `discovery.stars_range` (e.g. 1000-20000).

**Why it matters**: Our highest-conversion repos are the ones that already merged us. By hunting alumni first, we maximize merge-rate efficiency and minimize wasted API calls on repos that would reject us.

### Protocol 3: Immortal Memory — Persistent `./data/memory.db` SQLite DB
**Location**: `farm_agent/orchestrator/memory.py` and `farm_agent/core/config.py` line 120 (`db_path = "data/memory.db"`).

**Persistence**: `StorageConfig.resolved_db_path` → `data/memory.db`. SQLite with WAL journal mode. Survives restarts. WAL mode enables concurrent reads during writes. `aiosqlite` for full async support.

**Why it matters**: All learned state (PR history, outcome rates, repo preferences, blacklists, API usage quotas) persists across restarts. The 24h Alumni Sync (Protocol 4) populates it with historical merged PRs on startup and every 24h thereafter.

### Protocol 4: Alumni Sync — 24h Background Sync of Historically Merged PRs
**Location**: `farm_agent/orchestrator/human.py` lines 323-436 (`_sync_historical_friendly_repos()`) and lines 533-553 (24h timer in `run_daily_routine()`).

**Flow**:
1. `github.fetch_user_merged_prs(username)` → paginated GitHub search API (up to 1000 merged PRs).
2. Deduplicate by repo (one entry per repo, most recent merged PR wins).
3. For each repo: check star count via `github.get_repo_details()` against `discovery.stars_range`.
4. `INSERT OR IGNORE INTO submitted_prs (status='merged')` — idempotent, safe to re-run.
5. Runs on startup and then every 24 hours (`elapsed > 86400` check).

**Why it matters**: Populates Familiar Grounds (Protocol 2) with our complete historical merged PR network. After 24h, even if the bot was offline, it re-syncs to discover new repos where our PRs got merged while it was down.

### Protocol 5: Polyglot Guillotine — Multi-Language Docker Execution
**Location**: `farm_agent/core/sandbox.py` lines 21-77 (`LANGUAGE_ENVIRONMENTS` dict) and lines 179-322 (`run_in_sandbox()`).

**Supported languages and images**:
| Language | Image | Test Command |
|---|---|---|
| python | python:3.11-alpine | pip install pytest && pytest |
| javascript | node:20-alpine | npm install && npm test |
| typescript | node:20-alpine | npm install && npx tsc --noEmit |
| rust | rust:1.75-alpine | cargo test || cargo build |
| go | golang:1.21-alpine | go test ./... || go build |
| java | eclipse-temurin:21-jdk-alpine | mvn test || gradle test |
| ruby | ruby:3.3-alpine | bundle install && bundle exec rake test |
| php | php:8.2-cli-alpine | composer install && phpunit |
| c | gcc:14-bookworm | make test |
| cpp | gcc:14-bookworm | make test |
| csharp | mcr.microsoft.com/dotnet/sdk:8.0-alpine | dotnet test |

**Language detection priority**: explicit `language` parameter → `repo_info` GitHub API metadata → file extension scan of the repo directory.

**Why it matters**: Every code change is validated in an ephemeral container with the correct language runtime before being pushed. Exit code 137 (SIGKILL) means the process was OOM-killed or timed out. The container is force-removed in the `finally` block regardless of outcome.

### Protocol 6: X-Ray Vision — Local Ephemeral RAG using ChromaDB
**Location**: `farm_agent/core/rag.py` (`RepoIndexer`, `chunk_file()`, `_embed_texts_fallback()`) and `farm_agent/generator/engine.py` lines 579-656 (`_find_cross_file_instances()`).

**Flow**:
1. `ContributionGenerator._find_cross_file_instances()` is called during patch generation.
2. Creates a `RepoIndexer()` instance (RAM-only ChromaDB).
3. `index_repo()` chunks all `context.relevant_files` using sliding window (1200 chars, 200 char overlap).
4. Files matching `EXCLUDE_PATTERNS` (node_modules, dist/, build/, vendor/, .min.js, .map.js, .pyc, .lock, .wasm, binaries) are skipped. Files >200KB skipped.
5. `_embed_texts_fallback()` generates 128-dim word-frequency L2-normalized embeddings (deterministic sort order).
6. `query_context()` with the finding title+description+suggestion as query, returns top 8 semantically similar chunks from up to 3 other files.
7. These related chunks are injected into the Generator's prompt, giving it cross-file context ("X-Ray Vision").
8. `indexer.destroy()` frees RAM immediately after query. `__del__` guarantees cleanup on GC.

**ChromaDB fallback**: If ChromaDB import fails, `_embed_texts_fallback` is never called and `indexer.query_context()` silently returns `[]` — the Generator proceeds without cross-file context.

### Protocol 7: Red Team Adversarial Review — ReviewerAgent Rejecting Bad Code
**Location**: `farm_agent/generator/reviewer.py` (`ReviewerAgent`).

**Adversarial loop** (integrated into `ContribPipeline._process_repo()` when `self._sandbox` is configured):
1. `Generator.generate()` produces a `Contribution` with `list[FileChange]`.
2. `ReviewerAgent.review(contribution, context)` is called with a completely independent LLM instance.
3. The ReviewerAgent's system prompt is adversarial: "find every flaw", "MUST distrust the patch author".
4. Checks: HALLUCINATED VARIABLES, INCOMPLETE FIX, REGRESSIONS, LOGIC ERRORS, STYLE VIOLATIONS, INCORRECT SCOPE.
5. Returns `{"decision": "APPROVE"|"REJECT", "critique": "specific line/variable critique"}`.
6. If REJECT: the Generator rewrites using the critique as feedback → Step 2 again.
7. Up to `max_review_retries` (default 2) iterations.
8. If still reject: contribution discarded, no PR created.

**Why it matters**: The Generator and ReviewerAgent are distinct adversarial entities with separate LLM instances and separate conversational histories. A REJECT verdict means the independent reviewer found a concrete, specific flaw — not just stylistic disagreement.

---

## 4. Data Flows & State Management

### GitHub API → memory → LLM → sandbox → git push

```
GitHub API (httpx async)
    │
    ├── GET /repos/{owner}/{repo}         → repo metadata (stars, language)
    ├── GET /search/repositories           → discovery results
    ├── GET /search/issues (author:+is:pr+is:merged) → Alumni Sync
    ├── GET /repos/{owner}/{repo}/issues  → open issues
    ├── GET /repos/{owner}/{repo}/comments → PR comments (vibe check)
    ├── GET /repos/{owner}/{repo}/pulls   → open PRs (patrol)
    ├── GET /repos/{owner}/{repo}/commits  → commit history (style mimicry)
    ├── GET /repos/{owner}/{repo}/commits/{ref}/check-runs → CI status
    ├── GET /repos/{owner}/{repo}/interaction-limits → prior-contributor check
    └── DELETE /repos/{o}/{r}/git/refs/heads/{branch} → branch deletion

GitHubClient.create_or_update_file()
    │
    ├── fetch current blob SHA (GET /repos/{o}/{r}/contents/{path})
    ├── append DCO signoff line to commit message
    ├── set author timestamp: now - random(15..45) minutes
    └── PUT /repos/{owner}/{repo}/contents/{path}
            │
            ▼
Memory (SQLite WAL — data/memory.db)
    │
    ├── analyzed_repos       ← record_analysis()
    ├── submitted_prs        ← record_pr() / record_issue_proposal()
    ├── findings_cache       ← duplicate detection
    ├── run_log             ← start_run() / finish_run()
    ├── pr_outcomes         ← record_outcome()
    ├── repo_preferences    ← auto-updated from outcomes
    ├── blacklisted_repos   ← blacklist_repo()
    └── api_usage_log       ← check_and_record_llm_quota()
            │
            ▼
LLM (MinimaxProvider / MiniMax M2.7)
    │
    ├── CodeAnalyzer         → 7 strategy prompts → Finding[]
    ├── ContributionGenerator → Finding + RepoContext → FileChange[]
    ├── check_maintainer_vibe() → WELCOMING/STRICT/HOSTILE
    ├── _self_review()       → APPROVE/REJECT
    ├── _validate_findings() → VALID/INVALID (false positive filter)
    ├── ReviewerAgent        → APPROVE/REJECT (independent LLM)
    └── PatrolAgent          → PR response text
            │
            ▼
RepoIndexer (ChromaDB ephemeral — RAM only)
    │
    ├── index_repo()         → chunk files, generate embeddings
    ├── query_context()      → semantic cross-file search
    └── destroy()            → free RAM immediately
            │
            ▼
DockerSandbox (Polyglot Guillotine)
    │
    ├── run_in_sandbox()     → language auto-detection
    ├── LANGUAGE_ENVIRONMENTS[lang]["image"]
    ├── LANGUAGE_ENVIRONMENTS[lang]["test_cmd"]
    ├── mem_limit="512m", network_disabled=True
    ├── cap_drop=["ALL"], pids_limit=128
    ├── timeout=60s
    ├── exit_code=137 → SIGKILL → retry (max 3)
    └── stdout/stderr → sandbox result dict
            │
            ▼
Git push (via GitHubClient.create_or_update_file)
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
    type        TEXT NOT NULL,  -- code_quality, security_fix, issue_proposal, etc.
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
| `Finding` | `core/models.py` | id, type (ContributionType), severity (Severity), impact_level (ImpactLevel), title, description, file_path, line_start, line_end, suggestion, priority_score |
| `FileChange` | `core/models.py` | path, original_content, new_content, is_new_file |
| `RepoContext` | `core/models.py` | repo, branch, file_tree, readme_content, contributing_guide, relevant_files, commit_history, recent_prs, guidelines, coding_style |
| `Contribution` | `core/models.py` | finding, contribution_type, title, description, changes (list[FileChange]), commit_message, branch_name |
| `FarmAgentConfig` | `core/config.py` | github, llm, analysis, contribution, discovery, storage, scheduler, web, pipeline, quota, notifications, logging, multi_model |
| `Model` | `llm/models.py` | provider, name, temperature, max_tokens |
| `Guidelines` | `github/guidelines.py` | has_guidelines, preferred_types, forbidden_types, commit_format, pr_title_format, scope_rules, required_sections |
| `PipelineContext` | `core/middleware.py` | repo, finding, changes, error, retry_count, metadata |
| `Repository` | `core/models.py` | owner, name, full_name, description, language, stars, forks, open_issues, topics, default_branch, html_url, clone_url, has_license |
| `CodeChunk` | `core/rag.py` | content, file_path, chunk_index, total_chunks, doc_id |

---

## 5. Edge Cases & Fallback Protocols

### Edge Case 1: Sandbox Guillotine (All Retries Fail)
**Trigger**: `DockerSandbox.run_in_sandbox()` returns `exit_code=137` (SIGKILL) on all 3 attempts (configurable via `max_retries` in `pipeline.max_ci_retries`).
**Flow**:
```
DockerSandbox.run_in_sandbox() → exit_code=137 → retry 1
DockerSandbox.run_in_sandbox() → exit_code=137 → retry 2
DockerSandbox.run_in_sandbox() → exit_code=137 → retry 3
→ log "SANDBOX GUILLOTINE: PR creation blocked"
→ continue to next finding (skip this one)
→ Memory.record_analysis() with findings_count decremented
```
**Why it matters**: Prevents hallucinated code from being pushed. Exit 137 means the container was killed by the OOM killer (mem_limit=512m exceeded) or the 60s wall-clock limit was exceeded.

---

### Edge Case 2: ChromaDB Out of Memory
**Trigger**: ChromaDB `EphemeralClient` exhausts available RAM while indexing large repositories.
**Flow**:
```
RepoIndexer.index_repo()
  → chunks = chunk_file() for all files
  → embeddings = _embed_texts_fallback(texts)  [RAM pressure here]
  → chromadb.EphemeralClient() add() call
  → OS OOM killer sends SIGKILL to farm_agent process
OR:
  → chromadb throws MemoryError internally
```
**Fallback**: ChromaDB is imported with `try/except ImportError` in `_init_chroma()`. If `import chromadb` fails, `_chroma` is set to `None` and `_collection` to `None`. All subsequent `index_repo()` and `query_context()` calls check `if self._collection is None: return []` (empty results). The Generator proceeds without cross-file context using regex-based `_extract_search_patterns()` as the fallback.
**Why it matters**: RAM-only ChromaDB has no swap. On memory-constrained systems (e.g. 512MB RAM Docker containers), indexing a large repo with many chunks can trigger the OOM killer. The silent fallback ensures the pipeline continues without crashing.

---

### Edge Case 3: ReviewerAgent Rejects 3 Times (Max Review Retries Exceeded)
**Trigger**: `ReviewerAgent.review()` returns `decision=REJECT` on all `max_review_retries` (default: `pipeline.max_review_retries=2`, so 3 total attempts: initial + 2 retries).
**Flow**:
```
Generator.generate() → Contribution
ReviewerAgent.review() → REJECT: "Line 42: variable 'token' referenced but never defined"
  → Generator rewrites using critique
  → ReviewerAgent.review() → REJECT: "Still missing null check on line 50"
  → Generator rewrites using new critique
  → ReviewerAgent.review() → REJECT: "Regressions introduced in adjacent function"
→ log "Contribution rejected by adversarial reviewer after 3 attempts"
→ contribution discarded (no PR created)
→ Memory NOT updated with a PR record
→ Continue to next finding
```
**Why it matters**: Three consecutive REJECT verdicts from an independent adversarial reviewer indicate a fundamental flaw in the generated patch — either a hallucination the Generator keeps repeating, or a logic error that requires human-level understanding to fix. Discarding the contribution prevents bad PRs from polluting the bot's history.

---

### Edge Case 4: Anti-Farming Gate Blocks Everything
**Trigger**: All findings from a repo are dropped by the anti-farming gate (MEDIUM/LOW/TRIVIAL impact + farming keywords detected).
**Flow**:
```
CodeAnalyzer.analyze() → 5 findings
Anti-farming gate → all 5 dropped (impact=MEDIUM or farming keywords)
Memory.record_analysis(repo, findings_count=0)
No PR created
```
**Why it matters**: Prevents noise PRs on repos that only have documentation issues or trivial typos. CRITICAL/HIGH findings bypass this gate entirely.

---

### Edge Case 5: HOSTILE Maintainer Vibe
**Trigger**: LLM classifies recent PR comments as HOSTILE.
**Flow**:
```
fetch_recent_maintainer_comments() → [comments]
check_maintainer_vibe(comments) → "HOSTILE"
memory.blacklist_repo(owner, repo, "HOSTILE maintainer")
Memory.blacklisted_repos INSERT
Next _process_repo() call → is_blacklisted() → skip immediately
```
**Why it matters**: Permanent protection against hostile communities. The bot never targets a HOSTILE repo again, even across restarts (persisted in SQLite).

---

### Edge Case 6: Minimax LLM Rate Limit
**Trigger**: `api_usage_log` count ≥ 950 in 5-hour window OR ≥ 9500 in 7-day window.
**Flow**:
```
check_and_record_llm_quota() → LLMRateLimitError raised
in SuperHumanLoop._do_hunt():
    except LLMRateLimitError:
        sleep 3600 (1 hour cooldown)
        continue to next iteration
in ContribPipeline:
    except LLMRateLimitError:
        logger.warning("LLM quota exhausted, sleeping 30 min")
        await asyncio.sleep(1800)
        retry
```
**Why it matters**: Prevents hitting Minimax hard limits which would block the API key entirely. The 95% safety buffer (950 instead of 1000) gives headroom for the safety margin.

---

### Edge Case 7: GitHub Rate Limit (Secondary Abuse Detection)
**Trigger**: 403 response with no `X-RateLimit-Remaining` header (abuse detection, not primary rate limit).
**Flow**:
```
GitHubClient._request() → 403 no remaining header
→ sleep 60s → retry
→ 403 again → sleep 120s → retry
→ still failing → raise GitHubAPIError
Pipeline retries with exponential backoff via RetryMiddleware
```
**Why it matters**: Distinguishing abuse 403 (retryable) from hard rate limit 403 (remaining==0, immediate fail) is critical for reliability.

---

### Edge Case 8: CLA Signing — EasyCLA (Manual)
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

### Edge Case 9: CI Auto-Heal Surrender
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

### Edge Case 10: Patch Parsing — All 4 Passes Fail
**Trigger**: LLM returns a patch that fails all 4 matching passes in `_parse_changes()`.
**Flow**:
```
_parse_changes() → Try exact → Try whitespace-normalized
→ Try stripped → Try indentation-agnostic
→ all fail → logger.warning("Search text not found")
→ edits_applied = 0 → file skipped
No FileChange appended to changes list
Contribution may be discarded (if all files fail)
```
**Why it matters**: The Diff Minimizer + 4-pass parser together form a strong hallucination guard. If the LLM's own output cannot be matched back to the input, the change is discarded rather than applied blindly.

---

### Edge Case 11: Fork Exhaustion
**Trigger**: User hits `fork_count` limit (GitHub: ~100 for free, ~250 for paid).
**Flow**:
```
create_fork() → GitHub API returns 403 or 404
→ log "Fork limit reached or fork unavailable"
→ skip this repo, continue to next in discovery list
get_stats() → used in quota check
```
**Why it matters**: GitHub has per-user/organization fork limits. The bot gracefully skips repos it cannot fork rather than crashing.

---

### Edge Case 12: Docker Image Pull Failure (Polyglot Guillotine)
**Trigger**: `client.images.pull(image)` fails (e.g. network issues, image not found for a niche language).
**Flow**:
```
_start_container() → ImageNotFound
→ logger.info("Pulling missing sandbox image %s", image)
→ client.images.pull(image)
→ retry _run_container()
If pull fails or second run fails:
  → exception propagates up
  → pipeline skips sandbox validation
  → PR creation may proceed without sandbox check (depending on config)
```
**Why it matters**: For niche languages (e.g. Rust Alpine variant), the Docker Hub image may not exist. The pull-retry pattern handles transient network failures. If the image truly doesn't exist, the exception prevents silent failure.

---

### Edge Case 13: PRJanitor Classifies Critical PR as GARBAGE (False Positive)
**Trigger**: `PRJanitor._classify_pr()` misclassifies a legitimate exploratory PR as GARBAGE and closes it.
**Flow**:
```
fetch_user_open_prs() → [PRs]
_classify_pr(title, body) → LLM call
→ LLM classifies as GARBAGE despite PR being a legitimate fix
→ close_pull_request() called
```
**Mitigation**: The Janitor's system prompt is extremely strict about what constitutes GARBAGE (exploratory, doc-only, formatting, cosmetic, test-only). Any PR with actual code logic is classified as CRITICAL and spared. The Janitor operates on the bot's OWN open PRs only, not third-party repos.
**Why it matters**: The Janitor protects account reputation by closing the bot's own low-quality PRs before they accumulate and get the account flagged.

---

### Edge Case 14: Local Date vs UTC Date (PR Count)
**Trigger**: User is in UTC+7 timezone. A PR created at 01:00 local time (18:00 UTC previous day) must count toward today's local quota.
**Flow**:
```
get_today_pr_count():
    utc_now = datetime.now(UTC)
    local_now = utc_now.astimezone()  # OS timezone
    today_local = local_now.date().isoformat()
    cursor = db.execute(
        "SELECT COUNT(*) FROM submitted_prs WHERE created_at LIKE ?",
        (f"{today_local}%",)  -- matches "2026-03-29T01:00:00" local
    )
```
**Why it matters**: The old UTC-based query would miss PRs created in the 6-hour window between midnight UTC and the user's local dawn, causing the quota check to allow over-creation.

---

## 6. CLI Subcommands Reference

| Command | File | Description |
|---|---|---|
| `run` | `cli/main.py` | Full pipeline: discover → analyze → generate → PR |
| `target` | `cli/main.py` | Single specific repo through the pipeline |
| `hunt` | `cli/main.py` | Multi-round aggressive hunting with Familiar Grounds |
| `patrol` | `cli/main.py` | PR review and auto-heal loop |
| `superhuman` | `cli/main.py` | 24/7 stochastic daemon with Telegram poller |
| `analyze` | `cli/main.py` | Static analysis only (no PR creation) |
| `solve` | `cli/main.py` | Issue solver: find and fix open issues |
| `status` | `cli/main.py` | Today's PR count and quota status |
| `stats` | `cli/main.py` | Merge rate and repo preferences |
| `cleanup` | `cli/main.py` | Remove old forks and branches |
| `config` | `cli/main.py` | Validate config.yaml |
| `serve` | `cli/main.py` | FastAPI web server |
| `schedule` | `cli/main.py` | APScheduler cron jobs |
| `templates` | `cli/main.py` | PR template library |
| `profile` | `cli/main.py` | Model profile management |
| `models` | `cli/main.py` | List available LLM models |
| `interactive` | `cli/main.py` | Rich TUI interface |
| `leaderboard` | `cli/main.py` | Top repos by merge rate |
| `notify-test` | `cli/main.py` | Webhook test |
| `system-status` | `cli/main.py` | Full diagnostics |
| `janitor` | `cli/main.py` | Sweep and destroy garbage PRs |

---

## 7. Configuration Reference

**`config.example.yaml`** key values:
```yaml
github:
  max_prs_per_day: 10
  min_daily_prs: 3
  max_daily_prs: 10
  rate_limit_buffer: 100
  dco_signoff: true

discovery:
  stars_range: [1000, 20000]   # Shark Tank
  languages: [python]
  min_last_activity_days: 7

pipeline:
  max_concurrent_repos: 3
  max_ci_retries: 3
  max_discussion_replies: 3
  max_patch_retries: 2
  max_review_retries: 2

storage:
  db_path: data/memory.db

multi_model:
  enabled: false

notifications:
  telegram_token: ""
  telegram_chat_id: ""
```

**Docker Compose** (`docker-compose.superhuman.yml`):
- Service name: `agent`
- Build: `Dockerfile.superhuman` (python:3.11-slim-bookworm + git + docker.io)
- Container name: `farm_agent_core`
- `restart: unless-stopped`
- Mounts: `config.yaml` (ro), `farm_agent_data` (/root/.farm_agent:rw), `logs` (/app/logs:rw), Docker socket (`/var/run/docker.sock:rw`)
- Timezone: `Asia/Ho_Chi_Minh`
- CMD: `["farm_agent", "superhuman"]`
