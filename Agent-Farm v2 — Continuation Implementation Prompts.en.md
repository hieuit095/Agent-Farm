# Agent-Farm v2 — Continuation Implementation Prompts

**Purpose:** Execute the verified upgrade roadmap from the current, unfinished checkout. This is an ordered set of prompts for a coding agent and its independent reviewer. It is an implementation contract, not evidence that later milestones are complete.

## Read this handoff first

Read, in order, `Agent-Farm v2 — Verified Upgrade Roadmap.md`, `Agent-Farm v2 — High-Precision Autonomous Bug Bounty Architecture Improvement Plan.md`, `PROJECT_MAP.md`, the relevant source, tests, and `git status`/`git diff`. The verified roadmap's M0–M6 acceptance gates take precedence over the original plan's aspirational 22 phase ordering. Resolve any disagreement by inspecting current code and recording the decision. Never treat an old line number, an old map entry, a document claim, or a prior test result as current proof.

At the 2026-09-25 handoff, `HEAD` was `44f537f` (M2 phase 4). Recheck it; this snapshot may be stale. M0 and M1 are recorded as implemented. Committed M2 slices cover exact scope and request budget, scan threat assumptions and coverage, live semantic HTTP oracles, and hashed canonical artifacts with a read-only Docker mount. At handoff, the **uncommitted** M2 operator flow changed `farm_agent/cli/main.py`, `farm_agent/core/config.py`, `farm_agent/orchestrator/memory.py`, `farm_agent/orchestrator/pipeline.py`, and `tests/integration/test_m2_oracles_real.py`. The two source plan documents and `Plan-update.txt` were also untracked. Preserve user changes. The first implementation job is to review and finish this M2 slice; M2 has not been accepted. A previous focused M2 run returned 16 passes, and a previous full run returned 124 passes with an existing `AsyncMock` warning. These are historical observations, not a substitute for a new run.

## Rules for every prompt

1. Work on **one bounded slice at a time**. Read every caller and sink affected by the slice. State the base SHA, dirty files, intended files, entry points, data flow, security invariant, and acceptance tests before editing. Keep unrelated changes intact.
2. Use real source, a real SQLite database, real process boundaries, real loopback HTTP services, and Docker where a claim depends on them. A controlled vulnerable/fixed corpus is valid test infrastructure when requests, side effects, and oracles actually execute. A mock, stub, monkeypatch, fabricated response, in-memory substitute, or hard-coded expected result cannot be used as proof of a security gate, scope enforcement, exploit, patch success, cost, recall, or publication behavior. Mocks may support narrow unit parsing tests only; label them as such.
3. Do not claim a milestone complete because code compiles, a model says so, a self-score is high, or tests were skipped. Run the acceptance tests yourself and report command, exit status, pass/fail/skip counts, environment, and any uncovered path. A skipped Docker or network test is **unverified**, not passed. Separate pre-existing failures from new regressions with a baseline.
4. Keep `DISCOVERED`, `INVESTIGATING`, `CONFIRMED`, `RULED_OUT`, `OPEN_PROOF_GAP`, and `NEEDS_MANUAL_REVIEW` semantically distinct. Scanner, source, dependency, transport, model, Docker, or PoC failures never mean safe, false positive, or clean. A real negative needs counterevidence. Preserve exact repo, scan, candidate, target SHA, scope, oracle digest, and evidence bindings across retries and restarts.
5. No patch generation, PR, issue, advisory, report publication, or patrol security edit may bypass its independent gate. The patch worker cannot decide vulnerability truth or verify its own patch. Neither JEV nor an LLM can set final security closure, exploit success, severity, or publication eligibility. Preserve nonsecurity flows while guarding every security sink.
6. Live probing requires an operator supplied authorization record, exact target and origin scope, allowed role/impact, excluded endpoint enforcement, finite request budget, and the global switch. Use loopback services for automated integration tests. Never run probes against an outside target, call a paid API, publish externally, or expose credentials as a shortcut to a test result.
7. Do not create fake metrics, screenshots, logs, scan IDs, proof hashes, HTTP responses, provider usage, PR URLs, or benchmarks. If a prerequisite is missing, record the exact blocker and keep the state open. Never mark a task done by adding only a TODO, interface, empty module, ignored test, or plausible report.
8. Reconcile `PROJECT_MAP.md` only with verified current paths and outcomes. Its older generated inventory is explicitly historical. After each accepted slice, review `git diff --check`, the relevant tests, changed-file lint, and `git status`; record remaining risk. Do not bundle an unreviewed slice into the next one.

## Operating procedure for every coding session

Follow these instructions literally. Run commands from the repository root in PowerShell on Windows; adapt only the shell syntax on another OS. Replace an example path or symbol only after confirming its current location with `rg --files` or `rg -n`. Paths under `farm_agent/security/` and `tests/integration/` named below exist at handoff. Any new module named by the roadmap is **planned, not present** until verified on disk.

1. **Orient.** Run `git rev-parse HEAD`, `git status --short`, `git diff --stat`, and `git diff --check`. Read the roadmap milestone, the relevant source, its callers, and existing tests. List pre-existing edits separately from the files you will touch. Do not use `git reset`, `git clean`, `git checkout --`, or a broad formatter on a dirty checkout.
2. **Write a slice contract before editing.** State one observable behavior, its security invariant, exact files, existing helper to reuse, negative cases, and a test that would fail without the change. Name the *next* slice separately. If the proposed file or API is absent, verify that fact; do not invent an import and proceed.
3. **Implement the smallest complete vertical slice.** Change the shared boundary that all relevant callers use. Add the necessary real test, then run it. Keep security decisions in the state/verification boundary, not in CLI formatting or model prose. Do not silently weaken an acceptance criterion to make a test pass.
4. **Verify and inspect.** Record the literal command, working directory, exit code, pass/fail/skip count, and meaningful output. Use a unique test temp directory under the workspace and delete only that verified directory when done. If Windows read-only oracle artifacts prevent deletion, clear their read-only bit only inside that temp directory. Compare lint for changed lines against `HEAD` or a saved pre-edit result; compare whole-repo Ruff totals only with the same command, Ruff version, scope, and counting method. A pre-existing warning or failure must be identified by evidence, not assumption.
5. **Review independently.** Read `git diff` line by line and trace the security sink again. If a separate reviewer is available, give it the diff and acceptance criteria; otherwise perform a distinct reviewer pass and say so. Update `PROJECT_MAP.md` only after verification. Emit the required `IMPLEMENTATION REPORT`; do not advance on `FAIL` or `BLOCKED`.

**Evidence levels:** A unit test of parsing proves parsing. A local HTTP/SQLite integration test proves the tested local path. A Docker test proves the tested container boundary. A contract test against a local protocol server proves adapter behavior, not availability or billing of an external provider. A successful external action requires its actual remote result. Label every claim at the level its evidence supports.

## Prompt 0 — Establish the truthful starting point

**Role and boundary:** Audit only. Do not change product code, tests, the prompt document, or `PROJECT_MAP.md` during this prompt. A report is the deliverable. `Plan-update.txt` is user context, not an implementation authority. If an earlier AI IDE audit is supplied, check its claims against the actual checkout; do not inherit its gate verdict.

**Do this, in order:**

1. From the repository root run `git rev-parse HEAD`, `git status --short`, `git diff --stat`, `git diff --check`, and `git log -8 --oneline`. Save the literal output in your report. List every modified and untracked file with its likely role. Use `git diff -- <path>` for each dirty tracked file; read the untracked documents separately. Never count an untracked document as a committed implementation.
2. Read `docs/m0-baseline.md`, the M0–M2 rows of the verified roadmap, and the current top of `PROJECT_MAP.md`. Verify paths with `rg --files farm_agent tests docs`. Trace CLI entry points in `farm_agent/cli/main.py`; `run_circular`, `_process_repo`, and `_process_repo_impl` in `farm_agent/orchestrator/pipeline.py`; candidate and evidence persistence in `farm_agent/orchestrator/memory.py`; closure in `farm_agent/security/closure.py`; PoC execution in `farm_agent/generator/poc.py`; scope, transport, oracle, verifier, coverage, and artifact modules in `farm_agent/security/`; and outbound sinks in `farm_agent/pr/manager.py`, `farm_agent/github/security_gate.py`, and `farm_agent/pr/patrol.py`. For each flow, name the actual caller, callee, state transition, and publication guard. Check nonsecurity issue paths separately.
3. Establish a fresh baseline. In PowerShell, set `$m2Temp = Join-Path (Get-Location) '.pytest-p0-m2'` and run `python -m pytest -q tests/integration/test_m2_oracles_real.py tests/integration/test_m2_coverage_real.py tests/integration/test_m2_scope_real.py --basetemp $m2Temp --tb=short -rs`. Set a different `$fullTemp = Join-Path (Get-Location) '.pytest-p0-full'` and run `python -m pytest -q --basetemp $fullTemp --tb=short -rs`. Run `python -m pytest -q tests/integration/test_m2_artifact_docker_real.py --basetemp (Join-Path (Get-Location) '.pytest-p0-docker') -rs` if Docker is available; if unavailable, record the exact error and mark this gate unverified. Record Python, pytest, Ruff, and Docker versions where used.
4. Run `python -m ruff check farm_agent/cli/main.py farm_agent/core/config.py farm_agent/orchestrator/memory.py farm_agent/orchestrator/pipeline.py tests/integration/test_m2_oracles_real.py --output-format concise` and `python -m ruff check . --output-format concise`. Preserve their exit codes. For each finding on a changed file, use `git diff --unified=0 -- <path>` to determine whether the offending line is new or pre-existing. Compare the whole-repo result with the 707-error M0 baseline only if Ruff version, command, output format, counting method, and scope match; otherwise say comparison is inconclusive.
5. Confirm the audit did not change tracked files: run `git status --short` again and compare it with step 1. Delete only the three known temp directories after checking their resolved absolute paths stay inside this workspace. Do not delete any earlier temp directory whose owner is unknown.

**Deliver:** An evidence table with columns `Requirement | Current source path/symbol | Test or direct observation | Result | Gap`. Include a separate table for each dirty file: `Pre-existing change | Purpose | Risk | Test coverage | Owner`. List every contradiction with a source citation. Record the literal commands and counts; do not substitute `<tmp>` or abbreviated test names in the final report. State whether `SemanticVerifier` is invoked by the automatic hunt paths or only by an operator path. State what a successful test does and does not prove.

**Gate:** `PASS` means the dirty M2 slice, observed regressions, skip reasons, and each file's ownership are understood and the baseline is reproducible. `PASS` does **not** accept M2. New lint on the dirty slice and uncovered negative cases must become named Prompt 1 work items. If a required command fails, classify the exact failure and use `FAIL` or `BLOCKED`; do not call the audit complete through inference.

## Prompt 1 — Finish and audit the M2 operator workflow

**Role and boundary:** Finish the existing uncommitted operator CLI slice. Do not begin M3, provider migration, or a CommandCode patch worker. Start from Prompt 0's recorded dirty state and resolve its concrete findings. The immediate known new lint error is `E501` in `tests/integration/test_m2_oracles_real.py` near line 442; recheck the line because it may move.

**Where to work:** CLI commands and output in `farm_agent/cli/main.py`; switches and storage path in `farm_agent/core/config.py`; durable lookup/transactions in `farm_agent/orchestrator/memory.py`; live manifest selection in `farm_agent/orchestrator/pipeline.py`; existing scope and verification rules in `farm_agent/security/scope.py`, `transport.py`, `artifacts.py`, `oracles.py`, and `verifier.py`; real tests in `tests/integration/test_m2_oracles_real.py` and `test_m2_scope_real.py`. Read these first. Prefer fixing an invariant in its security module over duplicating it in six CLI commands.

**Do this, in order:**

1. Run `python -m farm_agent.cli.main --help` and each new command's `--help`. Trace `register-live-scan → store_scan_manifest/store_threat_model/initialize_coverage`, `register-candidate → create_security_candidate`, `register-oracle → ArtifactStore.save`, `verify-candidate → SemanticVerifier.verify_candidate`, and `scope-report/security-candidates → Memory` reads. Record stdout, stderr, exit code, and persisted rows for a real local invocation. Confirm the global switch defaults off and exact `ProgramScope.allow_live_testing` is required.
2. Add one end-to-end test path using separate CLI subprocesses, a real temporary SQLite file, and running vulnerable/fixed loopback HTTP services. Use distinct owner and attacker credentials and a specific cross-tenant object. Register the scan, candidate, and canonical oracle; run proof; restart the process; read candidate, evidence, and coverage from SQLite and CLI. Assert `CONFIRMED` only when the owner baseline and malicious cross-tenant result prove the same object. Keep test secrets out of printed output.
3. Add focused negative cases at the same boundary: disabled global switch, no matching program/SHA, `allow_live_testing=False`, excluded path, outside origin, wrong role or impact, exhausted four-request budget, changed artifact bytes, missing witness for SSRF/command injection, transport error, and HTTP 200 without the expected tenant object. Check nonzero CLI exit, unchanged or explicitly open candidate state, no semantic proof, no publication eligibility, and correct coverage. Test a repeated verification and a restart; do not silently consume budget or overwrite a prior outcome without an explicit rule.
4. Test a mixed program registry: when the global live switch is on but one exact program forbids live testing, `_process_repo_impl` must record a controlled scope/proof-gap outcome and must not turn that scan into a clean result or leak a raw validation crash. Add the regression test before the fix. Validate candidate file paths as repository-relative POSIX paths, including rejecting Windows drive syntax; preserve existing valid paths.
5. Review each new line and fix the new `E501`. Run focused M2 integration tests, the full suite, the Docker artifact test when available, changed-line lint, `git diff --check`, and a final `git status`. Update only verified M2 claims in `PROJECT_MAP.md`.

**Gate:** The operator workflow passes only if both positive and negative cases are observed with real process/HTTP/SQLite boundaries and no new lint or source regression. Record Docker separately. This prompt accepts the **CLI slice**, not all M2 proof integrity or automatic pipeline integration. Prompt 2 owns those remaining checks. Do not claim that a fixed loopback service proves Agent-Farm produced a real patch.

## Prompt 2 — Close the M2 integration and proof integrity gaps

**Role and boundary:** Complete M2's proof and integration review before M3. Work in small sub-slices: proof record, lifecycle/contradiction policy, then automatic hunt handoff. Mark M2 incomplete until all sub-slices pass. An operator-only verifier is a current integration gap, not evidence that automatic publication is impossible under every possible operator action.

**Where to work:** `farm_agent/security/oracles.py`, `verifier.py`, `transport.py`, `scope.py`, `artifacts.py`, `coverage.py`, `closure.py`, `state.py`, and `farm_agent/orchestrator/memory.py`. Trace consumers in `farm_agent/orchestrator/pipeline.py`, `farm_agent/pr/manager.py`, and `farm_agent/github/security_gate.py`. Add real tests under `tests/integration/`; reuse current loopback services and Docker harness. Before creating a new table or module, inspect the existing SQLite schema and migrations in `memory.py`.

**Do this, in order:**

1. Draw the observed chain `request budget → four HTTP observations → deterministic verdict → canonical artifact hash → persisted evidence → candidate closure → publication gate`. For each edge, identify the exact repo/SHA, scan ID, candidate ID, role, object, surface, risk class, and oracle digest checked by code. Identify missing bindings with a reproducing test.
2. Verify that `benign_before`, `malicious_before`, `malicious_after`, and `benign_after` run in that order against **identified** before/after deployments. Persist enough redacted request/response observations and deployment/proof metadata to independently inspect or replay the claim. A hash by itself is an integrity pointer, not a retrievable proof. Never store bearer tokens or sensitive response bodies unredacted. Confirm a fixed service is not misrepresented as an Agent-Farm patch.
3. Run real negative integration cases: modified oracle during execution, forged digest, wrong repo/SHA, outside origin or redirect, identical IDOR roles, empty HTTP 200, transport failure, partial four-step completion, concurrent request-budget consumption, and restart during a proof. Inspect SQLite after each failure. `NOT_TRIGGERED` needs a valid negative observation; execution problems become `OPEN_PROOF_GAP` or inconclusive coverage.
4. Decide and implement a durable contradiction policy. A later failed or contradictory run must not leave a stale semantic proof usable for publication. Check `security_candidate_has_semantic_proof` and closing evidence ownership in `memory.py`; prove one candidate cannot borrow another candidate's evidence. Keep vulnerability confirmation separate from patch success, regression, and publication permission.
5. Trace automatic `run_circular → _process_repo → _process_repo_impl` to publication. Provide a controlled handoff to the independent semantic verifier or an explicit pending-operator state; do not bypass the semantic proof requirement. Test both hunt paths and every security sink. Review the final diff independently, rerun focused/full/Docker tests and lint, then update `PROJECT_MAP.md` with precise scope.

**Gate:** M2 passes only when the roadmap's scope and semantic-proof criteria hold across the relevant runtime path, canonical artifacts remain protected, contradictory or stale evidence cannot authorize publication, and coverage truth survives restart. If a binding or replayability issue remains, report `FAIL` or `BLOCKED` and stop before M3.

## Prompt 3 — M3 candidate recall and root-cause discipline

**Task:** After M2 acceptance, remove investigation caps that discard candidates, including the `validated_findings[:2]` path and any file-level suppression of distinct vulnerabilities. Keep a separate bounded publication/rate policy. Add root-cause-aware deduplication keyed by actor, resource, source/control/sink, code location and target SHA; merge evidence from multiple sensors without merging unrelated bugs in one file. Ensure concurrent workers cannot publish or persist duplicate closure for the same root cause. Then add independent discovery lanes in small slices: route/API inventory and authorization matrix first; cross-file source-to-sink traces next; secret, SCA, and IaC lanes only where inputs and deterministic tools are available. Semgrep is one sensor, not a prerequisite for other lanes.

**Required evidence:** Run Agent-Farm, not only corpus helper functions, against pinned vulnerable/fixed fixtures. Include two distinct flaws in one file, two sensors for one flaw, a clean repo, scanner timeout, missing dependency, and a multi-file path. Report candidate counts through every gate, recall and precision by class with denominators, and open coverage. Failed sensors remain visible and never become clean results.

**Gate:** No distinct same-file candidate is lost; duplicate root causes converge with retained evidence; the controlled corpus shows recall improvement without violating the safety invariants. Do not claim a numeric precision target on an unrepresentative corpus.

## Prompt 4 — M4 provider adapter and bounded JEV routing

**Task:** Verify current official CommandCode Provider API and JEV contracts at implementation time; the roadmap's 2026-09-25 model IDs, pricing, endpoints, and CLI behavior may have changed. Implement one `httpx` provider adapter with explicit supported-endpoint discovery, timeout, retry policy, response schema validation, usage capture, and typed failure. Route generative DeepSeek calls to the supported chat endpoint and JEV only to the supported System One endpoint. Feed JEV minimal, redacted candidate state and bounded `choice`, `noul`, or `score` questions. Use deterministic routing where sufficient; JEV failure must fall back to a safe, auditable path. Remove hard-coded provider/model choices from pipeline call sites through existing configuration. Preserve current provider operation until the new adapter passes canary comparison.

**Required evidence:** Contract tests for 400/401/403/422/429/5xx, timeout, malformed JSON, missing usage, unavailable model, endpoint mismatch, and sensitive-data redaction. Tests must use recorded or locally served protocol responses for adapter behavior and be labeled as contract tests; do not present them as a successful paid provider call. Measure real token/cost fields when an authorized live provider run exists and use `unknown`, never zero, when usage is unavailable. Compare route quality on the pinned corpus before changing the default.

**Gate:** JEV never writes `CONFIRMED`, `RULED_OUT`, CVSS, exploit verdict, patch verdict, or report validity. No model routing rollout without measured quality and failure behavior.

## Prompt 5 — M5 isolated patch execution and independent verification

**Task:** Define a `FixContract` only for a confirmed, scope-bound candidate with root cause, required security invariant, canonical proof ID/digest, allowed paths, benign controls, test commands, and exact target SHA. Resolve the actual CommandCode binary unambiguously on the host; on Windows do not confuse `cmd.exe` with a CLI shim. Create an isolated worktree at the exact target SHA. Constrain filesystem, process, network, time, and credentials outside the prompt itself. Use the documented headless protocol and bounded turns; parse every NDJSON line and require an actual final success result. Treat timeout, max turns, malformed output, forbidden edits, wrong base SHA, and empty or invalid diff as unresolved. Keep the internal generator as a fallback subject to the same contract and checks.

**Required evidence:** A real patch attempt on an authorized local vulnerable fixture, immutable canonical oracle outside the patch workspace, diff/hash review, exploit replay before and after, benign controls before and after, native tests compared with baseline, and independent bypass review. Demonstrate that worker attempts to edit the oracle, proof, excluded files, or Git metadata fail. Record patch attempt and rejection reasons durably. No worker may push, submit, or mark its own patch accepted.

**Gate:** Only the independent verifier can set `PATCH_ACCEPTED`; a patch never changes the candidate's vulnerability truth. No external CLI claim counts as verified without the actual process result and artifact review.

## Prompt 6 — M6 reporting, publication, patrol, and release

**Task:** Build structured JSON and Markdown reports from stored evidence, with claim, exact scope/SHA, reproducible redacted proof, counterevidence, patch status, coverage, and open proof gaps. Separate local report generation from publication. Put every security PR, issue, private disclosure, advisory, notification, and patrol/CI edit through one policy and proof boundary, including retry and restart paths. Use explicit program channels, operator release review at first rollout, audit events, and idempotency keys. Keep public disclosure closed unless the program permits it.

**Required evidence:** Real local persistence and fake external endpoints may verify transport mechanics, but they do not prove a GitHub publication occurred. For an authorized publication run, record the actual remote identifier and outcome. Test double submit, crash/restart, wrong scope, stale SHA, missing or contradicted proof, patrol edits, and failed native regression. Produce corpus metrics with independent labels and denominators: precision, recall per class, false positives/negatives, open proof gaps, coverage, duplicates, patch success/regression, tokens, and USD. Document any metrics that cannot yet be measured.

**Gate:** In controlled tests: zero unverified automatic security reports or PRs; zero infrastructure failures labeled safe; zero publication outside scope; zero duplicate sends after restart. A ≥98% precision figure remains a target until independently measured on a representative benchmark.

## Required completion report after each prompt

Use this exact structure. Include the report even when blocked; fill unknowns honestly.

```text
IMPLEMENTATION REPORT
Prompt / milestone:
Base HEAD and working-tree status before work:
Requirement and security invariant:
Files changed (separate pre-existing edits):
Source paths and runtime flow inspected:
What actually changed:
Real commands run, environment, exit codes, pass/fail/skip counts:
Evidence artifacts and where they can be inspected:
Negative cases exercised:
Independent review result:
Diff and changed-file lint result:
Remaining proof gaps / blockers / risks:
PROJECT_MAP.md reconciliation:
Gate result: PASS | FAIL | BLOCKED
Next bounded prompt:
```

`PASS` requires every stated gate and its direct evidence. `BLOCKED` names the exact missing prerequisite and preserves open state. `FAIL` names the observed defect. Never advance by relabeling a failure, omission, skipped test, mock, or aspirational design as completion.
