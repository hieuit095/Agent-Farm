# 🗺️ Farm-Agent Project Map (v2.5.0)

> **Last synchronized:** 2026-03-31 — Derived from exhaustive source code analysis.
> This document reflects the **raw reality** of the codebase, not idealized designs.

---

## 1. System Overview & Tech Stack

Farm-Agent is an **autonomous AI agent** that discovers open-source GitHub repositories,
analyzes their code for real bugs and quality issues, generates fixes, submits pull requests,
monitors maintainer feedback, and auto-responds — all without human intervention.

### Active Tech Stack

| Layer              | Technology                | Notes                                         |
|--------------------|---------------------------|-----------------------------------------------|
| Language           | Python 3.11+              | `from __future__ import annotations` everywhere |
| Async Runtime      | `asyncio`                 | All I/O is `async/await`                      |
| HTTP Client        | `httpx` (async)           | Persistent `AsyncClient` with connection reuse |
| Database           | SQLite via `aiosqlite`    | WAL mode, single-file `memory.db`             |
| LLM Provider       | Minimax (ABAB models)     | REST API via `httpx`, semaphore-throttled     |
| GitHub API         | REST v3 via `httpx`       | Semaphore-guarded (concurrency=1)             |
| CLI Framework      | `click` + `rich`          | Rich console, logging, panels, tables         |
| Config             | `pydantic` + `PyYAML`     | `config.yaml` → `FarmAgentConfig` dataclass   |
| Docker             | `docker` (Python SDK)     | Sandbox for patch validation                  |
| RAG                | `chromadb` (ephemeral)    | In-memory, RAM-only semantic search           |
| Notifications      | Telegram Bot API          | Long-polling C2 command center                |
| Tests              | `pytest`                  | 333+ unit tests                               |
| Linting            | `ruff`                    | 100 char line length                          |

---

## 2. Module Dependency Graph

```
cli/main.py                              ← CLI entry point (click commands)
  └── orchestrator/pipeline.py           ← Core pipeline orchestrator
        ├── core/config.py               ← Pydantic config (FarmAgentConfig)
        ├── core/middleware.py            ← 5 ordered middlewares
        ├── core/sandbox.py              ← Docker-backed patch validation
        ├── core/rag.py                  ← ChromaDB ephemeral RAG engine
        ├── core/quotas.py               ← In-memory API quota tracker
        ├── core/retry.py                ← async_retry decorator + LRU cache
        ├── core/profiles.py             ← Named contribution profiles (presets)
        ├── core/leaderboard.py          ← PR merge/close rate tracking
        ├── core/daily_log.py            ← Append-only daily markdown logger
        ├── core/notifier.py             ← TelegramNotifier (C2 commands)
        ├── core/exceptions.py           ← Custom exception hierarchy
        ├── core/models.py               ← Data models (Repository, Finding, etc.)
        ├── github/client.py             ← HTTP client (semaphore=1, retry+backoff)
        ├── github/discovery.py          ← Repo search, filter, prioritize
        ├── github/guidelines.py         ← CONTRIBUTING.md + PR template parser
        ├── analysis/analyzer.py         ← CodeAnalyzer (7 analyzer types)
        │     ├── analysis/skills.py     ← 17 progressive skills (on-demand)
        │     └── analysis/mapper.py     ← RepoMapper (skeleton generation)
        ├── generator/engine.py          ← ContributionGenerator (code gen)
        │     └── generator/scorer.py    ← Quality scoring for contributions
        ├── pr/manager.py                ← PR lifecycle (fork→branch→commit→PR)
        ├── pr/patrol.py                 ← PR review monitor + auto-responder
        ├── pr/janitor.py                ← LLM-powered garbage PR destroyer
        ├── issues/solver.py             ← Issue-driven contribution engine
        ├── orchestrator/memory.py       ← SQLite persistence layer (8 tables)
        ├── orchestrator/human.py        ← SuperHumanLoop (stochastic daily routine)
        ├── agents/registry.py           ← 5 sub-agents (analyze/generate/patrol/compliance/issue)
        ├── tools/protocol.py            ← MCP-inspired tool interface + registry
        └── llm/provider.py              ← LLM abstraction (Minimax primary)
```

---

## 3. Core Execution Loops

### 3.1 Pipeline Modes

Farm-Agent has **6 entry points** exposed via CLI:

| Command         | Method                               | Purpose                                              |
|-----------------|--------------------------------------|------------------------------------------------------|
| `run`           | `ContribPipeline.run()`              | Auto-discover repos → analyze → PR                   |
| `target <url>`  | `ContribPipeline.run_single()`       | Target a specific repo                               |
| `hunt`          | `ContribPipeline.hunt()`             | Multi-round aggressive discovery                     |
| `patrol`        | `PRPatrol.patrol()`                  | Monitor open PRs for feedback                        |
| `superhuman`    | `SuperHumanLoop.run_daily_routine()` | Organic 24/7 loop (Hunt + Patrol)                    |
| `janitor`       | `PRJanitor.sweep_and_destroy()`      | LLM-evaluated garbage PR cleanup                     |
| `solve <url>`   | `IssueSolver.solve_issue()`          | Solve open issues in a repo                          |
| `analyze <url>` | `ContribPipeline.analyze_only()`     | Analysis without PR creation                         |
| `status`        | (memory query)                       | Show submitted PR status                             |
| `stats`         | (memory query)                       | Show aggregate statistics                            |
| `cleanup`       | (fork cleanup)                       | Delete forks with no open PRs                        |

### 3.2 Primary Pipeline Flow (`_process_repo`)

```
_process_repo(repo, dry_run, max_prs)
  │
  ├── 1. AI Policy Check → skip repos banning AI PRs
  ├── 2. Blacklist Check → skip blacklisted repos
  ├── 3. Fetch repo guidelines (CONTRIBUTING.md, PR template)
  ├── 4. CodeAnalyzer.analyze(repo) → AnalysisResult
  │     ├── Fetch file tree (recursive)
  │     ├── Select skills (language + framework detection)
  │     ├── LLM analysis with progressive skill loading
  │     └── Return list of Findings
  ├── 5. Anti-Farming Gate (STRICT):
  │     ├── Block README_FIX & DOCS_IMPROVE types (hard ban)
  │     ├── Filter out .md/.yml/.json/.toml file-only changes
  │     ├── Filter out protected meta files
  │     ├── Dedup against historical PRs (title similarity)
  │     ├── Quality score check (min threshold)
  │     └── Impact-level check
  ├── 6. ContributionGenerator.generate(finding, context)
  │     ├── X-Ray Vision: RAG-powered cross-file context
  │     ├── LLM generates patch (function-calling with read_file tool)
  │     ├── Quality scoring via ContributionScorer
  │     └── Return Contribution with Changes
  ├── 7. DockerSandbox validation (if available)
  │     ├── Detect language → pick Docker image
  │     ├── Apply patch in container
  │     ├── Run test suite with hard timeout (120s)
  │     └── Grade: pass/fail/inconclusive
  ├── 8. Atomic PR Quota Check (inside _human_typing_lock):
  │     ├── Re-check get_today_pr_count() under lock
  │     ├── Prevent concurrent quota overshoot
  │     └── Abort if limit reached
  ├── 9. PRManager.create_contribution_pr()
  │     ├── Fork repo (or reuse existing fork)
  │     ├── Create branch
  │     ├── Commit changes (with DCO signoff)
  │     ├── Create pull request
  │     └── Record PR in memory.db
  └── 10. Post-PR: CLA auto-signing, Telegram notification
```

### 3.3 Super Human Loop (`orchestrator/human.py`)

The `superhuman` command runs an **infinite stochastic daily routine**:

```
run_daily_routine():
  │
  ├── Startup:
  │     ├── Sync PR counter from DB (survive restarts)
  │     ├── Init pipeline components (GitHub, LLM, Memory)
  │     ├── Start Telegram long-polling (background task)
  │     ├── Sync Familiar Grounds (historical merged PRs)
  │     └── Sync VIP repos (>1000 stars, 24h throttle)
  │
  └── Main Loop (infinite):
        ├── New day check → randomize daily PR target (min_daily_prs..max_daily_prs, capped at 12)
        ├── Mandatory lunch break (12:00-13:01 UTC)
        │
        ├── If quota met → Patrol-only mode (long delays: 1-3 hours)
        │
        ├── If quota not met:
        │     ├── Check for pending notifications → prioritize Patrol
        │     ├── Random roll: 60% Hunt / 40% Patrol
        │     ├── Hunt:
        │     │     ├── DB-level quota guard (re-check before starting)
        │     │     ├── Targeted mode (--target-repo) or Wild discovery
        │     │     ├── Post-PR cooldown: 15-45 min random sleep
        │     │     └── Log to daily_log/daily_log_YYYY-MM-DD.md
        │     └── Patrol:
        │           ├── Fetch open + pending PRs
        │           ├── PRPatrol.patrol() with persistent clients
        │           └── Notify merged PRs via Telegram
        │
        ├── Human-like delay between iterations:
        │     ├── After hunt: 30-90 min
        │     ├── After hunt (0 repos): 2-5 min quick retry
        │     ├── After patrol: 10-30 min
        │     └── After error: 15 min stress break
        │
        └── 24-hour cron: re-sync Familiar Grounds + VIP repos
```

### 3.4 PR Patrol Flow (`pr/patrol.py`)

```
patrol(pr_records, dry_run, pr_filter):
  │
  ├── For each open PR:
  │     ├── Check live GitHub status (open/merged/closed)
  │     ├── Sync status to DB
  │     ├── Skip if merged/closed (update DB + continue)
  │     ├── Fetch unread review comments
  │     ├── Classify each comment via LLM:
  │     │     ├── CODE_CHANGE → generate fix, push to branch
  │     │     ├── QUESTION → generate answer, post reply
  │     │     ├── STYLE_FIX → generate style fix, push
  │     │     ├── CLA → re-sign CLA
  │     │     ├── APPROVE → no action (celebrate)
  │     │     └── SPAM/NOISE → ignore
  │     ├── Auto-heal CI failures (if enabled):
  │     │     ├── Fetch failing check runs
  │     │     ├── LLM generates fix based on CI logs
  │     │     ├── Push fix to PR branch
  │     │     └── Cap: max 3 CI fix attempts per PR (RETURNING clause)
  │     └── Comment ingestion: capped at 15 most recent (P1 OPSEC)
  │
  └── Return PatrolResult (checked, skipped, fixes, replies, errors)
```

### 3.5 PR Janitor Flow (`pr/janitor.py`)

```
sweep_and_destroy():
  │
  ├── Fetch all open PRs by authenticated user (GitHub search API)
  ├── For each PR:
  │     ├── Ask LLM: "Is this PR HIGH-VALUE or GARBAGE?"
  │     ├── GARBAGE → close PR + delete branch + log
  │     ├── HIGH-VALUE → spare + log
  │     └── 2.0s delay between evaluations (P1 OPSEC throttle)
  └── Return summary {total_scanned, garbage_closed, critical_spared}
```

---

## 4. Database Schema (`orchestrator/memory.py`)

SQLite database with **WAL mode** + `foreign_keys=ON`. 8 tables:

### 4.1 Tables

| Table               | Purpose                                        | Key Columns                                    |
|---------------------|------------------------------------------------|------------------------------------------------|
| `analyzed_repos`    | Track which repos have been analyzed           | `full_name` (PK), `analyzed_at`, `findings`    |
| `submitted_prs`     | All PRs + issue proposals                      | `repo`, `pr_number` (UNIQUE), `status`, `type` |
| `findings_cache`    | Cached analysis findings                       | `id` (PK), `repo`, `type`, `severity`, `status`|
| `run_log`           | Pipeline run history                           | `started_at`, `repos_analyzed`, `prs_created`  |
| `pr_outcomes`       | PR merge/close outcomes + feedback             | `repo`, `pr_number` (UNIQUE), `outcome`        |
| `repo_preferences`  | Learned per-repo preferences                   | `repo` (PK), `preferred_types`, `merge_rate`   |
| `blacklisted_repos` | Permanently banned repos                       | `repo` (PK), `reason`, `blacklisted_at`        |
| `api_usage_log`     | LLM API call tracking (sliding window)         | `timestamp` (REAL), `provider`                 |
| `task_schedule`     | Cron-like task throttling                      | `task_key` (PK), `next_run`                    |

### 4.2 Critical Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_api_usage ON api_usage_log(provider, timestamp);
```

### 4.3 Auto-Migrations

On `Memory.init()`, the system runs `ALTER TABLE` migrations for:
- `ci_fix_attempts INTEGER DEFAULT 0` on `submitted_prs`
- `discussion_replies INTEGER DEFAULT 0` on `submitted_prs`

Migration failures for "column already exists" are silently suppressed.

### 4.4 Record Cleanup (TTL)

On startup, `cleanup_old_records(days=30)` purges:
- `api_usage_log` entries older than 30 days
- `task_schedule` entries older than 7 days

---

## 5. LLM Integration (`llm/provider.py`)

### 5.1 Provider Architecture

```python
class LLMProvider(ABC):           # Abstract base
    complete(prompt, system, temperature, max_tokens) -> str
    chat(messages, system, temperature, max_tokens) -> str
    complete_with_tools(messages, tools, ...) -> LLMToolResponse  # function-calling

class MinimaxProvider(LLMProvider):  # Primary provider
    # Minimax Chat Completion v2 endpoint
    # Semaphore-throttled (global cap: 4 concurrent LLM calls)
    # 2.0s "human think gap" between calls
    # 3-retry loop with 10s/20s backoff on timeouts
    # Reasoning artifact stripping (<think>...</think>)
```

### 5.2 Quota System (Minimax Overdrive)

Sliding-window quota enforcement in `Memory.check_and_record_llm_quota()`:

| Window      | Hard Limit | Safety Threshold (95%) |
|-------------|------------|----------------------|
| 5-hour      | 1000       | 950                  |
| 7-day       | 10000      | 9500                 |

- Protected by `asyncio.Lock` (`_quota_lock`) for atomicity
- Hourly cleanup of entries older than 7 days
- Raises `LLMRateLimitError` on threshold breach

### 5.3 Tool/Function Calling

The base `LLMProvider.complete_with_tools()` supports:
- Native function calling (for providers that support it)
- Fallback: inline JSON parsing for `\`\`\`tool_call\`\`\`` blocks and `TOOL_CALL: {...}` patterns

---

## 6. GitHub API Client (`github/client.py`)

### 6.1 Rate Limiting & OPSEC

| Guard                    | Mechanism                                             |
|--------------------------|-------------------------------------------------------|
| **Global semaphore**     | `asyncio.Semaphore(1)` — max 1 concurrent API call    |
| **Proactive throttling** | Pre-request sleep: 3.0s (search), 2.0s (mutation), 1.5s (read) |
| **Retry backoff**        | `2.0 * (attempt + 1)` seconds on failure (P1 OPSEC)   |
| **403 handling**         | Exponential backoff (60s, 120s) for secondary rate limits |
| **Post-mutation delay**  | 2.0s sleep after `delete_branch`                      |
| **Reaction guard**       | `add_comment_reaction()` wrapped in semaphore          |

### 6.2 Key Methods

- `search_repositories()` — GitHub search API with star/language filters
- `get_repo_details()` → `Repository` model
- `get_file_content()` — raw file content
- `create_or_update_file()` — commit changes to a branch
- `create_pull_request()` — create PR
- `create_fork()` — fork a repo
- `delete_branch()` — cleanup with 2.0s post-delay
- `get_pr_review_comments()` — fetch review feedback
- `add_comment_reaction()` — react to comments (semaphore-guarded)
- `fetch_user_merged_prs()` — bulk fetch for Familiar Grounds sync
- `discover_vip_friendly_repos()` — find >1000-star repos with merged PRs

---

## 7. Analysis Engine (`analysis/`)

### 7.1 Progressive Skills System (`analysis/skills.py`)

17 skills loaded **on-demand** based on language + framework detection:

| Priority | Skill                | Languages              | Frameworks         |
|----------|----------------------|------------------------|---------------------|
| 1        | `security`           | (universal)            |                     |
| 2        | `code_quality`       | (universal)            |                     |
| 3        | `python_specific`    | Python                 |                     |
| 3        | `javascript_specific`| JS, TS                 |                     |
| 3        | `go_specific`        | Go                     |                     |
| 3        | `rust_specific`      | Rust                   |                     |
| 3        | `java_specific`      | Java, Kotlin           |                     |
| 4        | `django_security`    | Python                 | Django              |
| 4        | `flask_security`     | Python                 | Flask               |
| 4        | `fastapi_patterns`   | Python                 | FastAPI             |
| 4        | `react_patterns`     | JS, TS                 | React, Next         |
| 4        | `express_security`   | JS, TS                 | Express             |
| 5        | `performance`        | (universal)            |                     |
| 6        | `docs`               | (universal)            |                     |
| 7        | `ui_ux`              | JS, TS                 | React, Vue, Svelte  |
| 8        | `refactor`           | (universal)            |                     |

**Max 5 skills per analysis run**, sorted by priority.

### 7.2 Framework Detection

Auto-detected from file paths and content:
`django`, `flask`, `fastapi`, `express`, `react`, `next`, `vue`, `svelte`, `angular`, `spring`, `rails`

### 7.3 RAG Engine (`core/rag.py`)

- **ChromaDB EphemeralClient** (RAM-only, no disk persistence)
- Sliding-window text chunking: 1200 chars/chunk, 200 char overlap
- Pseudo-embeddings: 128-dim word-frequency vectors (deterministic, local)
- Auto-destroys collection after use to free RAM
- File exclusions: `node_modules`, `.git`, minified files, binaries, lock files
- Max file size for indexing: 200KB

---

## 8. Code Generation Engine (`generator/engine.py`)

### 8.1 Generation Flow

```
ContributionGenerator.generate(finding, context):
  ├── Build RAG index (ephemeral ChromaDB)
  ├── Construct LLM prompt with:
  │     ├── Project Map (structural skeleton)
  │     ├── Finding details (type, severity, file, suggestion)
  │     ├── RAG-retrieved cross-file context
  │     └── Tool definition (read_file for X-Ray Vision)
  ├── LLM generates code with function-calling loop:
  │     ├── Tool call: read_file(filepath) → fetch full file content
  │     ├── Re-feed content back to LLM
  │     └── Loop until text response (max iterations)
  ├── Parse diff/patch from LLM output
  ├── Quality score via ContributionScorer
  └── Return Contribution with list of Changes
```

### 8.2 X-Ray Vision (Tool-Calling Loop)

The generator uses an iterative tool-calling pattern:
1. LLM sees the Project Map (file signatures)
2. LLM requests `read_file` for files it needs
3. Tool fetches file content via GitHub API
4. Content is fed back to LLM
5. LLM produces final code changes

**Guards:**
- Binary/lock/minified files blocked by extension
- 404 returns a clear error message
- File content capped at 100KB

---

## 9. Sandbox Validation (`core/sandbox.py`)

### 9.1 Polyglot Docker Sandbox

Supports 11 languages with Docker images:

| Language   | Image                                    |
|------------|------------------------------------------|
| Python     | `python:3.11-alpine`                     |
| JavaScript | `node:20-alpine`                         |
| TypeScript | `node:20-alpine`                         |
| Rust       | `rust:1.75-alpine`                       |
| Go         | `golang:1.21-alpine`                     |
| Java       | `eclipse-temurin:21-jdk-alpine`          |
| Ruby       | `ruby:3.3-alpine`                        |
| PHP        | `php:8.2-cli-alpine`                     |
| C          | `gcc:14-bookworm`                        |
| C++        | `gcc:14-bookworm`                        |
| C#         | `mcr.microsoft.com/dotnet/sdk:8.0-alpine`|

### 9.2 Execution Flow

```
DockerSandbox.validate(patch, language):
  ├── Detect language from file extensions
  ├── Pull Docker image (if not cached)
  ├── Create container with:
  │     ├── Network disabled (security isolation)
  │     ├── Read-only root filesystem
  │     ├── Memory limit (512MB)
  │     └── Hard timeout: stop_timeout + API wait timeout (P0 fix)
  ├── Copy repo code + apply patch
  ├── Run test command (language-specific)
  └── Return: pass/fail/inconclusive
```

**P0 Deadlock Fix:** Hard `stop_timeout` on `containers.run()` + API `wait()` timeout guard.

---

## 10. Middleware Chain (`core/middleware.py`)

5 ordered middlewares, executed sequentially via `MiddlewareChain`:

| Order | Middleware              | Purpose                                      |
|-------|-------------------------|----------------------------------------------|
| 1     | `RateLimitMiddleware`   | Check daily PR limit before processing       |
| 2     | `ValidationMiddleware`  | Validate repo suitability                    |
| 3     | `RetryMiddleware`       | Wrap downstream with retry (2 retries, 5s+exp backoff) |
| 4     | `DCOMiddleware`         | Auto-compute DCO signoff from authenticated user |
| 5     | `QualityGateMiddleware` | Check contribution quality score (min 5.0)   |

Pattern: Each middleware calls `next_mw(ctx)` to pass control. Short-circuits by returning `ctx` directly if conditions fail.

---

## 11. Sub-Agent Architecture (`agents/registry.py`)

5 agents with parallel execution support (max 3 concurrent):

| Agent              | Role              | Wraps                     |
|--------------------|-------------------|---------------------------|
| `AnalyzerAgent`    | `analyzer`        | `CodeAnalyzer`            |
| `GeneratorAgent`   | `generator`       | `ContributionGenerator`   |
| `PatrolAgent`      | `patrol`          | `PRPatrol`                |
| `ComplianceAgent`  | `compliance`      | CLA/DCO/CI handling       |
| `IssueSolverAgent` | `issue_solver`    | `IssueSolver`             |

**Note:** These are lightweight stubs wrapping existing components via `AgentContext.data` dict injection. Parallel execution uses `asyncio.Semaphore`.

---

## 12. Tool Protocol (`tools/protocol.py`)

MCP-inspired tool interface with 2 built-in tools:

| Tool         | Class         | Actions                                        |
|--------------|---------------|------------------------------------------------|
| `github`     | `GitHubTool`  | `get_file`, `read_file`, `create_pr`, `get_user` |
| `llm`        | `LLMTool`     | `complete` (prompt → response)                 |

### `read_file` Tool Schema (for LLM function calling):

```json
{
  "name": "read_file",
  "parameters": {
    "type": "object",
    "properties": {
      "filepath": {"type": "string"}
    },
    "required": ["filepath"]
  }
}
```

**Guards:** BLOCKED_EXTENSIONS (binary/lock/minified), MAX_FILE_SIZE (100KB), 404 handling.

---

## 13. Issue Solver (`issues/solver.py`)

### 13.1 Classification

6 categories with label-based + keyword-based classification:

| Category        | Labels                                 | Contribution Type     |
|-----------------|----------------------------------------|-----------------------|
| `BUG`           | bug, fix, defect                       | `CODE_QUALITY`        |
| `FEATURE`       | feature, enhancement                   | `FEATURE_ADD`         |
| `DOCS`          | documentation, docs                    | `README_FIX`          |
| `SECURITY`      | security, vulnerability                | `SECURITY_FIX`        |
| `PERFORMANCE`   | performance                            | `PERFORMANCE_OPT`     |
| `UI_UX`         | ui, ux, accessibility                  | `UI_UX_FIX`           |
| `GOOD_FIRST_ISSUE` | good first issue, help wanted       | `CODE_QUALITY`        |

### 13.2 Complexity Estimation

Score 1-5 based on:
- Good-first-issue labels → score 1
- Body length (>2000 chars → +1, >5000 → +1)
- File reference count (>3 → +1)

Default `max_complexity=3`.

### 13.3 Deep Multi-File Solving

`solve_issue_deep()` uses:
1. Issue body + up to 5 comments
2. RepoMapper skeleton generation
3. Up to 10 relevant file contents
4. LLM returns `---FILE---` / `---END---` blocks (max 5 files)
5. Fallback: single-file `solve_issue()` if deep solve fails

---

## 14. Notification System (`core/notifier.py`)

### 14.1 Telegram Bot Commands

| Command     | Action                                        |
|-------------|-----------------------------------------------|
| `/start`    | Welcome message                               |
| `/help`     | Show help menu                                |
| `/status`   | Bot heartbeat check                           |
| `/rptoday`  | Today's PR count + URLs                       |
| `/quota`    | Minimax API budget (5h + 7d usage)            |
| `/update`   | Trigger Alumni Sync (historical merged PRs)   |
| `/clean`    | Trigger PR Janitor sweep                      |
| `/accept`   | Hall of Fame (merged PRs list)                |

### 14.2 Polling Architecture

- **Long-polling** with 30s timeout on `getUpdates`
- Exponential backoff on errors (5s → 60s cap)
- Chat ID validation (ignores unauthorized chats)
- Failed alerts persisted to `failed_alerts.log`

---

## 15. Anti-Farming Protections

### 15.1 Contribution Type Bans (Hard-Block)

```python
# ABSOLUTELY FORBIDDEN contribution types
BANNED_TYPES = {ContributionType.README_FIX, ContributionType.DOCS_IMPROVE}
```

Any finding with these types is **immediately dropped** before generation.

### 15.2 File-Level Protections

- **SKIP_EXTENSIONS**: `.md`, `.txt`, `.rst`, `.yml`, `.yaml`, `.toml`, `.cfg`, `.ini`, `.json`
- **PROTECTED_META_FILES**: 50+ governance/config files (LICENSE, CONTRIBUTING.md, tsconfig.json, package.json, etc.)
- Contributions touching ONLY skipped-extension files are rejected

### 15.3 Duplicate PR Detection

`_titles_similar()` uses keyword overlap (>50% match) to detect duplicates against historical PR titles in `submitted_prs`.

### 15.4 Quality Gate

Middleware enforces minimum quality score (default 5.0). Below-threshold contributions are blocked.

---

## 16. OPSEC & Stealth Hardening

### 16.1 API Pacing (Human Mimicry)

| Context                  | Delay            |
|--------------------------|------------------|
| GitHub search API call   | 3.0s             |
| GitHub mutation (POST)   | 2.0s             |
| GitHub read (GET)        | 1.5s             |
| After branch deletion    | 2.0s             |
| Between LLM calls        | 2.0s (think gap) |
| Between janitor PRs      | 2.0s             |
| After PR creation        | 15-45 min        |
| Hunt between rounds      | 30-90 min        |
| Patrol between cycles    | 10-30 min        |
| Patrol-only mode         | 1-3 hours        |
| Mandatory lunch break    | 12:00-13:01 UTC  |

### 16.2 Security Hardening

- **Prompt Injection Defense:** Commit messages in patrol.py use only structural PR identifiers (repo, PR#), never raw maintainer feedback
- **CI Name Sanitization:** `_sanitize_check_name()` strips emojis, AI-identity keywords, and injection patterns
- **LLM Comment Cap:** Patrol ingests max 15 most recent comments (prevents LLM quota burn)

### 16.3 Stealth Identity

- Zero attribution in PR bodies (`_farm_agent_attribution()` returns empty string)
- PR body tone: "tired senior developer" — no AI fluff, 2-4 sentences max
- Vietnamese human persona in logs (internal only, never exposed to GitHub)

---

## 17. Configuration System (`core/config.py`)

### 17.1 Config Hierarchy

```yaml
# config.yaml
github:
  token: "ghp_..."
  max_prs_per_day: 10
  max_repos_per_run: 5
  min_daily_prs: 4
  max_daily_prs: 10
  rate_limit_buffer: 500

llm:
  provider: "minimax"
  model: "abab7-chat-preview"
  api_key: "..."
  temperature: 0.1
  max_tokens: 8192
  minimax_group_id: "..."

discovery:
  languages: ["python", "javascript", "typescript"]
  stars_range: [100, 10000]
  min_last_activity_days: 7
  topics: []
  require_contributing_guide: false

analysis:
  enabled_analyzers: ["security", "code_quality"]
  severity_threshold: "medium"

contribution:
  enabled_types: [...]

pipeline:
  max_concurrent_repos: 3
  min_quality_score: 5.0

notifications:
  telegram_token: "..."
  telegram_chat_id: "..."

storage:
  db_path: "~/.farm_agent/memory.db"
```

### 17.2 Named Profiles (`core/profiles.py`)

4 built-in profiles: `security-focused`, `docs-focused`, `full-scan`, `gentle`

---

## 18. Retry & Caching (`core/retry.py`)

### 18.1 Retry Decorators

| Decorator           | Retries | Base Delay | Max Delay | Target Exceptions         |
|---------------------|---------|------------|-----------|---------------------------|
| `async_retry()`     | 3       | 1.0s       | 60s       | Configurable              |
| `github_retry()`    | 3       | 2.0s       | 60s       | GitHubAPIError, RateLimitError |
| `llm_retry()`       | 3       | 3.0s       | 60s       | LLMError, LLMRateLimitError |
| `rate_limit_retry()` | 5      | 10.0s      | 120s      | LLMRateLimitError         |

All use exponential backoff with ±25% jitter.

### 18.2 LRU Cache

Two global caches:
- `llm_cache`: max 200 entries
- `github_cache`: max 500 entries

Key generation via SHA-256 hash of args. Thread-safe via `OrderedDict`.

---

## 19. Leaderboard & Outcome Learning

### 19.1 Leaderboard (`core/leaderboard.py`)

Reads from `submitted_prs` table to compute:
- Per-repo merge rate
- Per-type merge rate
- Rankings by merged PR count

### 19.2 Outcome Learning (`orchestrator/memory.py`)

`record_outcome()` tracks:
- PR merge/close/reject outcomes
- Maintainer feedback text
- Time-to-close in hours

`get_repo_preferences()` returns learned preferences:
- Preferred contribution types
- Rejected contribution types
- Average merge rate
- Average review hours

### 19.3 Repo Blacklisting

Repos that explicitly reject Farm-Agent's PRs or ban AI contributions:
- Stored in `blacklisted_repos` table
- Filtered out during discovery (before analysis)

---

## 20. P0/P1/P2 Hardening Summary

### P0 Fixes (Critical Fatalities)

| Fix                      | File                    | What Changed                                          |
|--------------------------|-------------------------|-------------------------------------------------------|
| Sandbox Deadlock         | `core/sandbox.py`       | Added `stop_timeout` + API `wait()` timeout guard     |
| Timezone Quota Bypass    | `orchestrator/memory.py`| Python-generated UTC dates instead of SQLite `date()` |
| Prompt Injection         | `pr/patrol.py`          | Sanitized commit messages, stripped maintainer feedback|
| CI Name Identity Leak    | `pr/patrol.py`          | `_sanitize_check_name()` strips AI keywords/emojis    |

### P1 Fixes (OPSEC)

| Fix                      | File                    | What Changed                                          |
|--------------------------|-------------------------|-------------------------------------------------------|
| Semaphore on Reactions   | `github/client.py`      | `add_comment_reaction()` wrapped in `self._sem`       |
| Retry Backoff            | `github/client.py`      | `asyncio.sleep(2.0 * (attempt + 1))` on retry         |
| Branch Delete Delay      | `github/client.py`      | 2.0s post-mutation sleep                              |
| LLM Ingestion Cap        | `pr/patrol.py`          | Capped comment ingestion to 15 most recent            |
| Janitor Throttle         | `pr/janitor.py`         | 2.0s delay between PR evaluations                     |

### P2 Fixes (Architecture)

| Fix                      | File                    | What Changed                                          |
|--------------------------|-------------------------|-------------------------------------------------------|
| TOCTOU Database Race     | `orchestrator/memory.py`| `RETURNING` clause for atomic increment+read          |
| Concurrent Quota Bypass  | `orchestrator/pipeline.py`| Atomic quota check inside `_human_typing_lock`       |

---

## 21. File Organization

```
farm_agent/
├── __init__.py                    # Version (__version__)
├── agents/
│   └── registry.py                # Sub-agent registry (5 agents)
├── analysis/
│   ├── analyzer.py                # CodeAnalyzer (7 analyzer types)
│   ├── mapper.py                  # RepoMapper (skeleton generation)
│   └── skills.py                  # 17 progressive analysis skills
├── cli/
│   └── main.py                    # Click CLI (11 commands)
├── core/
│   ├── config.py                  # FarmAgentConfig (Pydantic)
│   ├── daily_log.py               # DailyMarkdownLogger
│   ├── exceptions.py              # Exception hierarchy
│   ├── leaderboard.py             # PR merge/close tracking
│   ├── logger.py                  # Daily rotating file logger
│   ├── middleware.py               # 5 middleware chain
│   ├── models.py                  # Data models (Repository, Finding, etc.)
│   ├── notifier.py                # TelegramNotifier
│   ├── profiles.py                # Named contribution profiles
│   ├── quotas.py                  # In-memory usage tracker
│   ├── rag.py                     # ChromaDB ephemeral RAG
│   ├── retry.py                   # async_retry + LRU cache
│   └── sandbox.py                 # DockerSandbox (11 languages)
├── generator/
│   ├── engine.py                  # ContributionGenerator
│   └── scorer.py                  # Quality scoring
├── github/
│   ├── client.py                  # GitHubClient (semaphore=1)
│   ├── discovery.py               # RepoDiscovery
│   └── guidelines.py              # CONTRIBUTING.md parser
├── issues/
│   └── solver.py                  # IssueSolver (single + deep multi-file)
├── llm/
│   └── provider.py                # LLMProvider + MinimaxProvider
├── notifications/                 # (additional notification backends)
├── orchestrator/
│   ├── human.py                   # SuperHumanLoop (24/7 stochastic loop)
│   ├── memory.py                  # Memory (SQLite, 8 tables)
│   └── pipeline.py                # ContribPipeline (main orchestrator)
├── plugins/                       # (plugin directory)
├── pr/
│   ├── janitor.py                 # PRJanitor (garbage PR destroyer)
│   ├── manager.py                 # PRManager (fork→PR lifecycle)
│   └── patrol.py                  # PRPatrol (review monitor)
├── templates/                     # (PR/commit templates)
└── tools/
    └── protocol.py                # Tool protocol + GitHubTool + LLMTool
```

---

## 22. Known Edge Cases & Gotchas

1. **Memory counter vs DB counter:** SuperHumanLoop tracks `_prs_created_today` in RAM but also
   reads from DB on startup via `get_today_pr_count()`. After restart, DB is authoritative.

2. **Familiar Grounds race:** `process_one_repo()` releases the semaphore before doing the
   API call (the `async with semaphore` only guards the 5s sleep). This is intentional but
   means the actual API calls run concurrently without bound.

3. **WAL mode assumption:** TOCTOU fixes assume SQLite WAL serializes writes. The `RETURNING`
   clause eliminates the separate SELECT, but concurrent readers can still see stale data
   between the WAL checkpoint.

4. **ChromaDB optional:** If `chromadb` is not installed, RAG falls back silently and returns
   empty results. The generator still works but without cross-file context.

5. **Docker optional:** If Docker daemon is unavailable, sandbox validation is skipped entirely.
   Patches go straight to PR without test validation.

6. **Issue proposals reuse `submitted_prs`:** The `record_issue_proposal()` method stores
   issues in the same table as PRs, with `type='issue_proposal'` and the `fork` column
   repurposed as `finding_title`. This is a schema hack.

7. **Minimax-specific code paths:** Several places check `config.llm.provider == "minimax"`
   to cap concurrency or adjust behavior. No other providers are currently registered.

8. **Signal handling (Windows):** `add_signal_handler` in superhuman mode doesn't work on
   Windows (asyncio limitation). Ctrl+C handling falls back to `KeyboardInterrupt`.

9. **Daily log timezone:** `DailyMarkdownLogger._write()` uses `datetime.now()` (local time)
   for log timestamps, NOT UTC. This is intentional for human readability but inconsistent
   with the rest of the codebase which uses UTC.

10. **Profile stale reference:** The `docs-focused` and `gentle` profiles still reference
    `docs_improve` contribution type, which is now hard-banned in the pipeline. These profiles
    would produce zero PRs if used.

---

*End of Project Map. This document is the authoritative reference for Farm-Agent's architecture.*
