# PROJECT_MAP.md — Agent-Farm Definitive Architecture Map

> **Ground-truth-only document**. Every entry traced from source code.
> Last verified: 2026-04-15

---

## 1. System Overview & Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ (asyncio) |
| LLM Providers | Minimax (ABAB-6.5S, M2.7) — primary; OpenRouter (Red Team mode) |
| Database | SQLite 3 (`data/memory.db`) via `aiosqlite` |
| Vector DB | ChromaDB (ephemeral/RAM-only, no disk persistence) |
| GitHub API | REST + GraphQL via `httpx` (multi-token rotation pool) |
| Container | Docker (`Dockerfile` / `docker-compose.yml`); DockerSandbox for code validation |
| CLI | `click` + `rich` (TUI dashboard available) |
| Deployment | Docker entrypoint (`entrypoint.sh`) → `farm_agent superhuman` (terminator loop) |

**System Purpose**: Autonomous security-focused bug bounty agent. Discovers open-source repositories, analyzes them for vulnerabilities, generates fixes, and submits pull requests through a multi-stage guarded pipeline.

---

## 2. Core Architecture & Data Flow

### 2.1 Pipeline Entry Points

| Entry Point | Source | Description |
|-------------|--------|-------------|
| `farm_agent run` | `cli/main.py` | Auto-discover repos and contribute |
| `farm_agent target <url>` | `cli/main.py` | Target a specific repo |
| `farm_agent analyze <url>` | `cli/main.py` | Analyze without contributing |
| `farm_agent solve <url>` | `cli/main.py` | Solve open issues in a repo |
| `farm_agent superhuman` | `cli/main.py` → `orchestrator/human.py` | **Terminator Mode**: relentless continuous loop (`SuperHumanLoop`) |
| `farm_agent hunt` | `cli/main.py` | Aggressive single-repo discovery |

### 2.2 Primary Execution Loop — `ContribPipeline.run_circular()`

```
target_repo.json ──seed──► SQLite target_repos table
                                    │
                                    ▼
                           ┌─────────────────┐
                           │  Atomic SELECT   │
                           │  WHERE status=   │
                           │  PENDING         │
                           │  UPDATE...RETURN │
                           │  ING (crash-safe)│
                           └────────┬────────┘
                                    │
                                    ▼
              ┌──────────────────────────────────────────┐
              │         Anti-Farming Filters              │
              │  Gate 1: Impact ≥ MEDIUM only            │
              │  Gate 2: README_FIX / DOCS banned         │
              │  Gate 3: .md/.txt/.rst/docs/ blocked      │
              │  Gate 4: 60+ farming keywords blocked     │
              │  Protected meta files (40+) blocked       │
              └──────────────────┬───────────────────────┘
                                 │ SURVIVING findings
                                 ▼
              ┌──────────────────────────────────────────┐
               │       Radar (BloodhoundAnalyzer)          │
               │  Semgrep-powered security radar + LLM White-Hat scan   │
               │  Maintainer Vibe Check (hostility filter)  │
              └──────────────────┬───────────────────────┘
                                 │ validated findings
                                 ▼
              ┌──────────────────────────────────────────┐
              │       Security Gate (Diplomat Protocol)    │
              │  Task 1: SECURITY.md / README.md scan for  │
              │          26 private-disclosure phrases      │
              │          → ABORT + secret_findings/ JSON   │
              │          → Telegram notification            │
              │  Task 2: CONTRIBUTING.md → RepoStyleGuide  │
              │          (cached in repo_style_guides table)│
              │  Task 3: LLM fills PR template checkboxes  │
              │  Protected Meta Files list enforced         │
              └──────────────────┬───────────────────────┘
                                 │ PASSED
                                 ▼
              ┌──────────────────────────────────────────┐
              │       DEV (ContributionGenerator)         │
              │  RAG context (ChromaDB ephemeral index)   │
              │  RepoMapper skeleton for codebase map      │
              │  Progressive Skills loaded per language    │
              │  Gag Order applied to ALL output           │
              │  7-tier Diff Minimizer for patch matching  │
              └──────────────────┬───────────────────────┘
                                 │ generated contribution
                                 ▼
              ┌──────────────────────────────────────────┐
              │       QA (QAHardcoreScorer)               │
              │  MIN_APPROVAL_SCORE = 9.0/10              │
              │  Weights: Path 20%, Logic 25%, Arch 20%,   │
              │           Idioms 15%, Security 10%,         │
              │           Scope 10%                         │
              │  CI/CD exception: infra fixes → 9.0+       │
              │  Test/docs paths: MAX 4.0                    │
              │  FAIL → QA lesson → knowledge_base table    │
              └──────────────────┬───────────────────────┘
                                 │ SCORE ≥ 9.0
                                 ▼
              ┌──────────────────────────────────────────┐
              │       Sandbox (DockerSandbox)             │
              │  Polyglot Guillotine: 11 languages         │
              │  Hard 60s timeout per validation            │
              └──────────────────┬───────────────────────┘
                                 │ PASSED
                                 ▼
              ┌──────────────────────────────────────────┐
              │       Delivery (PRManager / IssueManager)  │
              │  Route A (SECURITY_FIX, CRITICAL, HIGH):   │
              │          → Direct PR                       │
              │  Route B (all other types):                │
              │          → GitHub Issue (Issue-First)       │
              │  Git clone + local commit + push            │
              │  DCO signoff enforced                      │
              │  Gag Order sanitized title/body             │
              │  PRPatrol monitors post-submission          │
              └──────────────────────────────────────────┘
```

### 2.3 DEV-QA Retry Loop

Within `run_circular()`, if QA rejects a contribution:
- MAX_DEV_QA_CYCLES = 3 retry cycles
- Each failure injects QA critique context into next DEV cycle
- After 3 failures → status `COMPLETED_TOO_COMPLEX`

### 2.4 Terminator Mode — `SuperHumanLoop`

(`orchestrator/human.py`): Infinite loop pulling targets from SQLite. Runs `hunt_circular()` then `patrol()` with minimal sleep intervals. Has quota-aware cooldowns (LLM_QUOTA_COOLDOWN = 300s normal, 3s in time-warp). Time-warp mode (`--time-warp`) runs 10 fast iterations for testing.

### 2.5 PRPatrol — Post-Submission Monitoring

(`pr/patrol.py`): Monitors open PRs for:
- Review feedback → auto-fix with CI healing (up to `ci_fix_attempts` retries)
- Hostile maintainer detection → blacklists repo
- Discussion reply limits (prevents spam)
- Randomized `mean_delay` (2-10 min, exponential distribution, capped at 2h)

### 2.6 Sub-Agent Architecture

(`agents/registry.py`): DeerFlow-inspired registry with 5 registered agents:
- `AnalyzerAgent` — wraps `CodeAnalyzer`
- `GeneratorAgent` — wraps `ContributionGenerator`
- `PatrolAgent` — wraps `PRPatrol`
- `ComplianceAgent` — handles CLA/DCO/CI
- `IssueSolverAgent` — wraps `IssueSolver`
- Max concurrent: 3 per `AgentRegistry`

### 2.7 Issue Solver

(`issues/solver.py`): Reads open GitHub Issues, classifies (`bug`, `feature`, `docs`, `security`, `performance`, `ui_ux`, `good_first_issue`, `unsolvable`), and generates targeted contributions. Uses `RepoMapper` for multi-file understanding.

---

## 3. Critical Guardrails & Protocols

### 3.1 Diplomat Protocol (`github/security_gate.py` + `github/guidelines.py`)

**Task 1 — Private Disclosure Detection**:
- Scans SECURITY.md and README.md for 26 private-disclosure phrases (e.g., "do not open a public pr", "hackerone", "bugcrowd", "responsible disclosure", "vulnerability disclosure program")
- If triggered: pipeline **ABORTS**, findings saved to `secret_findings/` as JSON, Telegram notification sent
- Status set to `COMPLIANCE_SKIP_PRIVATE_DISCLOSURE`

**Task 2 — Style Guide Extraction**:
- LLM summarizes CONTRIBUTING.md → `RepoStyleGuide` (cached in `repo_style_guides` SQLite table)
- Injected into Generator and QA prompts

**Task 3 — PR Template Compliance**:
- LLM fills PR templates with checkbox compliance enforcement
- `adapt_pr_title()` and `adapt_pr_body()` ensure format adherence

**Protected Meta Files** (`PROTECTED_META_FILES`): 40+ files blocked from modification, including CONTRIBUTING.md, SECURITY.md, LICENSE, tsconfig.json, .eslintrc*, webpack.config.*, Dockerfile, docker-compose.yml, Makefile, .github/workflows/*, etc.

### 3.2 Gag Order (Stealth Mode) — `generator/engine.py`

**Security Vocabulary Suppression** (`_SECURITY_FORBIDDEN_RE`):
- Regex: `(?i)\b(security|vulnerability|vulnerabilities|attack|exploit|malicious|threat|cve|injection|path traversal|remote code execution|zero.day|zero-day)\b`
- Applied to: titles, bodies, commit messages, generated code

**Security Vocabulary Rewrites** (`_SECURITY_REWRITE`, 12 rules):
- "vulnerability" → "robustness gap"
- "security fix" → "reliability improvement"
- "security patch" → "robustness patch"
- "security issue" → "reliability issue"
- "security concern" → "reliability concern"
- "security flaw" → "robustness flaw"
- "security bug" → "reliability bug"
- "exploit" → "edge case"
- "attack vector" → "unexpected input path"
- "injection" → "input sanitization improvement"
- "path traversal" → "path resolution improvement"
- "remote code execution" → "code execution safety"

**AI Self-Identification Blocking** (`_GHOST_DISCLOSURE_RE`):
- Patterns: "as an ai", "ai generated", "language model", "openai", "minimax", "farm_agent", "automated", "bot", etc.
- Raises `GenerationError` if detected in titles, bodies, commit messages, or generated code

**XSS Sanitization** (`escape_html_xss()`):
- Strips `<script>` tags, `on*=` event handlers, `javascript:` URIs

**Applied in**: `PRManager.create_pr()` via `_sanitize_text()`, `_parse_changes()`, `PRPatrol` reply posting

### 3.3 QA Hardcore Scorer — `generator/scorer.py`

- **MIN_APPROVAL_SCORE = 9.0** out of 10.0
- Weighted grading: Path Relevance 20%, Logic 25%, Architecture 20%, Idioms 15%, Security 10%, Scope 10%
- **Path relevance penalty**: test/example/demo/docs paths → MAX 4.0
- **CI/CD exception**: security vulns in `.github/workflows`, Dockerfiles, deployment configs → 9.0+ if fix correctly sanitizes inputs
- **Failure handling**: critiques recorded as QA lessons in `knowledge_base` table, failure context injected into next DEV cycle

### 3.4 Anti-Farming Filters — `orchestrator/pipeline.py`

| Gate | Rule | Exception |
|------|------|-----------|
| Gate 1 — Impact Level | Only CRITICAL, HIGH, MEDIUM survive. LOW and TRIVIAL dropped. | None |
| Gate 2 — Docs Ban | `README_FIX` and `DOCS_IMPROVE` types BANNED always | None |
| Gate 3 — File Guillotine | `.md`, `.txt`, `.rst`, `/docs/` paths BLOCKED | None |
| Gate 4 — Keyword Blacklist | 60+ farming keywords (docstring, formatting, typo, lint, etc.) | `FEATURE_ADD` bypasses this gate |

### 3.5 Diff Minimizer — `generator/engine.py`

7-tier search/replace matching cascade:

| Tier | Strategy | Min Lines | Notes |
|------|----------|-----------|-------|
| 1 | Exact match | 1 | Literal string |
| 2 | Relaxed match | 1 | Strip trailing whitespace, normalize tabs→spaces |
| 3 | Stripped match | 1 (body>20 chars) | `search.strip()` |
| 4 | Indent-agnostic | 2 | Strip leading whitespace per line, re-indent replacement |
| 5 | Aggressive indent normalization | 1 | Strip ALL whitespace per line |
| 6 | Blank-line-agnostic | 2 non-blank | Remove all blank/whitespace-only lines |
| 7 | AST/Function-level fallback | 1 | Uses `target_function` field; Python `ast` module for `.py`, regex for others |

**Diff Minimizer ratio check**: If `replace_line_count / search_line_count > 2` OR `replace_line_count > 50`, edit is **BLOCKED** (prevents hallucinated full-file rewrites).
- `MAX_PATCH_RETRIES = 2` (configurable via `PipelineConfig.max_patch_retries`)

### 3.6 API Resilience

**MinimaxProvider** (`llm/provider.py`):
- 3 retries with exponential backoff for HTTP 429, 529, 402, and 5xx
- Backoff formula: `min(5 * (2 ** attempt), 60)` seconds
- Global semaphore: 4 concurrent calls
- Local quota tracking: `Memory.check_and_record_llm_quota()` (950/5hr, 9500/7day with 5% safety buffer)

**OpenRouterProvider** (`llm/provider.py`):
- Same 3-retry pattern, backoff `min(5 * (2 ** attempt), 60)` for 429, 529, 402, 403

**GitHubClient** (`github/client.py`):
- Multi-token rotation pool (primary + secondary)
- GET requests rotate tokens when `x-ratelimit-remaining < 50`
- 403 secondary rate limit: uses `retry-after` header or default `[60, 120]` second backoff
- 5xx: 3 retries with `2.0 * (attempt + 1)` second backoff
- Uses `httpx` with `trust_env=False`, granular timeouts (15s connect, 30s total)
- GraphQL falls back to REST on any error

---

## 4. Directory & Module Map

```
Agent-Farm/
├── config.yaml                  # Runtime configuration (secrets, limits, profiles)
├── target_repo.json             # Circular target list (seeds SQLite target_repos table)
├── Dockerfile                   # Production container
├── Dockerfile.superhuman        # Terminator mode container
├── docker-compose.yml           # Container orchestration
├── entrypoint.sh                # Docker entrypoint → farm_agent superhuman
├── Makefile                     # Build/run shortcuts
├── pyproject.toml               # Python project metadata & dependencies
├── requirements.txt             # Pinned dependencies
├── fix.py                       # Ad-hoc fix script (utility)
│
├── farm_agent/
│   ├── __init__.py               # Package version
│   │
│   ├── cli/
│   │   ├── main.py               # CLI entry point (click commands: run, target, analyze, solve, status, stats, config, superhuman)
│   │   └── tui.py                 # Rich TUI dashboard for monitoring
│   │
│   ├── orchestrator/
│   │   ├── pipeline.py           # ★ CORE: ContribPipeline (run_circular, run, hunt, run_single, _process_repo), anti-farming gates, DEV-QA loop
│   │   ├── human.py              # ★ SuperHumanLoop: Terminator Mode (infinite hunt-circular + patrol loop)
│   │   └── memory.py             # ★ SQLite persistent memory (all table schemas, CRUD operations)
│   │
│   ├── generator/
│   │   ├── engine.py             # ★ ContributionGenerator: Gag Order, Diff Minimizer (7-tier), False Positive detector, agentic generate loop
│   │   ├── scorer.py             # ★ QAHardcoreScorer: MIN_APPROVAL_SCORE=9.0, weighted grading, CI/CD exception
│   │   └── reviewer.py           # ★ ReviewerAgent: independent adversarial review (separate from generator)
│   │
│   ├── github/
│   │   ├── client.py             # ★ GitHubClient: REST+GraphQL, multi-token rotation, rate limiting, httpx
│   │   ├── discovery.py          # ★ RepoDiscovery (stochastic search), DatabaseTargetDiscovery (SQLite-backed circular)
│   │   ├── security_gate.py      # ★ Diplomat Protocol Task 1: SECURITY.md scan, 26 private-disclosure phrases, secret_findings/
│   │   └── guidelines.py          # ★ Diplomat Protocol Tasks 2-3: RepoStyleGuide extraction, PR template filling, adapt_pr_title/body
│   │
│   ├── pr/
│   │   ├── manager.py            # ★ PRManager: PR lifecycle, local git commit+push, Gag Order sanitization, CLA handling, Issue-First Protocol
│   │   ├── patrol.py             # ★ PRPatrol: review feedback, CI auto-healing, hostile maintainer detection, discussion reply limits
│   │   └── janitor.py.DISABLED   # DISABLED: Ruthless PR cleanup agent (closes/deletes GARBAGE PRs)
│   │
│   ├── issues/
│   │   └── solver.py             # IssueSolver: GitHub Issue classifier + multi-file contribution generator (IssueCategory enum)
│   │
│   ├── analysis/
│   │   ├── analyzer.py           # ★ CodeAnalyzer, BloodhoundAnalyzer (Semgrep-powered security radar + LLM White-Hat), Maintainer Vibe Check
│   │   ├── mapper.py             # RepoMapper: token-efficient structural map (Python ast + regex for JS/TS/Go/Rust)
│   │   ├── language_rules.py     # Language-specific security/quality rules for JS/TS, Go, Rust
│   │   ├── skills.py             # Progressive skill loading (on-demand prompts per language/framework)
│   │   └── strategies.py         # Framework-specific analysis strategies (detect framework → apply targeted rules)
│   │
│   ├── llm/
│   │   ├── provider.py           # ★ MinimaxProvider + OpenRouterProvider: exponential backoff, quota enforcement, semaphores
│   │   ├── router.py             # TaskRouter: routes tasks to optimal model (CostStrategy: PERFORMANCE/BALANCED/ECONOMY)
│   │   ├── models.py             # ModelSpec registry: capabilities, costs, context windows (MINIMAX_ABAB65S_CHAT, MINIMAX_M27)
│   │   ├── agents.py             # Multi-agent coordinator: specialized agents per task type
│   │   └── context.py            # ContextBudget: token estimation, chunking, prompt building from RepoContext
│   │
│   ├── agents/
│   │   └── registry.py           # Sub-agent registry (DeerFlow-inspired): AgentRole, AgentContext, 5 built-in agent stubs
│   │
│   ├── core/
│   │   ├── config.py             # ★ Full config system: GitHubConfig, LLMConfig, AnalysisConfig, PipelineConfig
│   │   ├── models.py             # ★ Pydantic models: Finding, Contribution, VulnerabilityDossier, QAResult, RepoContext, etc.
│   │   ├── exceptions.py          # Exception hierarchy: FarmAgentError, GitHubAPIError, LLMRateLimitError, GenerationError, ContextMissingError, etc.
│   │   ├── middleware.py          # Middleware chain: RateLimit, Validation, Retry, DCO, QualityGate
│   │   ├── retry.py              # Async retry decorators, LRUCache
│   │   ├── sandbox.py            # ★ DockerSandbox: Polyglot Guillotine (11 languages), hard 60s timeout
│   │   ├── rag.py                # RAGEngine: ephemeral ChromaDB, sliding-window chunking, auto-destroy after query
│   │   ├── quotas.py             # UsageTracker: in-memory daily limits (GitHub 5000/day, LLM 1000/day, 1M tokens/day)
│   │   ├── leaderboard.py        # LeaderboardEntry: PR merge/close rate tracking by repo
│   │   ├── daily_log.py          # DailyMarkdownLogger: append-only daily_log/daily_log_YYYY-MM-DD.md
│   │   ├── logger.py              # Daily rotating file logger setup
│   │   ├── notifier.py            # TelegramNotifier (used by Security Gate for private disclosure alerts)
│   │   └── profiles.py            # ContribProfile: named config presets (YAML-based)
│   │
│   ├── notifications/
│   │   └── notifier.py            # Notifier: multi-channel dispatcher (Slack, Discord, Telegram webhooks)
│   │
│   ├── plugins/
│   │   └── base.py                # AnalyzerPlugin + ContributionPlugin ABCs, PluginRegistry (entry-point discovery)
│   │
│   ├── templates/
│   │   ├── registry.py            # TemplateRegistry: prompt template management
│   │   └── builtin/               # Built-in prompt templates
│   │
│   └── tools/
│       └── protocol.py            # Tool Protocol + ToolRegistry: extensible tool support (DeerFlow-inspired)
│
├── secret_findings/              # Private vulnerability findings saved by Security Gate (JSON files)
├── data/                         # SQLite database (memory.db)
├── daily_log/                    # Daily markdown logs from SuperHumanLoop
├── logs/                         # Application logs
├── scripts/                      # Utility scripts
├── tests/                        # Test suite
└── docs/                         # Documentation
```

★ = Critical path module (pipeline will fail without it)

---

## 5. Database Schema

All tables live in `data/memory.db` (SQLite). Schema defined in `farm_agent/orchestrator/memory.py`.

| Table | Primary Key | Unique Constraints | Purpose |
|-------|-------------|-------------------|---------|
| `analyzed_repos` | `full_name` | — | Tracks repos that have been analyzed (language, stars, findings, metadata) |
| `submitted_prs` | `id` (auto) | `repo + pr_number` | All submitted PRs with status tracking (branch, fork, CI fix attempts, discussion replies) |
| `findings_cache` | `id` | — | Cached vulnerability findings (type, severity, file_path, status) |
| `run_log` | `id` (auto) | — | Pipeline run history (timestamps, repos analyzed, PRs created, errors) |
| `pr_outcomes` | `id` (auto) | `repo + pr_number` | PR outcome tracking (merged/closed, feedback, time to close) |
| `repo_preferences` | `repo` | — | Per-repo preferences (accepted/rejected types, merge rate, review hours) |
| `blacklisted_repos` | `repo` | — | Blacklisted repos with reason and timestamp |
| `api_usage_log` | `id` (auto) | — | API call tracking per provider |
| `task_schedule` | `task_key` | — | Scheduled task timestamps (next run time) |
| `knowledge_base` | — | `repo_name + entry_type + content` | QA lessons, style guides, learned patterns |
| `target_repos` | `repo_url` | — | Circular target queue (status, language, bounty_amount, diamond_target) |
| `repo_style_guides` | `repo` | — | Diplomat Protocol style guides (CONTRIBUTING.md → RepoStyleGuide cache) |

### Key Status Values in `target_repos`

| Status | Meaning |
|--------|---------|
| `PENDING` | Awaiting processing in circular loop |
| `PR_SUBMITTED` | Successfully passed QA+Sandbox, PR created |
| `COMPLETED_NO_VULN` | Bloodhound clean sweep or all non-production findings |
| `COMPLIANCE_SKIP_PRIVATE_DISCLOSURE` | Security Gate detected private disclosure policy |
| `COMPLETED_TOO_COMPLEX` | 3 DEV-QA cycles all failed QA (score < 9.0) |

---

## 6. Known Issues / Technical Debt

### 6.1 Disabled Features

| Feature | File | Status | Notes |
|---------|------|--------|-------|
| Janitor (PR cleanup) | `pr/janitor.py.DISABLED` | **DISABLED** | Ruthless PR garbage collector. Uses LLM to classify PRs as GARBAGE and closes/deletes them. Disabled by renaming to `.DISABLED`. Not dead code — could be re-enabled. |

### 6.2 Technical Debt

| Area | Description | Location |
|------|-------------|----------|
| Single-LLM routing | `TaskRouter` always returns MiniMax M2.7 regardless of task type; `CostStrategy` enum exists but is unused | `llm/router.py:30-60` |
| Gemini model references | `llm/models.py` docstring mentions "Gemini models" but only MiniMax models are registered | `llm/models.py:1-6` |
| No active code TODOs | Searched for TODO/FIXME/HACK/DIRTY — only found in prompt text strings, not in active code | Global |
| Janitor agent stub | `ComplianceAgent` in `agents/registry.py` is a minimal stub (checks CLA/DCO flags but doesn't implement real signing) | `agents/registry.py:188-215` |
| ContextMissingError defined | `ContextMissingError` exists for ChromaDB empty results but is not caught in pipeline.py — may cause unhandled exceptions if RAG returns nothing | `core/exceptions.py:52-58` |
| Hardcoded quota limits | LLM quotas (950/5hr, 9500/7day) are hardcoded in `Memory` class, not in `config.yaml` | `orchestrator/memory.py` |
| Semaphore concurrency | Minimax global semaphore = 4 concurrent calls; not configurable via config | `llm/provider.py` |

### 6.2 Architectural Observations

- **Terminator Mode** (`SuperHumanLoop`) has no graceful shutdown beyond SIGINT handling — could lose in-flight data on kill
- **PR creation** uses local git clone + commit + push (not GitHub Contents API), which requires SSH key or token-authenticated git in the environment
- **ChromaDB** is ephemeral (RAM-only) — all embeddings re-indexed per repo analysis, no cross-session persistence
- **UsageTracker** (`quotas.py`) is in-memory only with daily reset — no SQLite persistence, losing data on crash