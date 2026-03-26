# AUTO_HEALING_AUDIT

## Verdict

`CI Auto-Healing` was **not proven in reality** on `https://github.com/hieuit095/gitvisualizer-ai` during this crucible.

As of **March 26, 2026**, the live target repository had:

- **0 GitHub Actions workflows**
- **no `.github/workflows` entries in the default branch tree**
- **no check runs on the existing open PR heads**

Because of that, there was no real GitHub Actions failure log for `PRPatrol` to download with `download_check_run_log()`.

I still executed multiple live targeted runs, fixed several real `ContribAI` core bugs exposed by those runs, and captured the exact blockers below.

## Exact Commands Executed

```powershell
.\venv\Scripts\python.exe -m pytest tests\unit\test_superhuman.py -q
.\venv\Scripts\python.exe -m pytest tests\unit\test_pipeline_v2.py -q
.\venv\Scripts\python.exe -m pytest tests\unit\test_generator.py -q
```

```powershell
.\venv\Scripts\python.exe -m contribai.cli.main -c logs/config.auto_healing.yaml superhuman --target-repo https://github.com/hieuit095/gitvisualizer-ai --time-warp
```

I executed that live `superhuman` command repeatedly with isolated state, capturing stdout/stderr into:

- `logs/auto_healing_run1.out`
- `logs/auto_healing_run2.out`
- `logs/auto_healing_run3.out`
- `logs/auto_healing_run4.out`

I also queried the live GitHub API directly with inline Python/httpx scripts to verify workflows, PRs, and commit status.

## Live GitHub State

### Raw API proof: no GitHub Actions workflow surface

Command result:

```text
WORKFLOWS=
{
  "total_count": 0,
  "workflows": []
}
WORKFLOW_PATHS=
[]
```

### Raw API proof: existing open PRs before the crucible

```text
OPEN_PRS=
[
  {
    "number": 12,
    "title": "🔒 Security: CORS allows wildcard origin when ALLOWED_ORIGINS is not configured",
    "sha": "0a47f253f3dad14c762c8c01c9b8ef48ee7fb514"
  },
  {
    "number": 11,
    "title": "🎨 UI/UX: App-level loading state is a plain spinner with no context",
    "sha": "b9b33aaa4d1953d9a3a76a90d3b30dcf5fa59aee"
  },
  {
    "number": 10,
    "title": "🎨 UI/UX: Interactive graph nodes lack keyboard navigation and accessibility attributes",
    "sha": "832f0683ca13d21ab0ae55560cc0e0f2f3756937"
  }
]
```

### Raw API proof: only Vercel status on `main`, not failing GitHub Actions jobs

```text
MAIN_STATUS=
{
  "state": "success",
  "statuses": [
    {
      "state": "success",
      "description": "Deployment has completed",
      "context": "Vercel",
      "created_at": "2026-03-14T17:12:34Z",
      "updated_at": "2026-03-14T17:12:34Z"
    }
  ]
}
```

## Live Run Chronology

### Run 1: fresh targeted hunt, but duplicate filter prevented any PR

Raw terminal excerpts from `logs/auto_healing_run1.out`:

```text
366:                    INFO     No new findings after duplicate filter
367:                    INFO     ✅ Single-repo run completed:
369:                    INFO     Controlled hunt produced no PRs, retrying target
703:                    INFO     No new findings after duplicate filter
704:                    INFO     ✅ Single-repo run completed:
706:                    INFO     Controlled hunt produced no PRs, retrying target
1041:                   INFO     No new findings after duplicate filter
1042:                   INFO     ✅ Single-repo run completed:
```

### Fixes applied after Run 1

- `contribai/orchestrator/pipeline.py`
  - added `allow_duplicate_prs` to `run_single()` / `_process_repo()`
  - changed failed-CI handling to leave PRs open for Patrol instead of auto-closing
  - return immediately when GitHub reports `total == 0` check runs
- `contribai/orchestrator/human.py`
  - targeted crucible hunts now call `run_single(..., allow_duplicate_prs=True)`

### Run 2: duplicate bypass worked, but generation could not apply a multi-file fix

Raw terminal excerpts from `logs/auto_healing_run2.out`:

```text
362:                    INFO     Controlled run: preserving 1 finding(s) despite
363:                             existing PR history
373:                    INFO     🛠️ Generating fix for: GitHub Personal Access Token
378:                    INFO     Edits for src/lib/githubToken.ts: 1/1 applied
379:                    WARNING  No original content for server/router.ts (finding
380:                             file not fetched), skipping edits
384:                    INFO     Self-review rejected: **REJECT**
389:                             The approach of moving token storage server-side
390:                             is conceptually sound, but the fix is
391:                             **incomplete**
393:                    WARNING  Self-review failed for: GitHub Personal Access
395:                    INFO     ✅ Single-repo run completed:
396:                             hieuit095/gitvisualizer-ai — findings=8, PRs=0
```

### Fix applied after Run 2

- `contribai/orchestrator/pipeline.py`
  - passed `github_client=self._github` into `ContributionGenerator.generate()` so live generation could use repo reads

### Run 3: generator could read more files, but parser still dropped multi-file edits

Raw terminal excerpts from `logs/auto_healing_run3.out`:

```text
724:                    INFO     🛠️ Generating fix for: GitHub PAT stored in
726:                    INFO     HTTP Request: GET
727:                             https://api.github.com/repos/hieuit095/gitvisualizer-ai/contents/api/[...path].ts "HTTP/1.1 200 OK"
1036:                   INFO     Edits for src/lib/githubToken.ts: 1/1 applied
1037:                   WARNING  No original content for api/[...path].ts (finding
1041:                   WARNING  No original content for
1042:                            server/controllers/analyze-repo.ts (finding file
1047:                   WARNING  No original content for
1048:                            server/controllers/summarize-node.ts (finding file
1053:                   WARNING  No original content for
1054:                            server/controllers/embed-chunks.ts (finding file
1059:                   WARNING  No original content for
1060:                            server/controllers/chat-repo.ts (finding file not
1068:                   INFO     Self-review rejected: **REJECT**
1072:                            1. **Broken functionality**: The fix makes
1073:                            `getStoredToken()` always return an empty string
1076:                   WARNING  Self-review failed for: GitHub PAT stored in
1078:                   INFO     ✅ Single-repo run completed:
1079:                            hieuit095/gitvisualizer-ai — findings=4, PRs=0
1080:                   INFO     Controlled hunt produced no PRs, retrying target
```

### Fix applied after Run 3

- `contribai/generator/engine.py`
  - cached project-map file fetches back into `context.relevant_files`
  - cached successful `read_file` tool results back into `context.relevant_files`

### Run 4: parser-side cache bug fixed, but self-review still rejected the generated change before PR creation

Raw terminal excerpts from `logs/auto_healing_run4.out`:

```text
355:                    INFO     Controlled run: preserving 1 finding(s) despite
359:                    INFO     🛠️ Generating fix for: Untitled finding
673:                    INFO     Self-review rejected: **REJECT**
677:                             1. **Incomplete diff**: The diff appears truncated
678:                             - the environment variables table ends abruptly
681:                    WARNING  Self-review failed for: Untitled finding
682:                    INFO     ✅ Single-repo run completed:
683:                             hieuit095/gitvisualizer-ai — findings=2, PRs=0
684:                    INFO     Controlled hunt produced no PRs, retrying target
```

## Why `download_check_run_log()` Was Never Reached

The requested CI-heal proof requires this chain:

1. open a live PR
2. observe a real failed GitHub Actions check run
3. call `download_check_run_log()`
4. extract traceback
5. generate and push healing commit

That chain never became reachable here because:

- the target repo had **no GitHub Actions workflows**
- the live runs never created a new PR after repeated self-review failures
- therefore there was **no failed check run ID**
- therefore `download_check_run_log()` had nothing real to download

## Live PR URL Proof

There is **no new PR URL from this auto-healing crucible**.

That is the honest result. Existing open PRs on the target repo at test time were:

- `https://github.com/hieuit095/gitvisualizer-ai/pull/10`
- `https://github.com/hieuit095/gitvisualizer-ai/pull/11`
- `https://github.com/hieuit095/gitvisualizer-ai/pull/12`

None of those were created by this CI auto-healing crucible, and none provided a failing GitHub Actions log surface.

## Core Files Fixed During This Crucible

- `contribai/orchestrator/human.py`
  - targeted hunt now explicitly bypasses duplicate-history filtering for controlled repo tests
- `contribai/orchestrator/pipeline.py`
  - added `allow_duplicate_prs`
  - passed `github_client` into generation
  - changed failed-CI handling to leave PRs open for Patrol
  - short-circuits immediately when a PR has zero check runs
- `contribai/generator/engine.py`
  - caches project-map and tool-read file contents into `context.relevant_files`
- `tests/unit/test_superhuman.py`
  - updated targeted-hunt expectations
- `tests/unit/test_pipeline_v2.py`
  - added regression tests for failed CI handling, zero-check behavior, and generator wiring
- `tests/unit/test_generator.py`
  - added regression tests for caching fetched file contents into context

## Verification

The following targeted suites passed after the fixes:

```text
tests/unit/test_pipeline_v2.py  -> 19 passed
tests/unit/test_generator.py    -> 20 passed
tests/unit/test_superhuman.py   -> 12 passed
```

## Final Assessment

I executed the requested live crucible, but I cannot honestly claim `CI Auto-Healing works in reality` on this target repository today.

What I found was insufficient because the live target state on **March 26, 2026** does not match the test premise:

- no GitHub Actions workflows
- no check-run log surface
- no fresh PR successfully created during this crucible

The codebase is in a better position for the next attempt, but a true proof now requires a target repo that actually exposes a failing GitHub Actions job and lets the bot get a PR onto that failing branch.
