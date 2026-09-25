# PROJECT_MAP.md — Agent-Farm Ground Truth

> **2026-09-25 documentation handoff, reconciled after `4467ffa`:** [Agent-Farm v2 — Continuation Implementation Prompts.en.md](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/Agent-Farm%20v2%20%E2%80%94%20Continuation%20Implementation%20Prompts.en.md) gives explicit M2–M6 work steps and evidence gates. The M2 CLI slice and source plans were committed in `4467ffa`; the earlier description of them as uncommitted is historical. Earlier checks reported 16 focused M2 passes and 124 full-suite passes with an `AsyncMock` warning; rerun them before accepting any later slice. This documentation revision does not complete M2 or change runtime behavior.

> **2026-09-25 audit note:** This map was generated for an older checkout path and contains stale behavioral claims. The verified read-only architecture review and forward plan are in [Agent-Farm v2 — Verified Upgrade Roadmap.md](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/Agent-Farm%20v2%20%E2%80%94%20Verified%20Upgrade%20Roadmap.md). Re-audit source paths and runtime contracts before using this map for implementation.

> **Last Ground-Truth Audit:** 2026-09-25T14:26:53+07:00. **Current milestone: M0 baseline and telemetry implemented; real token/cost usage remains unmeasured until provider integration.** This section is current; the older generated inventory below remains historical and must not be used as proof of present behavior.
>
> **M0 active paths:** [pipeline.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/pipeline.py) (`run_circular`, `_process_repo`, `_process_repo_impl`, `_m0_event`), [memory.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/memory.py) (`scan_events`, `record_scan_event`, `get_scan_events`), [manifest.json](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/corpus/manifest.json), [targets.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/corpus/targets.py), [m0_report.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/scripts/m0_report.py), [m0-baseline.md](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/docs/m0-baseline.md).
>
> **Verification:** Baseline 81 pytest passes with workspace temp directory; after M0, 84 passes with the same warning. Pre-existing Ruff total: 707. M0 is metadata telemetry and offline corpus only. Next: M1 security state and fail-closed gates across both pipelines, followed by PR/patrol integration.
>
> **M1 phase 1 (2026-09-25):** [security/state.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/state.py), [security/evidence.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/evidence.py), and [security/closure.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/closure.py) define candidate closure and four-way PoC outcomes. [memory.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/memory.py) persists candidates and evidence with commit binding. [poc.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/generator/poc.py) distinguishes runtime errors from negative results. Focused verification: 16 tests passed. **Next:** wire fail-closed decisions into both live pipelines; phase 1 alone does not make publication safe.
>
> **M1 phase 2 (2026-09-25):** [pipeline.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/pipeline.py) now pins a local target SHA, closes security candidates as `OPEN_PROOF_GAP` for missing/failed PoC, baseline failure, missing sandbox, or unknown SHA, and generates fixes only after a `TRIGGERED` verdict and stored evidence. Patched PoC must exit cleanly; failed/skipped native tests no longer pass as success. [sandbox.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/core/sandbox.py) rejects path traversal and existing PoC filenames. **Next:** circular scanner status and proof gate, then publication/patrol gate.
>
> **M1 phase 3 (2026-09-25):** [analyzer.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/analysis/analyzer.py) raises `ScanIncompleteError` on missing scanner, timeout, invalid output, clone failure or unknown target SHA. `run_circular` converts Bloodhound results to `Finding` and passes them to `_process_repo` with the scanner SHA; both hunting paths now use the same PoC/fix gate. Empty prefilter results and scanner failures mark `PARTIAL_SCAN`, never `COMPLETED_NO_VULN`. The old circular DEV-QA patch branch was removed. **Next:** central PR/disclosure/patrol publication gate.

> **M1 phase 4 (2026-09-25):** [security/closure.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/closure.py) verifies a confirmed candidate against the exact repository, file, title, and target SHA before publication. [pr/manager.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/pr/manager.py) checks before GitHub writes and blocks public security issues. [github/security_gate.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/github/security_gate.py) checks before private dossier, GHSA, or secret-finding output. [pr/patrol.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/pr/patrol.py) blocks automatic code/CI updates for security or untyped PRs pending a later independent fix-verification contract. Verification: 107 pytest passes, one pre-existing AsyncMock warning.

> **M1 phase 5 (2026-09-25):** [pipeline.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/pipeline.py) fetches source files at the target commit SHA and closes security candidates as `OPEN_PROOF_GAP` with `SOURCE_UNAVAILABLE` when the affected file cannot be read. [test_m1_standard_gate.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/unit/test_m1_standard_gate.py) verifies that no fix is generated for missing source and that retrieval uses the pinned SHA. This closes the remaining M1 missing-source acceptance case. **M1 gate complete; M2 onward remain planned.**

> **M2 phase 1 (2026-09-25):** [security/scope.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/scope.py) defines exact repository/SHA program policies, scan manifests, permitted publication channels and exact-origin request policy. [memory.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/memory.py) stores an integrity-checked immutable manifest and atomically spends request budget. [security/transport.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/transport.py) sends actual HTTP requests with redirect following disabled. [closure.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/closure.py), [manager.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/pr/manager.py), and [security_gate.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/github/security_gate.py) require the stored scope before security publication. [test_m2_scope_real.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/integration/test_m2_scope_real.py) uses real SQLite and loopback HTTP. Next: scan-local threat model, coverage ledger, semantic verifier and immutable artifacts. **M2 is not complete.**

> **M2 phase 2 (2026-09-25):** [security/threat_model.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/threat_model.py) captures operator supplied actors, trust boundaries, assets, inputs and stories with provenance and versioned amendments. [security/coverage.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/coverage.py) reports tested/not-tested/blocked/inconclusive without a false clean verdict. [memory.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/memory.py) persists both with integrity and transition checks; [pipeline.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/pipeline.py) initializes them for authorized scans and emits completion state. [test_m2_coverage_real.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/integration/test_m2_coverage_real.py) verifies restart persistence. Next: real HTTP semantic verifier and protected canonical artifacts. **M2 is not complete.**

> **M2 phase 3 (2026-09-25):** [security/oracles.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/oracles.py) executes four ordered HTTP probes and evaluates IDOR, SQL injection, SSRF, traversal and command injection through structured content or independent side effects; transport errors remain inconclusive. [security/verifier.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/verifier.py) binds the oracle to a live scan, records semantic evidence and coverage, and closes candidates only after observed impact. [closure.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/closure.py) now requires semantic proof for external publication. [test_m2_oracles_real.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/integration/test_m2_oracles_real.py) uses separate running vulnerable/fixed loopback services, a real callback server and a filesystem side effect. The mocked GHSA positive tests were removed; no external GHSA operation is claimed. Next: immutable canonical probe artifacts and Docker mount verification. **M2 is not complete.**

> **M2 phase 4 (2026-09-25):** [security/artifacts.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/artifacts.py) stores canonical oracle JSON by SHA-256 and rejects changed bytes. [security/verifier.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/verifier.py) reloads the artifact after live HTTP probes and before persisting proof. [core/sandbox.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/core/sandbox.py) mounts the artifact read-only outside the patch workspace and now reads finite Docker logs after exit. [test_m2_artifact_docker_real.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/integration/test_m2_artifact_docker_real.py) passed with Docker daemon 29.3.1 and a locally available Python image; mount write failed, artifact hash stayed stable, normal sandbox output was captured, no labeled container remained. [test_m2_oracles_real.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/tests/integration/test_m2_oracles_real.py) also proves target-side artifact tampering cannot create semantic evidence. Next: CLI operator flow and final M2 integration audit. **M2 is not complete.**

> **M2 phase 5 (2026-09-25):** [cli/main.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/cli/main.py) adds the operator workflow (`register-live-scan`, `register-candidate`, `register-oracle`, `verify-candidate`, `scope-report`, `security-candidates`); the global `live_testing_enabled` switch defaults off and a matching `ProgramScope.allow_live_testing` is required. Completion audit fixed the two `E501` findings introduced in `4467ffa` and added fail-closed guards: [verifier.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/security/verifier.py) refuses to re-verify a candidate that already holds semantic proof (no silent request-budget spend), and [pipeline.py](file:///C:/Users/USER/Documents/GitHub/Bug-Bounty/Agent-Farm/farm_agent/orchestrator/pipeline.py) requests `mode="live"` only when the matched `ProgramScope.allow_live_testing` holds, recording `LIVE_TESTING_NOT_AUTHORIZED` as a scope gap instead of a raw validation crash; candidate paths are validated as repository-relative POSIX paths; CLI refusals (wrong commit, excluded endpoint/origin, wrong role/impact, exhausted budget, tampered artifact, missing witness, empty/transport semantics) are proven to leave the candidate unproven and unpublishable through the real publication guard on every channel. Verified: focused M2 integration 24 passed; full suite 133 passed with the pre-existing AsyncMock warning; Docker artifact 2 passed. Accepts the CLI slice only; **automatic-pipeline proof integration and the remaining proof-integrity checks stay open (M2 not complete).**

**Generated:** 2026-06-02  
**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence basis:** Direct code inspection. No assumptions. All line numbers are verified.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter (Qwen → Gemini), and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

Version 4.0.0 introduces the **Omniscient Context Engine**, which recursively discovers repository documentation, chunks it semantically by markdown headers, ingests it into ChromaDB, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents. Furthermore, version 4.0.0 incorporates **Dynamic Bug Verification** (generating and executing Proof-of-Concept exploits in an isolated container sandbox, evaluated via LLM) and **Blast Radius & Regression Auditing** (using baseline test suite runs and downstream dependent analysis to guarantee zero regressions).

| Component | Technology | Source |
|-----------|------------|--------|
| Language | Python 3.11+ | `pyproject.toml` |
| HTTP client | `httpx` (async) | `pyproject.toml` |
| Primary LLM | `deepseek/deepseek-v4-flash` via OpenRouter | `config.py:56` |
| Code Gen LLM | `deepseek/deepseek-v4-pro` via OpenRouter | `pipeline.py:395` |
| Layer 1 Appraiser | `qwen/qwen3.7-max` via OpenRouter | `pipeline.py:2790` |
| Layer 2 Supreme Auditor | `google/gemini-3.5-flash` via OpenRouter | `pipeline.py:2851` |
| Red Team (Bloodhound) | `deepseek/deepseek-v4-flash` via OpenRouter | `config.py:109` |
| Semgrep rulesets | `p/security-audit`, `p/cwe-top-25`, `p/default`, `p/golang`, `p/rust`, `p/smart-contracts` | `config.py:114` |
| Database | SQLite (`aiosqlite`) — WAL mode, fallback to DELETE | `memory.py:151` |
| Docker Sandbox | `docker>=7.1` — complete network + capability isolation | `sandbox.py:198` |
| Config | Pydantic v2 + YAML + `.env` | `config.py:222` |
| CLI | `click>=8.1` + `rich>=13.0` | `main.py` |
| Vector DB | `chromadb>=0.4` — RAG for file & documentation context | `core/rag.py` |
| Notifications | Telegram / Slack / Discord | `notifier.py` |

---

## 2. CLI Commands

The CLI is Click-based and located in [main.py](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/cli/main.py).

| Command | Python Method | Description |
|---------|--------------|-------------|
| `farm_agent advisories` | `advisories()` | List all Bug Bounty security advisory dossiers generated in `bounty_reports/`. |
| `farm_agent run` | `FarmAgentPipeline.run()` | Standard run: discover, analyze, generate fixes, run sandbox, check gates, submit PRs. |
| `farm_agent target <url>` | `FarmAgentPipeline.run_single()` | Process a single target repository. |
| `farm_agent hunt` | `FarmAgentPipeline.hunt()` | Run multi-round search and analysis (analysis, issues, or both). |
| `farm_agent hunt-circular` | `FarmAgentPipeline.run_circular()` | Deterministic round-robin target loop from `target_repo.json`. |
| `farm_agent patrol` | `PRPatrol.patrol()` | Check open PRs for maintainer review comments, reply to questions, and auto-fix CI failures. |
| `farm_agent superhuman` | `SuperHumanLoop.run_daily_routine()` | 24/7 loop cycling through circular target hunt and patrol operations with Circadian awareness. |
| `farm_agent solve <url>` | `IssueSolver` flow | Proactively search for solvable issues in a repo, construct deep fixes, and generate PRs. |
| `farm_agent analyze <url>` | `FarmAgentPipeline.analyze_only()` | Perform code analysis pass only; do not generate contributions or open issues. |
| `farm_agent status` | `_show()` | Show targets queue statuses from `target_repos` table. |
| `farm_agent stats` | `_get_stats()` | Show current runtime and OpenRouter API usage statistics. |
| `farm_agent cleanup` | `_cleanup()` | Purge local temporary files and cleanup stale forks. |
| `farm_agent reset-db` | `reset_db()` | Recreate database tables and reset memory database. |
| `farm_agent config` | `show_config()` | Output the current loaded runtime settings. |
| `farm_agent vips` | `vips()` | Monitor and synchronize VIP repository radar list. |
| `farm_agent templates` | `list_templates()` | Display dynamic LLM contribution generation status. |
| `farm_agent profile` | `run_profile()` | Run the pipeline pre-loaded with quick, standard, or thorough presets. |
| `farm_agent models` | `show_models()` | List the active LLM routing mappings. |
| `farm_agent leaderboard` | `show_leaderboard()` | Show leaderboards of merged and submitted contributions. |
| `farm_agent gc` | `gc()` | Purge knowledge base entries older than N days. |

---

## 3. Core Execution Pipelines

### 3A. Standard Pipeline — `_process_repo()` ([pipeline.py:1172](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/orchestrator/pipeline.py#L1172))

Processes a single repository through the full contribution pipeline:

```
_process_repo(repo)
  │
  ├─ Early Clone Initialization                         # pipeline.py:1186
  │    └─ Clones repository early to local temporary directory to populate codebase
  │
  ├─ Baseline Native Test Run                           # pipeline.py:1194
  │    └─ Runs unpatched native tests once to establish pre-existing failure baseline
  │
  ├─ [GATE 0] _check_ai_policy()                        # pipeline.py:1206
  │    └─ Scans AI_POLICY.md for AI-generated PR bans → skip if matches found
  │
  ├─ [GATE 1] github.check_interaction_limits()         # pipeline.py:1215
  │    └─ Skips repository if restricted to prior contributors only
  │
  ├─ fetch_repo_guidelines()                            # pipeline.py:1225
  │    └─ Parses CONTRIBUTING.md, templates, and style guidelines
  │
  ├─ discover_subsystem_docs()                          # pipeline.py:1231
  │    └─ Recursively discovers doc files (.md, .txt, .rst) inside cloned repo directory
  │
  ├─ RepoIndexer.index_repo()                           # pipeline.py:1238
  │    └─ Semantically chunks documentation by headers and indexes into ChromaDB asynchronously
  │
  ├─ [GATE 2] check_maintainer_vibe()                   # pipeline.py:1260
  │    ├─ Fetches recent maintainer comments
  │    └─ If "HOSTILE" comments found → blacklist repo and abort run
  │
  ├─ CodeAnalyzer.analyze()                             # pipeline.py:1291
  │    └─ Runs parallel LLM analyzers (security, code_quality, docs, ui_ux)
  │
  ├─ AST Dependency Injection                           # pipeline.py:1295-1310
  │    ├─ Reads all files, generates structural skeleton via RepoMapper
  │    └─ Injects imports, calls, and dependents into Finding.metadata["module_dependencies"]
  │
  ├─ [GATE 3] Pre-Filter (Non-code files check)         # pipeline.py:1323
  │    ├─ Skips findings targeting SKIP_EXTENSIONS (.md, .txt, .yaml, etc.)
  │    └─ Skips config/build files (tsconfig, eslintrc, package.json, workflows)
  │
  ├─ [GATE 4] Anti-Farming Filters                      # pipeline.py:1385
  │    ├─ Gate 4a: Drops security findings unless severity is CRITICAL or HIGH (Route A rule) # pipeline.py:1459
  │    ├─ Gate 4b: Drops non-security findings if impact_level is LOW or TRIVIAL # pipeline.py:1468
  │    ├─ Gate 4c: Drops README_FIX and DOCS_IMPROVE types # pipeline.py:1480
  │    ├─ Gate 4d: Drops findings on documentation paths (e.g. /docs/, docs/) # pipeline.py:1495
  │    └─ Gate 4e: Keyword blacklist match on title/description # pipeline.py:1523
  │
  ├─ Deduplication                                      # pipeline.py:1642
  │    └─ Filters duplicate titles using bigram similarity check (80% threshold)
  │
  ├─ _validate_findings() (Devil's Advocate Gate)       # pipeline.py:1711 (impl: 2604)
  │    ├─ LLM evaluates findings skeptically using strict validation checklist
  │    └─ Requires is_real_vulnerability=True AND confidence_score>=90
  │
  ├─ Limit to maximum 2 findings per repo               # pipeline.py:1714
  │
  ├─ [GATE 5] _layer1_expert_appraisal()                # pipeline.py:1732 (impl: 2773)
  │    ├─ Model: qwen/qwen3.7-max
  │    └─ Verifies finding is genuine and severe. Fail-closed on error.
  │
  ├─ Hybrid Router (Route A vs Route B)                 # pipeline.py:1744
  │    ├─ Route A (Direct PR): Used for SECURITY_FIX and Severity CRITICAL/HIGH/MEDIUM
  │    └─ Route B (Issue-First): Propose fix in issue and skip PR (Performance, Refactor, UI/UX, etc.)
  │
  ├─ [Route A only] [Verification Gate] (Phase 3)       # pipeline.py:1759
  │    ├─ PoCGenerator.generate_poc() -> Creates test script # pipeline.py:1772
  │    ├─ Sandbox.verify_vulnerability_with_poc() -> Runs script in isolated container # pipeline.py:1776
  │    └─ PoCGenerator.evaluate_poc_result() -> LLM checks if vulnerability triggered (True Positive) # pipeline.py:1784
  │         └─ If not triggered → drop finding as False Positive (save token usage)
  │
  ├─ [Route A only] Fix Generation                      # pipeline.py:1816
  │    └─ ContributionGenerator.generate() with Style Guide context and dependents context
  │
  ├─ Double-Pass Sandbox Validation (DEV-QA Loop)      # pipeline.py:1832-1925
  │    ├─ Pass 1 (Efficacy): Executes PoC on patched code. PoC MUST NOT trigger vulnerability. # pipeline.py:1866
  │    ├─ Pass 2 (Regression): Runs native tests. Rejects if baseline passed but patched code fails. # pipeline.py:1888
  │    │    └─ Fallback: Runs compilation/syntax checks in sandbox if no native tests exist. # pipeline.py:1904
  │    └─ Clean State Reversion: Reverts cached clone via `git reset --hard` and `git clean -fd`
  │         before applying patch on retry
  │
  ├─ Self-Correction Loop                               # pipeline.py:1933
  │    └─ If validation fails, LLM retries fix with stderr logs (max 3 validation attempts)
  │
  ├─ [GATE 6] _layer2_supreme_audit()                   # pipeline.py:1969 (impl: 2837)
  │    └─ Model: google/gemini-3.5-flash checks incident dossier, sandbox logs & proposed patch
  │
  ├─ [GATE 7] Diplomat: Security Disclosure Gate       # pipeline.py:1984
  │    └─ Bypasses PR if security targets require private disclosure
  │
  └─ PRManager.create_pr()                              # pipeline.py:2017
```

---

### 3B. Circular target pipeline — `run_circular()` ([pipeline.py:834](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/orchestrator/pipeline.py#L834))

Circular target pipeline loop extracting target repos from the local SQLite queue:

```
run_circular()
  │
  ├─ DatabaseTargetDiscovery.get_next_target()          # Picks oldest scanned target # pipeline.py:854
  ├─ Check daily PR limit cap
  │
  ├─ [PHASE 1] BloodhoundAnalyzer.run_bloodhound()      # pipeline.py:906
  │    ├─ White-hat Semgrep pre-scan (CWE-Top-25, security-audit, language-specific rulesets)
  │    ├─ If clean sweep → status marked COMPLETED_NO_VULN, terminates run early
  │    └─ CPU Profiling recorded on start/finish
  │
  ├─ Filter production_vulns (Contextual intelligence)  # pipeline.py:927
  │    └─ Skips vulnerability targets located in non-production paths (test, demo, benchmark, docs)
  │
  ├─ Fetch repo files structures (GraphQL / REST fallback) # pipeline.py:950
  │
  └─ 3-Cycle DEV-QA Loop (FinOps Circuit Breaker)      # pipeline.py:1004
       │
       ├─ [PHASE 2] DEV patch generation               # pipeline.py:1012
       │    ├─ Injects past QA critiques, failure context, and FILTER_REJECTION_LESSON
       │    ├─ Generates code patch using Repository Mapper structural context and dependency maps
       │    └─ Bails out early if DEV classifies findings as False Positives
       │
       ├─ [PHASE 3] QAHardcoreScorer evaluation         # pipeline.py:1043
       │    ├─ Model: qwen/qwen3.7-max
       │    ├─ Scores patches on strict code quality metrics (out of 10.0)
       │    └─ Rejection → writes qa_lesson to knowledge_base, appends critique to context, and retries
       │
       ├─ [PHASE 4] Docker Sandbox validation (Inside DEV generator)
       │
       ├─ [PHASE 5] _layer2_supreme_audit()             # pipeline.py:1082
       │    └─ Gemini checks incident dossier. Rejection marks COMPLETED_TOO_COMPLEX.
       │
       ├─ [PHASE 6] Security Disclosure Gate            # pipeline.py:1093
       │    └─ If disclosure requested by repo → writes to /app/secret_findings/ and skips PR
       │
       └─ [PHASE 7] PRManager.create_pr()               # pipeline.py:1115
            └─ Submits PR. On success status marked PR_SUBMITTED.
```

---

## 4. Adaptive Concurrency & Throttling

To prevent LLM rate limit exhaustion (HTTP 429 thundering herd) during parallel executions, the system utilizes the `AdaptiveConcurrencyManager` ([pipeline.py:214](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/orchestrator/pipeline.py#L214)):

1. **Safe Concurrency Limit**: Initial limit is parsed from the config (`config.pipeline.llm_concurrency_cap`).
2. **Dynamic Scaling on Rate Limit**: If an `LLMRateLimitError` (HTTP 429) is caught:
   - Concurrency collapses immediately down to **1** active slot.
   - Activates a cooldown period specified by `rate_limit_cooldown_sec` (defaults to 300s).
3. **Ramp-back Mechanism**: Once the cooldown timer expires, a background task gradually ramps concurrency back up by adding **1 slot every 60 seconds** until the original cap is restored.

---

## 5. PR Patrol Daemon & CI Auto-Fix Loop

The `PRPatrol` module ([patrol.py:152](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/pr/patrol.py#L152)) runs continuously to manage active contributions:

1. **Feedback Collection**: Queries open and pending PRs, pulling PR reviews, reviewer comments, and commit statuses.
2. **Comment Classification**: Feeds feedback to an LLM classifier, routing them into:
   - `CODE_FIX`: Requests to modify code implementation.
   - `QUESTION`: Queries requesting clarifications (the bot replies with a direct, professional message).
   - `CLA_RECHECK`: Requests for signing CLAs (bot triggers recheck workflow).
   - `CI_FAILURE`: System CI pipeline failures.
   - `GREETING` / `TRIVIAL`: Ignores or handles simple conversational remarks.
3. **Guardrails & Interaction Caps**:
   - **Discussion Limits**: Auto-reply replies are tracked in the database and capped at `max_discussion_replies` (default 3) per PR.
   - **CI Retry Limits**: Total CI auto-fix commits are tracked and capped at `max_ci_retries` (default 3) per PR. Exceeding either cap triggers auto-closure of the PR to prevent spam.
4. **CI Auto-Fix Cycle** ([patrol.py:1497](file:///c:/Users/USER/Documents/GitHub/Agent-Farm/farm_agent/pr/patrol.py#L1497)):
   - Parse raw logs, sanitize checks names, and isolate compiler tracebacks.
   - Use `_guess_file_from_traceback` (line 2004) to identify the buggy source file.
   - Launch LLM to draft a CI fix, mounting the workspace to the isolated Docker sandbox.
   - Auto-run local test commands. If sandbox validation passes, commit and push the fix directly.

---

## 6. Omniscient Context Engine & Subsystems

Version 4.0.0 upgrades the system's codebase understanding from superficial file scans to deep documentation and linkage maps:

1. **Documentation Discovery**:
   - In `guidelines.py`, `discover_subsystem_docs()` searches for markdown (`.md`), text (`.txt`), and reStructuredText (`.rst`) files.
   - Focuses recursively on target folders: `docs/`, `architecture/`, `wiki/`, and the root `README.md`.
   - Utilizes `asyncio.to_thread` for non-blocking disk reads.
2. **Semantic Header-Based Chunking**:
   - In `rag.py`, documentation markdown is split cleanly by headers (H1, H2, and H3).
   - Overly large sections are sub-chunked while retaining original header title context.
   - Chunks are stored in ChromaDB using a cosine metric collection, tagged with metadata (`file_path`, `folder_path`, `header_title`, `is_doc: "true"`).
3. **Subsystem Dependency Graphing**:
   - In `mapper.py`, `RepoMapper.get_module_dependencies()` constructs local call linkages.
   - Uses `ast` parsing for Python files to map package imports and external `ast.Call`/`ast.Attribute` expressions.
   - Employs optimized regex patterns for Go (`import`), Rust (`use`), and JavaScript/TypeScript to extract dependency call paths, mapping `"imports"`, `"calls"`, and `"dependents"`.

---

## 7. SQLite Schema & Persistence

Database file resides in `data/memory.db` and operates in **WAL (Write-Ahead Logging)** mode. Composite indices prevent full table scans.

### Table Schema

* **`analyzed_repos`**: Tracks repositories that have already gone through analysis.
  * Columns: `full_name` (PK), `language`, `stars`, `analyzed_at`, `findings`, `metadata`.
* **`submitted_prs`**: Tracks bot-created PRs, issues, and associated limits counters.
  * Columns: `id` (PK AUTOINCREMENT), `repo`, `pr_number`, `pr_url`, `title`, `type` (e.g. `issue_proposal` for Route B), `status`, `branch`, `fork`, `created_at`, `updated_at`, `ci_fix_attempts`, `discussion_replies`.
  * Unique Constraint: `(repo, pr_number)`.
* **`findings_cache`**: Temporary cache of detected code findings.
  * Columns: `id` (PK), `repo`, `type`, `severity`, `title`, `file_path`, `status`, `created_at`.
* **`run_log`**: Log of overall runs metrics and durations.
  * Columns: `id` (PK AUTOINCREMENT), `started_at`, `finished_at`, `repos_analyzed`, `prs_created`, `findings`, `errors`, `metadata`.
* **`pr_outcomes`**: Stores merged/closed PR states and maintainer review remarks.
  * Columns: `id` (PK AUTOINCREMENT), `repo`, `pr_number`, `pr_url`, `pr_type`, `outcome`, `feedback`, `time_to_close_hours`, `recorded_at`.
  * Unique Constraint: `(repo, pr_number)`.
* **`repo_preferences`**: Learned project contribution preferences updated dynamically from outcomes.
  * Columns: `repo` (PK), `preferred_types`, `rejected_types`, `merge_rate`, `avg_review_hours`, `notes`, `updated_at`.
* **`blacklisted_repos`**: Projects blacklisted due to hostile maintainer checks or failures.
  * Columns: `repo` (PK), `reason`, `pr_number`, `blacklisted_at`.
* **`api_usage_log`**: Tracks LLM API usage.
  * Columns: `id` (PK AUTOINCREMENT), `timestamp`, `provider`.
* **`task_schedule`**: Persistent schedule queue for tasks in the `SuperHumanLoop`.
  * Columns: `task_key` (PK), `next_run`, `updated_at`.
* **`knowledge_base`**: Stores lessons, past critiques, self-learning lessons, and **architectural context**.
  * Columns: `repo_name`, `entry_type` (e.g. `FILTER_REJECTION_LESSON`, `ARCHITECTURE_CONTEXT`), `content`, `created_at`.
  * Unique Constraint: `(repo_name, entry_type, content)`.
* **`target_repos`**: Deterministic circular target queue.
  * Columns: `repo_url` (PK), `status`, `scanned_at`, `language`, `bounty_amount`, `diamond_target`.
* **`repo_style_guides`**: Caches contributing templates, formatting, and structures.
  * Columns: `repo` (PK), `style_summary`, `contributing_md`, `pr_template`, `created_at`, `updated_at`.

### Optimization & Indices
* **`idx_api_usage`**: Composite index on `(provider, timestamp)` to optimize LLM call counts and quota checks.
* **`idx_api_usage_cleanup`**: Index on `(timestamp)` to optimize daily purge queries.

---

## 8. Directory & Module Architecture

```
.                                       # Workspace Root (v4.0.0)
├── Dockerfile                          # Stage 1 builder (wheel creation) + Stage 2 lean runtime v4.0.0
├── docker-compose.yml                  # agent-farm service definition with volumes (data/, logs/, secret_findings/)
├── start.sh                            # Unix quick start wrapper script
├── start.bat                           # Windows quick start wrapper script
│
├── farm_agent/                         # Package root (version = "4.0.0")
│   ├── __init__.py
│   │
│   ├── cli/
│   │   └── main.py                     # Click CLI — command registrations
│   │
│   ├── core/
│   │   ├── config.py                   # Pydantic v2 config and YAML loading
│   │   ├── daily_log.py                # Formats daily markdown activity logs
│   │   ├── exceptions.py               # System exception types hierarchy
│   │   ├── leaderboard.py              # Leaderboard stat collections
│   │   ├── logger.py                   # Rotating file logging system setup
│   │   ├── middleware.py               # Context middleware chain layers
│   │   ├── models.py                   # Core Pydantic data structures definitions
│   │   ├── notifier.py                 # Telegram notifications integration
│   │   ├── profiles.py                 # Thorough, quick, and standard run configurations
│   │   ├── rag.py                      # ChromaDB vector DB context loaders (with semantic markdown header chunking)
│   │   ├── retry.py                    # Retry decorators for GitHub/LLM interfaces
│   │   └── sandbox.py                  # DockerSandbox engine with Polyglot Guillotine, PoC execution context mapping
│   │
│   ├── analysis/
│   │   ├── analyzer.py                 # CodeAnalyzer (parallelized security, quality, UX scanners) & BloodhoundAnalyzer
│   │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
│   │
│   ├── generator/
│   │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
│   │   ├── poc.py                      # PoCGenerator (PoC validation & LLM evaluation)
│   │   ├── reviewer.py                 # ReviewerAgent (Self-reflective code auditor with Blast Radius checks)
│   │   └── scorer.py                   # QAHardcoreScorer (Qwen-based QA grader)
│   │
│   ├── github/
│   │   ├── client.py                   # Async-retrying GitHub REST and GraphQL Client
│   │   ├── discovery.py                # Target network search and crawler discoverers
│   │   ├── guidelines.py               # Guidelines, PR templates, and subsystem doc discovery
│   │   └── security_gate.py            # Identifies private security disclosure files
│   │
│   ├── issues/
│   │   └── solver.py                   # IssueSolver (solves issues, multi-file deep planner)
│   │
│   ├── llm/
│   │   ├── context.py                  # Generator system instruction builders
│   │   ├── models.py                   # Model registry definitions
│   │   ├── provider.py                 # OpenRouter integration handlers
│   │   └── router.py                   # Task router mapping
│   │
│   ├── orchestrator/
│   │   ├── memory.py                   # Persistence memory sqlite connection interface
│   │   ├── pipeline.py                 # Pipeline (Standard & Circular pipelines implementation)
│   │   └── human.py                    # SuperHumanLoop relentless daily scheduler
│   │
│   └── pr/
│       ├── manager.py                  # Pull Request manager (forking, branches, commits)
│       └── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
```

---

## 9. Error Handling & Fallback Matrix

| Scenario | Behavior |
|----------|----------|
| Missing runtime config file | Auto-defaults are used. Loads token from `GITHUB_TOKEN` environment variable or fallbacks to `gh auth token` CLI |
| Qwen / Gemini API failure | **Fail-Closed**: Instantiation throws error, drops the current finding, and skips generation |
| Docker Daemon offline | Sandbox functions return error, blocking PR submissions |
| Sandbox Execution Timeout | Hard timeout wrapper (`timeout --signal=KILL 60s`) terminates execution. Exit code 137. |
| Database WAL mode error | Logs warning and automatically reverts journal mode to `DELETE` |
| Primary Token Rate Limited | Swaps active auth headers to configured `secondary_tokens` list |
| GitHub API Error (502/503/429) | Backs off. Jittered retry: 5 retries, base 10s, max 120s, ±25% random jitter |
| DEV-QA Cycles fail | Marks target status as `COMPLETED_TOO_COMPLEX` to avoid loops |
| Maintainer marked Hostile | Project repository is blocked and blacklisted in `blacklisted_repos` |
| Private Disclosure target | Saved to `/app/secret_findings/{repo}.json`, skips PR creation, sends Telegram/Discord/Slack alert |

---

*Historical map: verify paths, claims, and line numbers against the current checkout before implementation.*
