# PROJECT_MAP.md — Agent-Farm Ground Truth

**Generated:** 2026-04-20  
**Version:** v3.2.0 — "Defense-in-Depth" Architecture  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence basis:** Direct code inspection. No assumptions. All line numbers are verified.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent that discovers open-source GitHub repositories, scans them for HIGH/CRITICAL severity vulnerabilities via multi-phase LLM + Semgrep analysis, generates validated patches, passes them through a two-layer garbage filter (Kimi → Gemini), runs the patch in a hermetically isolated Docker sandbox, then submits PRs or captures private disclosures — all without human intervention.

| Component | Technology | Source |
|-----------|------------|--------|
| Language | Python 3.11+ | `pyproject.toml` |
| HTTP client | `httpx` (async) | `pyproject.toml` |
| Primary LLM | `deepseek/deepseek-v3.2` via OpenRouter | `config.py:55` |
| Layer 1 Appraiser | `moonshotai/kimi-k2.5` via OpenRouter | `models.py:125`, `pipeline.py:2473` |
| Layer 2 Supreme Auditor | `google/gemini-3.1-pro-preview` via OpenRouter | `models.py:134`, `pipeline.py:2534` |
| Red Team (Bloodhound) | `cognitivecomputations/dolphin-mistral-24b-venice-edition:free` via OpenRouter | `config.py:67` |
| Semgrep rulesets | `p/security-audit`, `p/cwe-top-25`, `p/default`, `p/golang`, `p/rust`, `p/smart-contracts` | `config.py:117` |
| Database | SQLite (`aiosqlite`) — WAL mode, falls back to DELETE | `memory.py:154` |
| Docker Sandbox | `docker>=7.1` — complete network+cap isolation | `sandbox.py:512` |
| Config | Pydantic v2 + YAML + `.env` (dotenv) | `config.py:239` |
| CLI | `click>=8.1` + `rich>=13.0` | `main.py` |
| Vector DB | `chromadb>=0.4` — RAG for file context | `core/rag.py` |
| Scheduling | APScheduler (SuperHuman loop) | `human.py` |

---

## 2. CLI Commands

| Command | Python Method | Description |
|---------|--------------|-------------|
| `farm_agent run` | `ContribPipeline.run()` | Discover → analyze → generate → PR (multi-repo, parallel) |
| `farm_agent target <url>` | `ContribPipeline.run_single()` | Process one specific repo |
| `farm_agent hunt` | `ContribPipeline.hunt()` | Multi-round aggressive discovery (Issues FIRST, then analysis) |
| `farm_agent hunt-circular` | `ContribPipeline.run_circular()` | Deterministic round-robin from `target_repo.json` — Bloodhound mode |
| `farm_agent patrol` | `PRPatrol` | Check open PRs for feedback; auto-reply to reviewer comments |
| `farm_agent superhuman` | `SuperHumanLoop` | 24/7 organic loop mimicking a human dev schedule |
| `farm_agent solve <url>` | `IssueSolver` | Discover + solve open GitHub Issues in a repo |
| `farm_agent analyze <url>` | `ContribPipeline.analyze_only()` | Analysis pass only, no PR generation |

---

## 3. Core Execution Pipelines

### 3A. Standard Pipeline — `_process_repo()` (pipeline.py:1013)

Called by `run()`, `hunt()`, and `run_single()`. Runs full code analysis then contribution cycle.

```
_process_repo(repo)
  │
  ├─ [GATE 0] _check_ai_policy()                    # pipeline.py:1027
  │    └─ Scans AI_POLICY.md for "no ai-generated" etc. → skip if banned
  │
  ├─ [GATE 1] github.check_interaction_limits()     # pipeline.py:1036
  │    └─ Skip repos restricting to prior contributors only
  │
  ├─ fetch_repo_guidelines()                         # pipeline.py:1046
  │    └─ Parses CONTRIBUTING.md, PR template, caches to repo_style_guides
  │
  ├─ [GATE 2] check_maintainer_vibe()               # pipeline.py:1067
  │    └─ Fetches recent maintainer comments via GitHub API
  │    └─ If "HOSTILE" → blacklist repo, return early
  │
  ├─ CodeAnalyzer.analyze()                          # pipeline.py:1098
  │    └─ Runs 4 LLM analyzers in parallel: security, code_quality, docs, ui_ux
  │    └─ Injects FILTER_REJECTION_LESSON from memory into each analyzer prompt
  │
  ├─ [GATE 3] Pre-filter (non-code/protected files) # pipeline.py:1116
  │    └─ Drops SKIP_EXTENSIONS (.md .txt .yaml etc.)
  │    └─ Drops PROTECTED_META_FILES (tsconfig, eslintrc, package.json, .env, workflows, etc.)
  │    └─ Drops config bootstrap files (babel, webpack, vite, rollup)
  │
  ├─ [GATE 4] Anti-Farming Filter                   # pipeline.py:1174
  │    ├─ Gate 4a: DROP impact_level LOW or TRIVIAL
  │    ├─ Gate 4b: DROP ContributionType README_FIX, DOCS_IMPROVE (absolute ban)
  │    ├─ Gate 4c: DROP findings targeting .md/.txt/.rst files or docs/ paths
  │    └─ Gate 4d: DROP findings matching 50+ farming keywords (docstring, format, typo, test…)
  │         └─ Exception: FEATURE_ADD type bypasses keyword check
  │
  ├─ Deduplication                                   # pipeline.py:1360+
  │    └─ Bigram similarity check (80% overlap → duplicate) against SQLite + live GitHub PRs
  │
  ├─ _validate_findings() — Devil's Advocate Gate    # pipeline.py:1491
  │    └─ LLM re-validates each finding with a skeptical "Devil's Advocate" persona
  │    └─ Requires: is_real_vulnerability=true AND confidence_score≥90
  │    └─ Requires: data_flow_proof (exact variable names, no "If/Assume/Maybe")
  │    └─ JSON extracted via multi-step regex (fence strip → brace isolation → json.loads)
  │
  ├─ Limit to 2 findings per repo                   # pipeline.py:1494
  │
  ├─ [GATE 5] _layer1_expert_appraisal() per finding # pipeline.py:1512
  │    └─ Model: moonshotai/kimi-k2.5 (OpenRouter, copy.copy() of llm config)
  │    └─ Returns: (is_genuine: bool, critique: str)
  │    └─ On rejection → add_filter_lesson(repo, layer=1, snippet, critique) to SQLite
  │    └─ Fail-closed: any exception → (False, reason)
  │
  ├─ For each surviving finding → Route A or Route B:
  │    Route A (SECURITY_FIX / CRITICAL / HIGH / MEDIUM): Direct PR
  │    Route B (everything else): Issue-First (post GitHub Issue, skip PR)
  │
  └─ [Route A only] For each finding:
       ├─ ContributionGenerator.generate()            # engine.py:239
       │    └─ Injects: style_guide, project_map (Omniscient Eye), repo_prefs
       │    └─ Injects: FILTER_REJECTION_LESSON from memory
       │    └─ Patch-Correction Retry Loop (max_patch_retries=2)
       │    └─ Adversarial ReviewerAgent loop (max_review_retries=2)
       │    └─ Snippet Sanity Check: search==replace → abort (no-op guard)
       │
       ├─ DockerSandbox.run_in_sandbox()              # pipeline.py:1582
       │    └─ Max 3 attempts with self-correction between retries
       │    └─ Security: network_mode=none, mem_limit=512m, cap_drop=ALL
       │    └─ Timeout: 60s at 3 levels (OS kill, asyncio.wait_for, poll loop)
       │
       ├─ [GATE 6] _layer2_supreme_audit()            # pipeline.py:1652
       │    └─ Model: google/gemini-3.1-pro-preview (OpenRouter, copy.copy())
       │    └─ Audits: finding + patch + sandbox logs (full dossier)
       │    └─ Returns: (approved: bool, reason: str)
       │    └─ On rejection → add_filter_lesson(repo, layer=2, patch, reason)
       │    └─ Fail-closed: any exception → (False, reason)
       │
       ├─ [GATE 7] run_security_gate()                # pipeline.py:1667
       │    └─ Scans SECURITY.md / README for private disclosure phrases (60+ patterns)
       │    └─ If triggered: save to /app/secret_findings/{repo}.json → return
       │
       └─ PRManager.create_pr()                       # pipeline.py:1700
            └─ TOCTOU quota check inside human_typing_lock
            └─ Post-PR: check_compliance_and_fix(), _check_ci_and_close_if_failed()
```

---

### 3B. Circular Pipeline — `run_circular()` (pipeline.py:692)

Used by `hunt-circular` CLI command. Bloodhound + DEV-QA cycle without CodeAnalyzer.

```
run_circular()
  │
  ├─ DatabaseTargetDiscovery.get_next_target()       # oldest scanned_at from target_repos
  ├─ Check daily PR quota
  │
  ├─ [PHASE 1] BloodhoundAnalyzer.run_bloodhound()  # pipeline.py:758
  │    └─ Semgrep pre-scan (6 rulesets) → VulnerabilityDossier
  │    └─ If no bugs → mark COMPLETED_NO_VULN, return
  │
  ├─ Filter production_vulns (drop LOW_PRIORITY_CONTEXT from forbidden_paths) # pipeline.py:774
  │
  ├─ Fetch file contents for vulnerable files        # pipeline.py:807
  │
  └─ DEV-QA Cycle Loop (max 3 cycles):              # pipeline.py:845
       │
       ├─ [PHASE 2] ContributionGenerator.generate_from_dossier()   # pipeline.py:853
       │    └─ Injects: QA lessons + FILTER_REJECTION_LESSON from memory
       │    └─ Injects: Omniscient Eye (repo skeleton + dependency files)
       │    └─ Failure context from previous cycles injected into prompt
       │
       ├─ [PHASE 3] QAHardcoreScorer.evaluate()     # pipeline.py:884
       │    └─ LLM-based quality score ≥ threshold required (moonshotai/kimi-k2.6 via OpenRouter)
       │    └─ If rejected → record_qa_lesson(), inject critique into failure_context → retry
       │
       ├─ [PHASE 4] DockerSandbox (inside generate_from_dossier)
       │
       ├─ [PHASE 5] _layer2_supreme_audit()          # pipeline.py:923  ← AFTER QA
       │    └─ Audits: dossier + patch + accumulated failure_context as sandbox proxy
       │    └─ On veto → add_filter_lesson(repo, layer=2), mark COMPLETED_TOO_COMPLEX
       │
       ├─ [PHASE 6] run_security_gate()              # pipeline.py:934  ← AFTER Layer 2
       │    └─ If triggered → mark COMPLIANCE_SKIP_PRIVATE_DISCLOSURE, return
       │
       └─ PRManager.create_pr()                      # pipeline.py:956
            └─ On success → mark PR_SUBMITTED
```

> ⚠️ **Time-Travel Bug: RESOLVED.** `run_security_gate()` is guaranteed to execute at line 934 (after Layer 2 at line 923). No sandbox logs or patches exist before this point.

---

## 4. Active Protocols & Guardrails

| Protocol | Gate Location | Mechanism |
|----------|--------------|-----------|
| **AI Policy Gate** | `_process_repo():1027` | Scans `AI_POLICY.md`, `.github/AI_POLICY.md` for 10+ ban phrases. Skip if matched. |
| **Interaction Limits Gate** | `_process_repo():1036` | GitHub API `check_interaction_limits()`. Skip if repo locked to prior contributors. |
| **Maintainer Vibe Check** | `_process_repo():1067` | LLM classifies recent maintainer comments. "HOSTILE" → blacklist + skip. |
| **Pre-Filter (Non-Code)** | `_process_repo():1116` | Drops findings on SKIP_EXTENSIONS, PROTECTED_META_FILES, config files. |
| **Anti-Farming Filters (x4)** | `_process_repo():1174` | Impact gate / Docs ban / File-extension guillotine / 50+ keyword blacklist. |
| **Duplicate Detection** | `_process_repo():1360` | 80% bigram overlap → duplicate. Checks SQLite history AND live GitHub PRs. |
| **Devil's Advocate Gate** | `_validate_findings()` | LLM skeptically re-validates each finding. Needs `confidence≥90` + `data_flow_proof` with exact variable names. False positives with "If/Assume/Maybe" in proof are auto-dropped. |
| **Layer 1 — Kimi Appraiser** | `_layer1_expert_appraisal()` | `moonshotai/kimi-k2.5` via OpenRouter. Verifies finding is genuinely HIGH/CRITICAL. Fail-closed. Rejections → `add_filter_lesson` to DB. |
| **Layer 2 — Gemini Auditor** | `_layer2_supreme_audit()` | `google/gemini-3.1-pro-preview` via OpenRouter. Full dossier audit (finding + patch + sandbox logs). Fail-closed. Vetoes → `add_filter_lesson` to DB. |
| **Security Disclosure Gate** | `run_security_gate()` | 60+ private disclosure phrases in SECURITY.md / README → save to `/app/secret_findings/`, skip PR. |
| **Sandbox Guillotine** | `DockerSandbox` | `network_mode=none`, `mem_limit=512m`, `nano_cpus=0.5`, `cap_drop=ALL`, `pids_limit=128`. Triple timeout: OS kill + `asyncio.wait_for(60s)` + poll deadline loop. Hardcoded ON (`sandbox_validation_enabled=True`). |
| **Snippet Sanity Check** | `engine.py:447` | If patch `search == replace` (no-op) → abort PR to prevent empty spam. |
| **TOCTOU Quota Defense** | `pipeline.py:1687` | Inside `human_typing_lock`, re-check `get_today_pr_count()` before PR submission. |
| **Self-Learning Loop** | `memory.py:642`, `analyzer.py:582`, `engine.py:403,673` | Rejection critiques from Layer 1/2 stored as `FILTER_REJECTION_LESSON` in `knowledge_base`. Fetched per-repo and injected into Analyzer + Generator system prompts. |
| **Adversarial Reviewer** | `engine.py:492`, `reviewer.py` | Completely separate LLM entity reviews every generated patch. REJECT → rewrite with critique (up to `max_review_retries=2`). |
| **Patch-Correction Retry** | `engine.py:415` | If patcher fails (hallucinated SEARCH block) → re-prompt with actual file content. Up to `max_patch_retries=2`. |
| **Gag Order (AI Disclosure)** | `engine.py:146-152` | Scans all LLM output for AI disclosure strings (`as an ai`, `openai`, `farm_agent`, etc.). Abort generation if found. Security/vuln keywords rewritten to human-neutral terms. |
| **PROTECTED_META_FILES** | `pipeline.py:51` | ~40 files/patterns never modified: tsconfig, eslintrc, prettier, webpack, babel, package.json, .env, workflows, LICENSE, SECURITY.md |
| **Protected Extension Skip** | `pipeline.py:123` | SKIP_EXTENSIONS = `.md .txt .rst .yml .yaml .toml .cfg .ini .json` — never modified. |

---

## 5. The Self-Learning Protocol (Detail)

### Write Path
When Layer 1 or Layer 2 **rejects** a finding or patch:
```python
# pipeline.py:1516-1518 (Layer 1)
await self._memory.add_filter_lesson(repo.full_name, layer=1, snippet_or_fix=file_content, critique=critique)

# pipeline.py:1655-1657 (Layer 2)
await self._memory.add_filter_lesson(repo.full_name, layer=2, snippet_or_fix=patch_str, critique=reject_reason)
```

### Storage (memory.py:642)
```sql
INSERT OR REPLACE INTO knowledge_base (repo_name, entry_type, content, created_at)
VALUES (?, 'FILTER_REJECTION_LESSON', ?, ?)
```
Deduplication on `UNIQUE(repo_name, entry_type, content)`.

### Read Path → Prompt Injection
```python
# analyzer.py:582 — injected into EVERY analyzer's system prompt
lessons = await self._memory.get_knowledge(context.repo.full_name, "FILTER_REJECTION_LESSON")
system += f"\n\n### PREVIOUS MISTAKES TO AVOID ON THIS REPO:\n{lessons}\n"

# engine.py:401-407 — generate() standard path
filter_lessons = await self._memory.get_knowledge(context.repo.full_name, "FILTER_REJECTION_LESSON")
system += f"\n\n### PREVIOUS MISTAKES TO AVOID ON THIS REPO:\n{filter_lessons}\n"

# engine.py:672-677 — generate_from_dossier() circular path
filter_lessons = await self._memory.get_knowledge(context.repo.full_name, "FILTER_REJECTION_LESSON")
qa_lessons_section += f"\n\n### PREVIOUS MISTAKES TO AVOID ON THIS REPO:\n{filter_lessons}\n"
```

**Isolation guarantee:** SQL `WHERE repo_name = ? AND entry_type = ?` — repo-A lessons never appear in repo-B prompts.

---

## 6. Database Schema & Persistence

### Docker Volume Strategy (`docker-compose.yml`)

```yaml
volumes:
  - ./data:/app/data                    # SQLite memory.db — survives container restarts
  - ./secret_findings:/app/secret_findings  # Private disclosure JSON files
  - /var/run/docker.sock:/var/run/docker.sock  # DinD for sandbox containers
```

Networks: `internet_access` (bridge, for GitHub API) + `sandbox_isolated` (internal=true, for sandbox containers).

### SQLite DB — `data/memory.db` (WAL mode, fallback DELETE)

| Table | Key Columns | Purpose |
|-------|------------|---------|
| `analyzed_repos` | `full_name` PK | Track scanned repos — dedup guard |
| `submitted_prs` | `(repo, pr_number)` UNIQUE | All submitted PRs + CI retry count + reply count |
| `findings_cache` | `id` PK, `repo`, `type`, `severity` | Temporary finding storage |
| `run_log` | `id` PK, `started_at` → `finished_at` | Historical pipeline run stats |
| `pr_outcomes` | `(repo, pr_number)` UNIQUE | Outcome tracking (merged/closed) |
| `repo_preferences` | `repo` PK | Per-repo learned style preferences |
| `blacklisted_repos` | `repo` PK | Permanently blocked repos (toxic maintainer, etc.) |
| `api_usage_log` | `provider`, `timestamp` | LLM API quota tracking (5-hour + 7-day windows) |
| `task_schedule` | `task_key` PK | Persistent task scheduling for SuperHumanLoop |
| `knowledge_base` | `UNIQUE(repo_name, entry_type, content)` | QA lessons + **`FILTER_REJECTION_LESSON`** entries for Self-Learning |
| `target_repos` | `repo_url` PK, `status`, `scanned_at` | Circular hunt target queue |
| `repo_style_guides` | `repo` PK | Cached CONTRIBUTING.md parse + PR template |

**Active migrations:** `ci_fix_attempts INTEGER DEFAULT 0` and `discussion_replies INTEGER DEFAULT 0` auto-added to `submitted_prs` on init.

### Secret Findings Path

```python
# security_gate.py:20
_SECRET_FINDINGS_DIR = Path("/app/secret_findings")
```

Files written as `{_SECRET_FINDINGS_DIR}/{safe_repo_name}.json` containing the full vulnerability dossier, timestamp, and disclosure trigger phrase.

---

## 7. Configuration Limits & Thresholds

| Parameter | Default | Source |
|-----------|---------|--------|
| `max_repos_per_run` | 5 | `config.py:20` |
| `max_prs_per_day` | 10 | `config.py:21` |
| `rate_limit_buffer` | 3 | `config.py:24` |
| `max_concurrent_repos` | 3 (capped by llm_concurrency_cap) | `config.py:180`, `pipeline.py:229` |
| `timeout_per_repo_sec` | 300 | `config.py:181` |
| `max_ci_retries` | 3 | `config.py:183` |
| `max_discussion_replies` | 3 | `config.py:184` |
| `max_patch_retries` | 2 | `config.py:185` |
| `max_review_retries` | 2 | `config.py:186` |
| `sandbox_validation_enabled` | `True` (hardcoded, never bypassed) | `config.py:188` |
| `max_files_per_pr` | 10 | `config.py:136` |
| `max_snippet_chars` | 15000 | `config.py:68` |
| `red_team_daily_limit` | 1000 OpenRouter calls/day | `config.py:114` |
| `DEV-QA max cycles` | 3 | `pipeline.py:825` |
| Sandbox execution timeout | 60s (3 levels) | `sandbox.py:217` |
| Bigram overlap threshold | 80% | `pipeline.py:185` |
| Devil's Advocate confidence threshold | ≥ 90 | `pipeline.py:2431` |

---

## 8. Directory & Module Architecture

```
farm_agent/                             # Package root (version = "3.0.0")
├── __init__.py
│
├── cli/
│   └── main.py                         # Click CLI — all commands
│
├── core/
│   ├── config.py                       # Pydantic v2 config: FarmAgentConfig + load_config()
│   ├── daily_log.py                    # Daily rolling structure logger
│   ├── exceptions.py                   # GitHubAPIError, LLMRateLimitError, ContextMissingError
│   ├── leaderboard.py                  # PR stats aggregation
│   ├── logger.py                       # Logging setup (daily rotating files)
│   ├── middleware.py                   # DeerFlow-style middleware chain
│   ├── models.py                       # Pydantic models: Repository, Finding, Contribution, etc.
│   ├── notifier.py                     # TelegramNotifier
│   ├── profiles.py                     # quick/standard/thorough contribution profiles
│   ├── quotas.py                       # Quota tracking helpers
│   ├── rag.py                          # ChromaDB RAG pipeline (ACTIVE — used by analyzer)
│   ├── retry.py                        # @async_retry, @github_retry, @llm_retry decorators
│   └── sandbox.py                      # DockerSandbox — Polyglot Guillotine (12 languages)
│
├── analysis/
│   ├── analyzer.py                     # CodeAnalyzer (LLM-based, 7 analyzers)
│   │                                   # BloodhoundAnalyzer (Semgrep + LLM dossier)
│   │                                   # Both inject FILTER_REJECTION_LESSON from memory
│   └── mapper.py                       # RepoMapper — Omniscient Eye skeleton + dep graph
│
├── generator/
│   ├── engine.py                       # ContributionGenerator.generate() + generate_from_dossier()
│   │                                   # Injects filter lessons, QA lessons, style guide, project map
│   │                                   # Anti-template interceptor, Gag Order, Snippet Sanity Check
│   ├── reviewer.py                     # ReviewerAgent — adversarial self-review loop
│   └── scorer.py                       # QAHardcoreScorer — QA evaluation for circular pipeline
│
├── github/
│   ├── client.py                       # GitHubClient — REST + GraphQL, @async_retry wrapped
│   ├── discovery.py                    # RepoDiscovery (network search) + DatabaseTargetDiscovery
│   ├── guidelines.py                   # fetch_repo_guidelines() — CONTRIBUTING.md + PR template
│   └── security_gate.py               # run_security_gate() — private disclosure → /app/secret_findings
│
├── issues/
│   └── solver.py                       # IssueSolver — fetch + classify + solve open issues
│
├── llm/
│   ├── agents.py                       # DeerFlow-style LLM agent definitions
│   ├── context.py                      # build_generator_system_prompt(), extract_style_guide()
│   ├── models.py                       # ModelSpec registry: KIMI_K2_APPRAISER, GEMINI_31_AUDITOR
│   │                                   # ALL_MODELS, MODELS_BY_NAME, get_model()
│   ├── provider.py                     # create_llm_provider() — OpenRouter backend
│   └── router.py                       # TaskRouter — per-task model assignment
│
├── orchestrator/
│   ├── memory.py                       # Memory class — SQLite ops, add_filter_lesson, get_knowledge
│   ├── pipeline.py                     # ContribPipeline — THE CORE ENGINE (2867 lines)
│   │                                   # _process_repo(), run_circular(), hunt()
│   │                                   # _layer1_expert_appraisal(), _layer2_supreme_audit()
│   │                                   # _validate_findings() (Devil's Advocate)
│   └── human.py                        # SuperHumanLoop — 24/7 organic dev pacing
│
├── pr/
│   ├── manager.py                      # PRManager.create_pr() — fork, branch, commit, push, PR
│   ├── patrol.py                       # PRPatrol — auto-reply to reviewer comments, CI monitoring
│   └── janitor.py.DISABLED            # ⚠️ DISABLED — janitor functionality offline
│
├── agents/
│   └── registry.py                     # create_default_registry() — DeerFlow agent registry
│
├── tools/
│   └── protocol.py                     # create_default_tools(), GitHubTool, READ_FILE_TOOL_SCHEMA
│
├── notifications/
│   └── notifier.py                     # Multi-channel notifier (Slack/Discord/Telegram)
│
├── plugins/                            # Plugin base (inactive — no active plugins)
└── templates/                          # Template registry (inactive)

scripts/
├── cleanup_forks.py                    # Standalone fork cleanup utility
├── inject_ci_trap.py                   # CI test injection
├── inject_maintainer_feedback.py       # Maintainer feedback simulation
└── vip_repos_radar.py                  # VIP repo tracking

tests/
├── unit/
│   ├── test_circular_target.py
│   ├── test_concurrency_cap.py
│   └── test_pr_creation_integrity.py
└── test_async_io_pipeline.py

docker-compose.yml                      # Service definition + volume bindings
Dockerfile                              # WORKDIR=/app, Python 3.11-slim
target_repo.json                        # Circular hunt target list (seed file)
config.yaml                             # Runtime config (YAML, loaded by load_config())
```

---

## 9. Error Handling & Fallback Matrix

| Scenario | Behavior |
|----------|----------|
| No config file | All defaults used; token from `GITHUB_TOKEN` env → `gh auth token` CLI |
| Layer 1 / Layer 2 API failure | **Fail-Closed** → `(False, "Instantiation failed: …")` — finding/PR dropped |
| Sandbox Docker unavailable | Returns error dict; PR creation **BLOCKED** |
| Sandbox timeout (60s) | Exit code 137; stderr = "Sandbox execution timed out after 60s" |
| All analysts fail | `AnalysisError` raised (if 0 out of N succeeded) |
| LLM quota breach (5h/7d window) | `LLMRateLimitError` → cooldown |
| GitHub 429 rate limit | `rate_limit_retry`: 5 retries, base 10s, max 120s, ±25% jitter |
| GitHub API error | `async_retry`: 3 retries, base 2s, max 60s |
| LLM error | `llm_retry`: 3 retries, base 3s, max 60s |
| Daily PR quota exhausted | Pipeline returns early (checked at start + TOCTOU check before each PR) |
| All DEV-QA cycles fail | Mark `COMPLETED_TOO_COMPLEX` in target_repos |
| Private disclosure detected | Save to `/app/secret_findings/`, Telegram notification, skip PR |
| Toxic maintainer ("HOSTILE") | Add to `blacklisted_repos`, return early |

---

## 10. Known Technical Debt

| ID | Description | Source |
|----|-------------|--------|
| ~~`DEBT-04`~~ | **RESOLVED** — Two indexes added: `idx_api_usage(provider, timestamp)` for COUNT queries; `idx_api_usage_cleanup(timestamp)` for periodic DELETE. `get_openrouter_usage_today` rewritten from non-indexable `date()` transform to Unix timestamp range comparison. | `memory.py:163` |
| ~~`CRIT-03`~~ | **RESOLVED** — Replaced `min(max_conc, 5)` hardcode with `AdaptiveConcurrencyManager`. Cap now reads from `pipeline.llm_concurrency_cap` (config.yaml). On `LLMRateLimitError`: drops to 1, waits `rate_limit_cooldown_sec` (default 300s), ramps back +1/60s. | `pipeline.py:188`, `config.py:191` |
| `P0-FIX v2` | Sandbox wrapped with `timeout --signal=KILL` (replaced broken `stop_timeout`) | `sandbox.py:503` |
| `Crucible BUG` | `client.api.wait()` had 60s HTTP hard limit — replaced with polling loop | `sandbox.py:585` |
| `PHASE 2-FIX` | Manifest-driven language detection (package.json → tsconfig → Cargo.toml) | `sandbox.py:120` |
| `PHASE 3-FIX` | Bigram sequence overlap (80%) replaced naive word intersection (50%) | `pipeline.py:185` |
| Janitor disabled | `pr/janitor.py.DISABLED` — functionality offline, renamed to prevent import | `pr/` dir |

---

*All evidence anchored to source files. All line numbers verified by direct inspection. No speculation.*