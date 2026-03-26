# FINAL QA AUDIT

Date: 2026-03-26  
Workspace: `C:\Users\USER\Documents\GitHub\ContribAI`

## Scope

This audit used live GitHub and live Minimax calls.  
The mocked pytest stack was intentionally not used during this sweep because the repository map explicitly states the test stack includes `respx`.

### Evidence

Command:

```powershell
Get-Content project_map.md
```

Raw output excerpt:

```text
**Stack:** pytest + pytest-asyncio + respx (HTTP mocking) + ruff (lint/format)
```

## Environment Proof

Command:

```powershell
python --version
```

Raw output:

```text
Python 3.14.2
```

Command:

```powershell
python -m contribai.cli.main system-status
```

Exit code: `0`

Raw output excerpt:

```text
INFO     Memory initialized at C:\Users\USER\.contribai\memory.db
INFO     HTTP Request: GET https://api.github.com/rate_limit "HTTP/1.1 200 OK"
INFO     Rate limit: 5000/5000 remaining (resets at 1774508804)
🔑 GitHub API rate limit remaining: {'limit': 5000, 'used': 0, 'remaining': 5000, 'reset': 1774508804}
```

## Failure/Fix/Retest Cycle 1: Minimax Redirect + False-Green Analysis

### Failure Reproduction

Command:

```powershell
python -m contribai.cli.main analyze https://github.com/pallets/itsdangerous
```

Exit code: `0`

Raw output excerpt:

```text
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2/ "HTTP/1.1 307 Temporary Redirect"
ERROR    Analyzer code_quality failed: Minimax HTTP 307: Redirect response '307 Temporary Redirect' for url 'https://api.minimax.io/v1/text/chatcompletion_v2/'
ERROR    Analyzer ui_ux failed: Minimax HTTP 307: Redirect response '307 Temporary Redirect' for url 'https://api.minimax.io/v1/text/chatcompletion_v2/'
ERROR    Analyzer docs failed: Minimax HTTP 307: Redirect response '307 Temporary Redirect' for url 'https://api.minimax.io/v1/text/chatcompletion_v2/'
ERROR    Analyzer security failed: Minimax HTTP 307: Redirect response '307 Temporary Redirect' for url 'https://api.minimax.io/v1/text/chatcompletion_v2/'
INFO     Analysis of pallets/itsdangerous complete — 0 findings. Summary: No issues found.
│ Found 0 issues │
```

### Root Cause

- `contribai/llm/provider.py` `MinimaxProvider.__init__` + `MinimaxProvider.chat`
  The client posted to `https://api.minimax.io/v1/text/chatcompletion_v2/` with a trailing slash because it used `AsyncClient(base_url=full_endpoint)` and then `.post("")`.
- `contribai/analysis/analyzer.py` `CodeAnalyzer.analyze` + `CodeAnalyzer._run_analyzer`
  Analyzer exceptions were swallowed and converted into a fake-success `0 findings` result.

### Source Fixes Applied

- `contribai/llm/provider.py`
  - store `self._chat_url = (config.base_url or self.API_URL).rstrip("/")`
  - post directly to `self._chat_url`
  - enable `follow_redirects=True`
- `contribai/analysis/analyzer.py`
  - raise `AnalysisError` when individual analyzers fail
  - raise `AnalysisError` when all analyzers fail instead of reporting success
  - harden finding parsing so messy Minimax output does not get silently dropped

### Retest

Command:

```powershell
python -m ruff check contribai/llm/provider.py contribai/analysis/analyzer.py
python -m compileall contribai/llm/provider.py contribai/analysis/analyzer.py
python -m contribai.cli.main analyze https://github.com/pallets/itsdangerous
```

Exit codes: `0`, `0`, `0`

Raw output excerpt:

```text
All checks passed!
Compiling 'contribai/llm/provider.py'...
Compiling 'contribai/analysis/analyzer.py'...
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     Analysis of pallets/itsdangerous complete — 0 findings. Summary: No issues found.
│ Analyzed 40 files in 63.8s │
│ Found 0 issues │
```

## Failure/Fix/Retest Cycle 2: Removed Provider Class Still Imported by Pipeline

### Failure Reproduction

Command:

```powershell
python -m contribai.cli.main target https://github.com/pallets/itsdangerous --dry-run
```

Exit code: `0`

Raw output excerpt:

```text
INFO     📋 Repo guidelines: commit=default, 0 template sections
INFO     🔬 Analyzing code...
ERROR    ❌ Single-repo run failed for pallets/itsdangerous: cannot import name 'MultiModelProvider' from 'contribai.llm.provider' (C:\Users\USER\Documents\GitHub\ContribAI\contribai\llm\provider.py)
❌ Errors: 1
```

### Root Cause

- `contribai/orchestrator/pipeline.py` `ContribPipeline._set_task`
  The pipeline still hard-imported `MultiModelProvider` even though only the Minimax provider remains.

### Source Fix Applied

- `contribai/orchestrator/pipeline.py`
  - removed the stale import
  - switched `_set_task` to capability detection: `hasattr(self._llm, "set_task")`

### Retest

Command:

```powershell
python -m ruff check contribai/orchestrator/pipeline.py contribai/analysis/analyzer.py contribai/llm/provider.py
python -m compileall contribai/orchestrator/pipeline.py contribai/analysis/analyzer.py contribai/llm/provider.py
python -m contribai.cli.main target https://github.com/pallets/itsdangerous --dry-run
```

Exit codes: `0`, `0`, `0`

Raw output excerpt:

```text
All checks passed!
Compiling 'contribai/orchestrator/pipeline.py'...
INFO     ▶ Starting single-repo run: pallets/itsdangerous (dry_run=True)
INFO     📦 Processing: pallets/itsdangerous
INFO     Repo guidelines: commit=default, pr_title=default, scopes=any, sections=0
INFO     🔬 Analyzing code...
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     HTTP Request: POST https://api.minimax.io/v1/text/chatcompletion_v2 "HTTP/1.1 200 OK"
INFO     Analysis of pallets/itsdangerous complete — 0 findings. Summary: No issues found.
INFO     No findings for pallets/itsdangerous
INFO     ✅ Single-repo run completed: pallets/itsdangerous — findings=0, PRs=0
│ 📦 Repos analyzed: 1 │
│ 🔍 Issues found: 0 │
│ 🛠️  Contributions generated: 0 │
│ 📤 PRs created: 0 │
```

## Failure/Fix/Retest Cycle 3: Generator Repo Preference Lookup + Output Parsing + Self-Review Blindness

### Failure Reproduction A: wrong `RepoContext` attribute

Command executed: live inline Python calling `ContributionGenerator.generate(...)` against `pallets/itsdangerous` and `src/itsdangerous/exc.py`.

Raw output excerpt:

```text
DEBUG:contribai.generator.engine:Could not fetch repo preferences: 'RepoContext' object has no attribute 'full_name'
WARNING:contribai.generator.engine:No valid changes parsed for finding: Clarify BadPayload error propagation
GENERATOR_RESULT=None
```

### Failure Reproduction B: self-review rejected because it never saw the changed part of the file

Command executed: live inline Python that built the same contribution and printed the raw self-review verdict.

Exit code: `0`

Raw output excerpt:

```text
The title says "Clarify BadPayload error propagation" but looking at the actual code changes, I don't see any `BadPayload` class in the file.
...
**REJECT**
...
The diff appears incomplete or missing the relevant `BadPayload` changes.
```

### Root Causes

- `contribai/generator/engine.py` `ContributionGenerator._get_repo_preferences`
  used `context.full_name` instead of `context.repo.full_name`.
- `contribai/generator/engine.py` `ContributionGenerator._parse_changes`
  was too brittle for live Minimax responses that contain reasoning text, fences, or YAML-ish payloads.
- `contribai/generator/engine.py` `ContributionGenerator._self_review`
  reviewed `change.new_content[:2000]`, which hid late-file edits like `BadPayload` in `exc.py` and created false rejections.
- `contribai/llm/context.py` `build_generator_system_prompt` and `contribai/generator/engine.py` `_build_generation_prompt`
  did not strongly forbid prose / `<think>` output for machine-readable generation.

### Source Fixes Applied

- `contribai/generator/engine.py`
  - `_get_repo_preferences`: use `context.repo.full_name`
  - `_parse_changes`: strip `<think>...</think>`, accept JSON or YAML-ish payloads, normalize paths
  - `_parse_changes`: preserve `original_content` on modified files
  - `_self_review`: include finding description and review a unified diff instead of the first 2,000 file characters
  - `_build_review_snippet`: added diff-focused review context
- `contribai/llm/context.py`
  - generator system prompt now explicitly requires only machine-readable output, with no prose / markdown / `<think>` tags
- `contribai/generator/engine.py`
  - generation prompt now explicitly requires only JSON, no prose or markdown fences

### Retest A: parser can now extract a real change

Command executed: live inline Python calling `_agentic_generate(...)` then `_parse_changes(...)` against `pallets/itsdangerous`.

Exit code: `0`

Raw output:

```text
CHANGE_COUNT=1
CHANGE_PATH=src/itsdangerous/exc.py
NEW_CONTENT_DELTA=44
```

### Retest B: full generator now returns a contribution object

Command executed: live inline Python calling `ContributionGenerator.generate(...)` against `pallets/itsdangerous`.

Exit code: `0`

Raw output:

```text
GENERATOR_RESULT=ok
FILES_CHANGED=1
COMMIT_MESSAGE=refactor(itsdangerous): clarify badpayload error propagation

Improve exception context while preserving existing behavior.

Affected files: exc.py
BRANCH=contribai/improve/quality/clarify-badpayload-error-propagation
```

## Additional Live Runtime Verification

### Issue Solver Surface

Command:

```powershell
python -m contribai.cli.main solve https://github.com/pallets/itsdangerous --dry-run --max-issues 3
```

Exit code: `0`

Raw output:

```text
INFO     HTTP Request: GET https://api.github.com/repos/pallets/itsdangerous "HTTP/1.1 200 OK"
INFO     HTTP Request: GET https://api.github.com/repos/pallets/itsdangerous/issues?state=open&per_page=20 "HTTP/1.1 200 OK"
Found 1 open issues
1 are solvable
│ 389 │ bug │ serializer_kwargs are missing in load_pa │ - │
```

### Patrol Surface

Command:

```powershell
python -m contribai.cli.main patrol --dry-run
```

Exit code: `0`

Raw output:

```text
INFO     Memory initialized at C:\Users\USER\.contribai\memory.db
INFO     Using LLM provider: minimax (model: MiniMax-M2.7)
No open PRs found in database.
```

### Web Server + API Surface

Command:

```powershell
$job = Start-Process -FilePath python -ArgumentList '-m','contribai.cli.main','serve','--host','127.0.0.1','--port','8791' -PassThru -WindowStyle Hidden; Start-Sleep -Seconds 6; try { $health = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8791/api/health'; $stats = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8791/api/stats'; $logs = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8791/api/logs/today?lines=5'; Write-Output "HEALTH_STATUS=$($health.StatusCode)"; Write-Output $health.Content; Write-Output "STATS_STATUS=$($stats.StatusCode)"; Write-Output $stats.Content; Write-Output "LOGS_STATUS=$($logs.StatusCode)"; Write-Output $logs.Content } finally { if ($job -and !$job.HasExited) { Stop-Process -Id $job.Id -Force }; Start-Sleep -Seconds 1 }
```

Exit code: `0`

Raw output:

```text
HEALTH_STATUS=200
{"status":"ok","version":"2.5.0"}
STATS_STATUS=200
{"total_repos_analyzed":1,"total_prs_submitted":0,"prs_merged":0,"total_runs":2}
LOGS_STATUS=200
{"lines":["2026-03-26 13:22:25 | INFO     | provider | Using LLM provider: minimax (model: MiniMax-M2.7)","2026-03-26 13:22:47 | INFO     | logger | Daily rolling logger initialized → logs\\contribai_2026-03-26.log (level=INFO, keep=30 days)","2026-03-26 13:22:48 | INFO     | memory | Memory initialized at C:\\Users\\USER\\.contribai\\memory.db","2026-03-26 13:22:48 | INFO     | auth | API key auth disabled (no keys configured)","2026-03-26 13:22:48 | INFO     | server | Dashboard API started"],"total_lines":1657,"showing":5,"file":"logs\\contribai_2026-03-26.log"}
```

### User-Facing Stats / Status Commands

Commands:

```powershell
python -m contribai.cli.main stats
python -m contribai.cli.main status
```

Exit codes: `0`, `0`

Raw output:

```text
┌─────────────────────────── ContribAI Statistics ────────────────────────────┐
│ 📊 Total Runs: 2                                                            │
│ 🔬 Repos Analyzed: 1                                                        │
│ 📤 PRs Submitted: 0                                                         │
│ ✅ PRs Merged: 0                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
No PRs found.
```

## Final Modified Source Files

- `contribai/llm/provider.py`
- `contribai/analysis/analyzer.py`
- `contribai/orchestrator/pipeline.py`
- `contribai/generator/engine.py`
- `contribai/llm/context.py`

## Final State

The live sweep ended with:

- live GitHub API calls succeeding
- live Minimax calls succeeding at `https://api.minimax.io/v1/text/chatcompletion_v2`
- `analyze` succeeding without redirect failures
- `target --dry-run` succeeding without stale provider imports
- generator parsing and full contribution generation succeeding
- issue solver, patrol, web server, stats, and status commands all returning exit code `0`

No claim above is based on theory; every claim is backed by the raw terminal outputs included in this file.
