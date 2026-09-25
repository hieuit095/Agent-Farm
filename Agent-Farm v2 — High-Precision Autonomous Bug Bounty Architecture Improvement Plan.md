# Agent-Farm v2  
## High-Precision Autonomous Bug Bounty Architecture Improvement Plan

**Status:** Proposed Architecture and Implementation Roadmap  
**Primary Goal:** Transform Agent-Farm from a finding-oriented autonomous security pipeline into a high-precision, evidence-driven autonomous bug bounty engine with strong coverage, reproducible proof, controlled false-positive risk, lower LLM token consumption, and independently verified remediation.

---

# 1. Executive Summary

Agent-Farm already contains several strong foundations:

- multi-stage vulnerability analysis;
- Semgrep-assisted static discovery;
- LLM-based security analysis;
- Docker/sandbox execution;
- PoC generation;
- differential PoC verification primitives;
- patch generation;
- adversarial patch review;
- QA scoring;
- persistent memory;
- security disclosure logic.

However, its current architecture still has several weaknesses that limit its suitability as a high-precision autonomous bug bounty system:

1. findings can progress despite incomplete proof;
2. some error paths fail open rather than preserving uncertainty;
3. PoC generation and PoC evaluation are too closely coupled;
4. the existing differential PoC verifier is not fully enforced by the main pipeline;
5. Semgrep is overly influential in some discovery paths;
6. current cross-file mapping is not yet a true source-to-sink security graph;
7. deduplication can discard unrelated vulnerabilities located in the same file;
8. hard limits on findings can reduce recall;
9. confidence is insufficiently tied to concrete evidence;
10. long-term memory may become stale when code changes;
11. severity may be inferred too early from text instead of demonstrated impact;
12. expensive generative models are used for decisions that could be made more cheaply;
13. Agent-Farm currently carries too much responsibility for writing fixes itself.

The target architecture therefore adopts three major concepts:

### A. Strix-derived security discipline

Extract the strongest architectural concepts from Strix:

- scan-local threat model;
- coverage ledger;
- explicit candidate closure;
- counterevidence;
- proof-gap tracking;
- source-aware discovery;
- root-cause-aware deduplication;
- specialist agents and skills;
- independent validation;
- structured state persistence.

### B. JEV as the Decision Plane

Use TypeSafe JEV through:

```text
~typesafe/jev-latest
```

for high-volume structured decisions such as:

- routing;
- classification;
- skill selection;
- verifier selection;
- model selection;
- prioritization;
- escalation;
- cost control;
- next-action selection.

JEV must **not** become the final security authority.

TypeSafe describes Jev as a System One model that consumes state and produces typed probabilistic decisions rather than free-form prose. OpenRouter currently exposes `~typesafe/jev-latest` as an alias that automatically follows the newest Jev model; the currently listed Jev family uses a 32K context window.

### C. Command Code as the Patch Execution Plane

Move most patch-writing responsibility away from Agent-Farm's internal LLM generator.

Agent-Farm must determine:

> Is this vulnerability real?

> What evidence proves it?

> What security property must the patch enforce?

Command Code must determine:

> How should the repository be modified to satisfy that contract?

Agent-Farm then independently verifies the resulting patch.

Command Code officially supports non-interactive `--print` mode, JSON output, maximum-turn limits, model selection and isolated worktrees, making it suitable for an orchestrated coding-worker role.

---

# 2. Target Architectural Principle

The fundamental architectural rule should become:

```text
Agent-Farm decides security truth.
JEV decides where work should go.
Security agents perform deep reasoning.
Deterministic tools collect machine evidence.
Command Code writes code.
Agent-Farm independently verifies everything.
```

The system must explicitly separate:

```text
DISCOVERY
    ≠
VERIFICATION
    ≠
PATCH GENERATION
    ≠
PATCH VERIFICATION
    ≠
REPORTING
```

No component should be allowed to prove its own work.

---

# 3. Target High-Level Architecture

```text
                         TARGET REPOSITORY
                                │
                                ▼
                 ┌──────────────────────────┐
                 │ Repository Intelligence  │
                 │                          │
                 │ Languages                │
                 │ Frameworks               │
                 │ Routes / APIs            │
                 │ Dependencies             │
                 │ Roles                    │
                 │ Trust boundaries         │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │ Scan-Local Threat Model  │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │       JEV ROUTER         │
                 │ ~typesafe/jev-latest     │
                 │                          │
                 │ Discovery routing        │
                 │ Skill routing            │
                 │ Model routing            │
                 │ Verification routing     │
                 │ Cost routing             │
                 └────────────┬─────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
 Deterministic          Security Agents       Specialized
 Analysis                                     Scanners
        │                     │                     │
 Semgrep                Authorization           Secrets
 AST                     Authentication          SCA
 Dataflow                Business Logic          Config
 Call graph              Injection               Cloud
 Route map               Race/TOCTOU             IaC
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                     CANDIDATE STORE
                              │
                              ▼
                 SECURITY EVIDENCE GRAPH
                              │
                              ▼
                     COUNTEREVIDENCE
                              │
                              ▼
                  INDEPENDENT VERIFIER
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼

     RULED_OUT         OPEN_PROOF_GAP         CONFIRMED
                                                │
                                                ▼
                                 ┌────────────────────────┐
                                 │      FIX CONTRACT      │
                                 └───────────┬────────────┘
                                             │
                                             ▼
                                 ┌────────────────────────┐
                                 │     COMMAND CODE       │
                                 │    Coding Executor     │
                                 └───────────┬────────────┘
                                             │
                                             ▼
                                       Proposed Patch
                                             │
                                             ▼
                                  AGENT-FARM RE-TAKES
                                      CONTROL
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
               Original PoC            Benign Control          Native Tests
                    │                        │                        │
                    ├────────────────────────┼────────────────────────┤
                    │                        │                        │
                    ▼                        ▼                        ▼
             Security Regression       Build / Typecheck       Bypass Review
                    │                        │                        │
                    └────────────────────────┼────────────────────────┘
                                             ▼
                                  Independent Patch Auditor
                                             │
                              ┌──────────────┴──────────────┐
                              ▼                             ▼
                           ACCEPT                         REJECT
                                                           │
                                                           ▼
                                                 PatchFailureReport
                                                           │
                                                           ▼
                                                    Command Code
                                                           │
                                                         Retry
```

---

# 4. Core Security Invariants

The following invariants should become non-negotiable.

## 4.1 Infrastructure failure is not proof of safety

The following conditions:

```text
dependency missing
Docker unavailable
build failure
PoC generation failure
LLM timeout
source unavailable
test environment unavailable
unsupported framework
```

must never automatically mean:

```text
RULED_OUT
```

They mean:

```text
OPEN_PROOF_GAP
```

unless concrete security evidence independently proves the candidate safe.

---

## 4.2 Only confirmed vulnerabilities may enter automatic reporting

```text
state == CONFIRMED
```

must be mandatory for automatic report generation.

---

## 4.3 Patch generation does not confirm a vulnerability

A successfully generated patch provides no proof that the original finding was real.

---

## 4.4 Patch verification must be independent

Command Code may write the patch.

Command Code must not determine whether the security property is actually fixed.

---

## 4.5 PoCs and verification evidence are immutable to the patch worker

Command Code must not be allowed to modify:

```text
.agent-farm/evidence/**
.agent-farm/security-oracles/**
.agent-farm/proofs/**
.agent-farm/candidates/**
.agent-farm/threat-model/**
```

or the canonical exploit/control test supplied by Agent-Farm.

---

## 4.6 Missing coverage is not equivalent to clean coverage

```text
NOT EXAMINED
```

must remain distinct from:

```text
EXAMINED AND RULED OUT
```

This principle is directly inspired by Strix's explicit coverage tracking.

---

# 5. Proposed Core Data Model

Introduce an explicit security-state subsystem.

Suggested package:

```text
farm_agent/security/
├── candidates.py
├── evidence.py
├── closure.py
├── coverage.py
├── threat_model.py
├── evidence_graph.py
├── counterevidence.py
├── verifier.py
├── dedupe.py
├── severity.py
└── report_gate.py
```

## Candidate state

```python
class CandidateState(StrEnum):
    DISCOVERED = "discovered"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    RULED_OUT = "ruled_out"
    OPEN_PROOF_GAP = "open_proof_gap"
```

## Security candidate

```python
@dataclass
class SecurityCandidate:
    candidate_id: str

    vulnerability_class: str

    entrypoints: list[str]
    sources: list[str]
    controls: list[str]
    sinks: list[str]

    auth_context: str | None
    preconditions: list[str]

    supporting_evidence: list[str]
    counterevidence: list[str]

    proof_gaps: list[str]

    state: CandidateState

    confidence_level: str
    confidence_rationale: str

    severity_change_conditions: list[str]
```

## Evidence

```python
@dataclass
class Evidence:
    evidence_id: str
    evidence_type: str

    file: str | None
    start_line: int | None
    end_line: int | None

    command: str | None
    exit_code: int | None

    request_id: str | None
    response_id: str | None

    stdout_hash: str | None
    stderr_hash: str | None

    produced_by: str

    executed: bool

    timestamp: str
```

Evidence should be append-only wherever practical.

---

# 6. Phase 0 — Establish Baseline and Regression Harness

## Objective

Freeze the current behavior before architectural changes.

This phase prevents improvements from accidentally reducing existing capabilities.

## Work

Instrument the current Agent-Farm pipeline.

Capture:

```text
candidates discovered
findings validated
findings rejected
PoCs generated
PoCs executed
patches generated
patches accepted
patches rejected
LLM calls
input tokens
output tokens
model
latency
cost
reason for each transition
```

Introduce:

```text
ScanTelemetry
ModelUsage
CandidateTimeline
ToolExecutionEvent
```

## Benchmark corpus

Build paired test repositories:

```text
vulnerable version
patched version
```

Cover at minimum:

```text
SQL injection
command injection
path traversal
SSRF
IDOR
BFLA
authentication bypass
JWT mistakes
XSS
unsafe deserialization
file upload
race/TOCTOU
business logic
cross-tenant authorization
```

## Required regression scenarios

Explicitly test:

```text
real vulnerability -> report
patched counterpart -> no report

PoC generation failure -> OPEN_PROOF_GAP

Docker unavailable -> no automatic report

source unavailable -> OPEN_PROOF_GAP

LLM timeout -> no automatic confirmation

two independent vulnerabilities in one file -> both retained

same root cause found by multiple agents -> one merged candidate
```

## Exit criteria

No subsequent phase may proceed without reproducible baseline metrics.

---

# 7. Phase 1 — Introduce Candidate/Evidence State Machine

## Objective

Replace implicit finding progression with explicit security state transitions.

This is the most important foundational change.

## Modify

```text
farm_agent/core/models.py
farm_agent/orchestrator/pipeline.py
```

Add:

```text
farm_agent/security/candidates.py
farm_agent/security/evidence.py
farm_agent/security/closure.py
```

## Transition rules

Example:

```text
DISCOVERED
    ↓
INVESTIGATING
    ├── CONFIRMED
    ├── RULED_OUT
    └── OPEN_PROOF_GAP
```

Direct transitions should not be freely made by arbitrary agents.

Instead:

```python
closure_service.close_candidate(...)
```

must evaluate whether closure requirements are satisfied.

---

# 8. Phase 2 — Port Strix Closure Discipline

## Objective

Adopt one of Strix's strongest concepts: every candidate must end with an explicit and defensible outcome.

A candidate should close as exactly one of:

```text
CONFIRMED
RULED_OUT
OPEN_PROOF_GAP
```

## CONFIRMED

Require one of:

### Dynamic confirmation

A reproducible PoC demonstrates attacker-controlled behavior and meaningful security impact.

or:

### Complete static confirmation

A complete reachable trace exists:

```text
attacker-controlled source
        ↓
reachable path
        ↓
relevant security controls
        ↓
sink
        ↓
demonstrable impact
```

Dynamic proof should remain preferred when practical, but it should not be artificially mandatory for vulnerability classes where complete source proof is sufficient.

---

## RULED_OUT

Require concrete counterevidence such as:

```text
specific authorization control
specific sanitizer
specific allowlist
specific validation
specific unreachable condition
```

and evidence that the control occurs on every attacker-reachable path before the dangerous sink.

Statements like:

```text
"probably safe"
"cannot reproduce"
"build failed"
"caller not found"
```

are insufficient.

---

## OPEN_PROOF_GAP

Use whenever:

```text
candidate remains plausible
AND
confirmation is incomplete
AND
no universal blocking control has been proved
```

This preserves recall without polluting reports.

---

# 9. Phase 3 — Scan-Local Threat Model

## Objective

Prevent individual agents from inventing incompatible security assumptions.

Inspired by Strix, create a shared threat model for each scan.

## Add

```text
farm_agent/security/threat_model.py
```

## Threat model structure

```yaml
actors:
  - anonymous
  - authenticated_user
  - tenant_user
  - administrator
  - service_account

trust_boundaries:
  - browser_to_api
  - api_to_database
  - tenant_boundary
  - internal_to_external_network

assets:
  - credentials
  - PII
  - financial_data
  - admin_operations

attacker_controlled_inputs:
  - HTTP parameters
  - headers
  - uploaded files
  - websocket messages
  - queue messages

attacker_stories:
  - cross-tenant access
  - privilege escalation
  - internal service access
  - arbitrary command execution

severity_calibration:
  ...
```

The threat model is:

```text
scan-local
versioned
mutable through explicit amendments
provenance-tracked
```

It must not blindly persist across commits.

---

# 10. Phase 4 — Coverage Ledger

## Objective

Make scan completeness observable.

Inspired directly by Strix's coverage approach.

## Add

```text
farm_agent/security/coverage.py
```

## Coverage record

```python
@dataclass
class CoverageEntry:
    surface: str
    risk_area: str
    outcome: str

    evidence_ids: list[str]
    candidate_ids: list[str]

    agent_id: str

    started_at: str
    completed_at: str | None

    history: list
```

## Example

```text
Surface: /api/orders/:id
Risk Area: horizontal authorization
Outcome: confirmed
```

or:

```text
Surface: file upload
Risk Area: path traversal
Outcome: needs_follow_up
```

## Completion report

At scan end identify:

```text
uncovered attack surfaces
risk classes never assessed
specialist agents that produced no coverage
open proof gaps
agents terminated early
budget exhaustion
unsupported language/framework regions
```

Agent-Farm must never report:

```text
"No vulnerabilities found"
```

when the accurate statement is:

```text
"No confirmed vulnerabilities found within completed coverage."
```

---

# 11. Phase 5 — Integrate JEV as the Decision Plane

## Objective

Reduce unnecessary generative-model work while improving routing consistency.

Jev is designed for typed decisions rather than prose. TypeSafe positions System One models as complementary to slower, deliberative generative models: System One handles fast judgments/classification while the generative model handles complex reasoning.

OpenRouter exposes the moving model identifier:

```text
~typesafe/jev-latest
```

which currently tracks the latest Jev release.

## New package

```text
farm_agent/router/
├── base.py
├── schemas.py
├── jev.py
├── discovery_router.py
├── skill_router.py
├── verification_router.py
├── model_router.py
├── cost_router.py
├── escalation.py
└── fallback.py
```

---

## 11.1 Do not send full repository context to JEV

JEV should receive compact structured state.

Example:

```python
@dataclass
class RoutingContext:
    vulnerability_class: str

    language: str
    framework: str

    source_role: str | None
    sink_role: str | None

    attacker_controlled: bool

    auth_boundary_present: bool

    static_evidence_count: int
    runtime_evidence_count: int

    dataflow_depth: int

    proof_gap_count: int

    coverage_state: str

    estimated_cost: int
```

Target JEV input:

```text
hundreds of tokens
```

not:

```text
tens of thousands of source-code tokens
```

---

# 12. JEV Decision Types

Use Jev for decisions that naturally map to typed alternatives.

## Discovery routing

```text
SEMGREP
AST_ANALYZER
DATAFLOW
AUTH_SPECIALIST
BUSINESS_LOGIC_SPECIALIST
RACE_SPECIALIST
DEPENDENCY_SCANNER
SECRET_SCANNER
```

## Verification routing

```text
STATIC_TRACE
HTTP_REPLAY
UNIT_TEST
DIFFERENTIAL_POC
AUTH_MATRIX
STATE_MACHINE_REPLAY
RACE_HARNESS
MANUAL_REASONING
```

## Model routing

```text
NO_LLM
CHEAP_LLM
SECURITY_LLM
STRONG_REASONING_LLM
```

## Skill routing

```text
IDOR
SSRF
SQLI
JWT
OAUTH
GRAPHQL
FASTAPI
DJANGO
NEXTJS
SUPABASE
...
```

## Cost routing

```text
VERIFY_NOW
VERIFY_LATER
ESCALATE
DEFER
```

A deferred candidate must remain:

```text
DEFERRED / OPEN_PROOF_GAP
```

and never silently become safe.

---

# 13. JEV Must Not Be Final Security Authority

JEV may answer:

```text
"Route this candidate to static verification."
```

It must not directly assert:

```text
"This vulnerability is false."
```

and close the candidate.

Correct architecture:

```text
JEV
 ↓
select verifier
 ↓
verifier collects evidence
 ↓
closure engine
 ↓
RULED_OUT / CONFIRMED / OPEN_PROOF_GAP
```

This distinction is fundamental.

TypeSafe's own positioning is that Jev is a structured decision model, not a replacement for multi-step reasoning.

---

# 14. JEV Confidence-Gated Escalation

Use returned probabilities as routing signals, not truth.

Example policy:

```text
high routing confidence
    → execute selected route

medium confidence
    → selected route + deterministic corroboration

low confidence
    → escalate to stronger reasoning model
```

Thresholds must be calibrated through Agent-Farm's own benchmark rather than hardcoded from intuition.

Store every JEV decision:

```text
decision_id
state_hash
question
choices
probabilities
selected_choice
model_version
outcome
```

This will later allow empirical analysis of routing quality.

---

# 15. JEV Failure Fallback

JEV must be an optimization layer, not a single point of failure.

```text
JEV unavailable
       ↓
RuleBasedRouter
       ↓
safe default route
```

Examples:

```text
SQL injection → Injection Specialist
IDOR → Authorization Specialist
unknown → General Security Reasoner
```

Do not abort scans just because the router is unavailable.

---

# 16. Phase 6 — Multi-Sensor Discovery Engine

## Objective

Increase recall and eliminate Semgrep as a discovery bottleneck.

Semgrep remains valuable but becomes one sensor among many.

## Discovery lanes

```text
Pattern analysis
AST analysis
Dataflow / taint
Call graph
Route/API inventory
AuthN analysis
AuthZ analysis
Role matrix
Dependency/SCA
Secret analysis
Configuration analysis
Cloud/IaC analysis
Business logic
State machine
Race/TOCTOU
File/parser analysis
Deserialization
Historical diff
Sibling/caller sweep
```

JEV chooses relevant lanes based on repository and candidate state.

---

# 17. Phase 7 — Security Evidence Graph

## Objective

Replace lightweight dependency mapping with a security-aware program representation.

Current mapping functionality can remain useful as a fallback/context provider but should not be considered sufficient proof of source-to-sink reachability.

## Add

```text
farm_agent/security/evidence_graph.py
farm_agent/analysis/security_graph/
```

## Node types

```text
ENTRYPOINT
SOURCE
TRANSFORM
AUTHN_CONTROL
AUTHZ_CONTROL
VALIDATION_CONTROL
SANITIZER
SINK
IMPACT
```

## Edge types

```text
CALLS
DATA_FLOWS_TO
GUARDED_BY
BYPASSES
REACHABLE_FROM
RETURNS_TO
CONTROLS
```

Example:

```text
HTTP parameter
      │
      ▼
SOURCE
      │
      ▼
parse_order_id()
      │
      ▼
AUTHZ_CONTROL
      │
      ├── guarded path
      │
      └── bypass path
             │
             ▼
       database sink
             │
             ▼
        cross-tenant data
```

Use language-specific parsers when available.

Regex remains fallback only.

---

# 18. Phase 8 — Specialist Security Agents and Skills

## Objective

Increase depth without loading every vulnerability methodology into every prompt.

Create:

```text
farm_agent/skills/
```

Suggested categories:

```text
skills/
├── vulnerabilities/
│   ├── idor/
│   ├── ssrf/
│   ├── sqli/
│   ├── xss/
│   ├── command_injection/
│   ├── deserialization/
│   ├── path_traversal/
│   ├── race_conditions/
│   └── business_logic/
│
├── frameworks/
│   ├── fastapi/
│   ├── django/
│   ├── flask/
│   ├── nextjs/
│   ├── nestjs/
│   └── express/
│
├── protocols/
│   ├── oauth/
│   ├── jwt/
│   └── graphql/
│
└── cloud/
    ├── aws/
    ├── azure/
    ├── gcp/
    ├── kubernetes/
    ├── supabase/
    └── firebase/
```

This mirrors one of Strix's strongest ideas: load specialized knowledge only when relevant.

Command Code independently supports an Agent Skills mechanism with progressive disclosure—skill metadata is loaded initially and full instructions are loaded when activated—which reinforces the value of the same architectural principle for Agent-Farm.

---

# 19. Phase 9 — Mandatory Counterevidence

## Objective

Actively attack every promising finding before reporting it.

For every candidate approaching confirmation, create an independent task:

```text
Find the strongest evidence that this reported vulnerability is NOT exploitable.
```

The counterevidence agent must inspect:

```text
callers
middleware
framework defaults
authorization guards
sanitizers
validation
deployment assumptions
configuration
alternate paths
preconditions
```

It must not simply review the original agent's reasoning.

Prefer a fresh context.

Where economical, prefer model diversity.

Example:

```text
Discovery Agent → Model A

Counterevidence Agent → Model B

Machine verifier → deterministic

Final closure → state machine
```

Model diversity is useful but does not replace independent evidence.

---

# 20. Phase 10 — Upgrade PoC Verification

Agent-Farm already contains the beginnings of differential PoC verification.

The next architecture must enforce it.

## Eliminate fail-open behavior

Current behavior conceptually equivalent to:

```text
PoC failed
   ↓
generate fix anyway
```

must become:

```text
PoC failed
   ↓
OPEN_PROOF_GAP
```

unless complete static proof exists.

---

# 21. Four-Part Differential Security Proof

Upgrade from simple:

```text
before patch
after patch
```

to:

```text
A. legitimate baseline
B. malicious behavior before patch
C. malicious behavior after patch
D. legitimate behavior after patch
```

Example IDOR:

```text
A owner → 200

B attacker → 200
  CONFIRMS unauthorized access

PATCH

C attacker → 403

D owner → 200
```

A patch is valid only if:

```text
B demonstrates vulnerability
C demonstrates mitigation
D demonstrates preserved legitimate behavior
```

---

# 22. Vulnerability-Specific Machine Oracles

Do not rely primarily on:

```text
process exit != 0
```

because successful security exploits frequently exit normally.

Create structured oracles.

Examples:

## IDOR

```text
attacker receives another user's object
```

## SQL injection

```text
payload modifies query semantics
```

## SSRF

```text
server reaches controlled internal destination
```

## Path traversal

```text
resolved file escapes allowed root
```

## Command injection

```text
controlled side effect occurs
```

## Race condition

```text
forbidden state observed under concurrency
```

---

# 23. Phase 11 — Replace Internal Patch Generation with Command Code Executor

## Objective

Reduce Agent-Farm workload and let a specialized coding harness perform repository modification.

Command Code's official documentation describes it as an agentic coding system with file, edit, shell, sub-agent and other tooling. It also supports many models and model selection through the CLI.

Create:

```text
farm_agent/fix/
├── orchestrator.py
├── contract.py
├── result.py
└── executors/
    ├── base.py
    ├── command_code.py
    └── internal.py
```

The existing internal generator can remain as a fallback initially.

---

# 24. Fix Contract

Agent-Farm must provide Command Code with a compact, deterministic specification.

Example:

```yaml
fix_id: FIX-AF-2026-00132

candidate:
  id: AF-2026-00132

vulnerability:
  class: IDOR
  cwe: CWE-639

evidence:
  entrypoint:
    file: src/api/orders.ts
    line: 84

  attacker_input:
    expression: req.params.orderId

  sink:
    file: src/repositories/orders.ts
    line: 113

demonstrated_behavior:
  owner_request:
    status: 200

  attacker_request:
    status: 200

required_behavior:
  owner_request:
    status: 200

  attacker_request:
    status: 403

constraints:
  - preserve public API compatibility
  - do not modify the security oracle
  - do not modify the canonical PoC
  - do not disable tests
  - do not suppress exceptions merely to satisfy tests
  - prefer minimal security fix
```

Command Code does **not** receive the entire original Agent-Farm reasoning transcript.

This significantly reduces redundant context.

---

# 25. Command Code Execution Mode

Use Command Code programmatically.

Its official CLI supports:

```text
-p / --print
--output-format json
--max-turns
--model
--worktree
--permission-mode
```

in non-interactive workflows.

Conceptual invocation:

```bash
cmd -p \
  --output-format json \
  --permission-mode dont-ask \
  --max-turns 30 \
  --worktree "fix-AF-2026-00132" \
  "Implement the attached Fix Contract."
```

Agent-Farm should parse Command Code's machine-readable output instead of scraping conversational text.

---

# 26. Use Isolated Worktrees

Command Code officially supports managed git worktrees so sessions can operate on isolated branches/directories without modifying the main checkout.

Use:

```text
one vulnerability
        ↓
one isolated worktree
        ↓
one patch attempt
```

Benefits:

```text
no contamination of main checkout
parallel fix attempts
easy git diff
easy rollback
easy comparison between competing fixes
```

Possible future architecture:

```text
AF-001
 ├── fix-attempt-A
 ├── fix-attempt-B
 └── fix-attempt-C
```

Agent-Farm can verify each and choose an accepted patch based on security evidence—not stylistic preference.

---

# 27. Command Code Permission Policy

Never run the patch worker in unrestricted YOLO mode.

Command Code provides:

```text
default
accept-edits
plan
yolo
dont-ask
```

permission modes.

For autonomous Agent-Farm operation:

```text
dont-ask
```

is preferable because unapproved operations fail closed instead of waiting for interactive approval. Command Code explicitly documents this mode as suitable for unattended/CI workflows.

Example project policy:

```json
{
  "permissions": {
    "defaultMode": "dont-ask",

    "allow": [
      "Edit(src/**)",
      "Edit(app/**)",
      "Edit(lib/**)",
      "Shell(pytest *)",
      "Shell(npm test*)",
      "Shell(npm run test*)",
      "Shell(npm run build*)",
      "Shell(git diff*)",
      "Shell(git status*)"
    ],

    "deny": [
      "Edit(.git/**)",
      "Edit(.agent-farm/evidence/**)",
      "Edit(.agent-farm/proofs/**)",
      "Edit(.agent-farm/security-oracles/**)"
    ]
  }
}
```

Actual allowlists must be generated for each repository.

---

# 28. Add OS-Level Isolation Too

Command Code permissions should not be the sole protection mechanism.

Use:

```text
container
+
worktree
+
filesystem permissions
+
Command Code permission policy
+
Agent-Farm hooks
```

The canonical PoC/security oracle can be mounted:

```text
read-only
```

into the patch environment.

This prevents the coding agent from making a failing exploit test disappear by editing the test itself.

---

# 29. Command Code Hooks

Command Code supports:

```text
PreToolUse
PostToolUse
Stop
SessionStart
```

hooks.

Pre-tool hooks can block operations, and post-tool hooks can audit changes.

Use them to implement:

### PreToolUse

Reject:

```text
editing security oracle
editing PoC
git push
git reset --hard
external network access if unnecessary
destructive commands
```

### PostToolUse

Record:

```text
edited file
timestamp
session ID
tool
diff hash
```

### Stop

Check that:

```text
working tree diff exists
tests were attempted
protected files remain unchanged
```

Do not use hooks as proof that the patch is secure.

They are execution controls only.

---

# 30. Patch Result Contract

Command Code executor should return:

```python
@dataclass
class FixResult:
    attempt_id: str

    success: bool

    worktree: str

    changed_files: list[str]

    diff: str

    commands_run: list[str]

    tests_run: list[str]

    executor_model: str

    turns_used: int

    raw_event_log: str
```

Security judgment fields should intentionally be absent.

Command Code should not return:

```text
vulnerability_confirmed = true
patch_secure = true
```

as authoritative values.

---

# 31. Phase 12 — Closed-Loop Patch Verification

Once Command Code finishes:

```text
Agent-Farm regains control.
```

Run:

```text
1 canonical exploit
2 security oracle
3 benign control
4 native unit tests
5 native integration tests
6 build
7 typecheck
8 lint where relevant
9 bypass-oriented security checks
```

Patch status:

```text
PATCH_PROPOSED
PATCH_VERIFYING
PATCH_ACCEPTED
PATCH_REJECTED
PATCH_UNRESOLVED
```

This state must remain separate from vulnerability state.

Example:

```text
Vulnerability:
CONFIRMED

Patch:
UNRESOLVED
```

is valid.

---

# 32. Structured Patch Failure Feedback

When verification fails, do not merely tell Command Code:

```text
"Try again."
```

Generate:

```yaml
patch_attempt: 2

status: rejected

failures:

  - type: SECURITY_FAILURE
    oracle: IDOR-attacker

    expected:
      status: 403

    observed:
      status: 200

  - type: FUNCTIONAL_REGRESSION
    test:
      tests/orders/test_owner_access.py

    expected:
      status: 200

    observed:
      status: 500
```

Feed only relevant failure data into the next patch attempt.

Suggested:

```text
max_fix_attempts = configurable
```

For example:

```text
3
```

initially.

Do not loop indefinitely.

---

# 33. Phase 13 — Root-Cause-Aware Deduplication

Remove deduplication logic based primarily on:

```text
same file
similar title
```

A single file may contain several unrelated exploitable vulnerabilities.

Create fingerprint:

```text
vulnerability_class
entrypoint
attacker_source
security_control
sink
auth_context
root_cause
impact
```

Example:

```python
fingerprint = hash(
    vuln_class,
    entrypoint,
    source,
    root_control,
    sink,
    auth_context,
)
```

If three discovery agents identify the same root cause:

```text
merge evidence
```

instead of producing three reports.

If the same helper produces independently exploitable vulnerabilities through separate entrypoints:

```text
retain separate candidates
```

when attacker context or impact differs.

This follows Strix's stronger root-cause-oriented deduplication philosophy.

---

# 34. Phase 14 — Source-Aware Sibling Sweep

After confirming one vulnerability, automatically inspect:

```text
sibling routes
sibling methods
other callers
duplicate helpers
alternate wrappers
parallel implementations
other role paths
```

Example:

```text
GET /users/:id vulnerable

→ examine:

PUT /users/:id
DELETE /users/:id
GET /orders/:id
shared getById helper
admin/user variants
```

Finding one flaw should increase coverage rather than terminate investigation.

---

# 35. Phase 15 — Remove Artificial Finding Caps

Replace:

```text
max N findings
```

with:

```text
max concurrent verification tasks
max token budget
max wall-clock budget
max expensive-model calls
```

Candidate storage should remain high recall.

Verification controls cost.

This is critical for bug bounty scanning because arbitrary candidate limits create false negatives.

---

# 36. Phase 16 — Context and Memory Redesign

## Problem

Repository-wide long-lived lessons can become stale.

Example:

```text
"auth helper X is safe"
```

may be true for commit A and false for commit B.

## Solution

Key learned knowledge by:

```text
repository
commit SHA
branch
language
framework
vulnerability class
analyzer version
verifier version
timestamp
TTL
```

Separate:

```text
ScanLocalState
```

from:

```text
LongTermKnowledge
```

Scan-local state includes:

```text
threat model
coverage
candidate evidence
open proof gaps
JEV decisions
agent assignments
```

Long-term knowledge should store patterns and outcomes with provenance rather than absolute security claims.

---

# 37. Phase 17 — Context Compaction Inspired by Strix

Persist important state in structured stores instead of leaving it only in agent conversation history.

Store:

```text
ThreatModel
CandidateStore
EvidenceGraph
CoverageLedger
DecisionLog
PatchAttemptLog
```

When spawning an agent, construct only the context required for that task.

Example:

```text
AuthorizationAgent
```

gets:

```text
relevant routes
role matrix
relevant call graph
related candidates
auth controls
required skill
```

not the complete scan transcript.

This improves:

```text
token efficiency
reasoning focus
reproducibility
debuggability
```

---

# 38. Phase 18 — Severity Calibration After Proof

Move final severity calculation later.

Pipeline:

```text
candidate discovered
        ↓
reachability proven
        ↓
exploitability proven
        ↓
impact demonstrated
        ↓
counterevidence passed
        ↓
severity calibrated
```

Avoid deriving final severity primarily from:

```text
scanner severity
title
description
keyword matching
```

Store:

```text
preliminary_severity
```

separately from:

```text
verified_severity
```

---

# 39. Phase 19 — Hard Reporting Gate

Implement:

```text
farm_agent/security/report_gate.py
```

Conceptual logic:

```python
def can_auto_report(candidate):

    if candidate.state != CONFIRMED:
        return False

    if candidate.proof_gaps:
        return False

    if not candidate.counterevidence_completed:
        return False

    if candidate.requires_runtime_proof:
        if not candidate.runtime_evidence:
            return False

    if not candidate.impact_demonstrated:
        return False

    return True
```

Static-only confirmation remains possible when the evidence graph provides a complete reachable source-to-control-to-sink-to-impact proof.

---

# 40. Final Bug Bounty Report Schema

Require:

```text
Repository
Commit SHA
Affected version

Vulnerability class
CWE

Affected entrypoint
Attacker-controlled source
Security control
Sink

Preconditions

Complete evidence chain

Counterevidence

PoC or static proof

Replay instructions

Demonstrated impact

Confidence
Confidence rationale

Severity
Severity-change conditions

Remediation

Patch verification status

Coverage context

Known remaining proof gaps
```

The report generator must consume structured evidence, not reconstruct facts from an old conversation.

---

# 41. Phase 20 — Token and Cost Intelligence

Add:

```text
farm_agent/telemetry/cost.py
```

Track:

```text
tokens per candidate
tokens per confirmed vulnerability
tokens per false candidate
tokens by agent
tokens by model
tokens by vulnerability class
cost per confirmed vulnerability
JEV decisions
JEV escalation rate
JEV routing accuracy
Command Code turns per accepted patch
```

This enables empirical routing optimization.

---

# 42. Recommended JEV Cost Strategy

JEV handles frequent decisions.

Deterministic logic handles obvious cases.

Expensive models handle uncertainty.

Target hierarchy:

```text
                TASK
                  │
                  ▼
          deterministic rule?
             /          \
           yes           no
            │             │
            ▼             ▼
          TOOL           JEV
                           │
                 ┌─────────┼─────────┐
                 │         │         │
                 ▼         ▼         ▼
              tool      cheap AI   strong AI
```

Example:

```text
Parse Semgrep result
→ Python

Select security specialist
→ JEV

Straightforward candidate classification
→ JEV

Simple source context explanation
→ cheaper model

Cross-tenant privilege chain
→ strong security reasoner

Complex business logic exploit
→ strong reasoning model

Write patch
→ Command Code

Verify patch
→ Agent-Farm + deterministic oracle
```

---

# 43. Important JEV Optimization

Do not ask JEV:

```text
"Analyze this repository and tell us what to do."
```

Ask bounded typed decisions such as:

```text
Which verifier should handle this candidate?

A static trace
B HTTP replay
C differential PoC
D authorization matrix
E race harness
```

This is exactly the class of structured decision TypeSafe built Jev to address.

---

# 44. Phase 21 — Command Code Cost Optimization

Do not start a coding session until:

```text
candidate == CONFIRMED
```

The Fix Contract should contain only relevant source information.

Command Code can then independently inspect additional repository context if necessary.

Use:

```text
--max-turns
```

to bound runaway coding sessions.

Command Code officially supports per-session model selection, so patch complexity can eventually be routed by JEV:

```text
simple patch
    → economical coding model

multi-file refactor
    → stronger coding model
```

Command Code currently exposes a broad model registry through `--model` and `--list-models`.

---

# 45. Phase 22 — Security Benchmark and Release Gate

Before calling Agent-Farm v2 production ready, measure it against controlled truth.

## Primary metrics

```text
Auto-report precision
Recall by vulnerability class
False positive rate
False negative rate
Open-proof-gap rate
Runtime reproduction rate
Duplicate-report rate
Coverage completeness
Patch success rate
Patch regression rate
Tokens per confirmed vulnerability
Cost per confirmed vulnerability
```

Recommended engineering objectives:

```text
unverified automatic reports = 0

infrastructure failure classified as safe = 0

hidden uncovered surfaces = 0

counterevidence for automatic reports = 100%

exact affected code location for reports = 100%

duplicate reports from same root cause ≈ 0
```

A precision target such as:

```text
>= 98%
```

may be used for a controlled benchmark, but it should remain a target until empirically achieved.

Do not treat LLM self-confidence as benchmark truth.

---

# 46. Recommended Implementation Order

The phases should be implemented in this order:

```text
PHASE 0
Baseline + telemetry
        ↓
PHASE 1
Candidate / Evidence state
        ↓
PHASE 2
Closure discipline
        ↓
PHASE 3
Threat model
        ↓
PHASE 4
Coverage ledger
        ↓
PHASE 5
JEV router
        ↓
PHASE 6
Multi-sensor discovery
        ↓
PHASE 7
Security Evidence Graph
        ↓
PHASE 8
Specialist skills
        ↓
PHASE 9
Counterevidence
        ↓
PHASE 10
PoC verification upgrade
        ↓
PHASE 11
Command Code executor
        ↓
PHASE 12
Closed-loop patch verification
        ↓
PHASE 13
Root-cause dedupe
        ↓
PHASE 14
Sibling sweep
        ↓
PHASE 15
Remove candidate caps
        ↓
PHASE 16
Memory redesign
        ↓
PHASE 17
Context compaction
        ↓
PHASE 18
Severity calibration
        ↓
PHASE 19
Hard report gate
        ↓
PHASE 20
Cost intelligence
        ↓
PHASE 21
Command Code/JEV optimization
        ↓
PHASE 22
Benchmark + production rollout
```

---

# 47. Priority Grouping

## P0 — Security Correctness

Implement first:

```text
Candidate state machine
Evidence model
OPEN_PROOF_GAP
remove fail-open behavior
wire differential PoC into main pipeline
hard report gate
```

Without these, later automation can amplify incorrect decisions.

---

## P1 — Security Discipline

```text
Threat Model
Coverage Ledger
Counterevidence
Root-cause dedupe
```

This imports the most valuable architectural discipline from Strix.

---

## P2 — Efficiency

```text
JEV Decision Plane
Context reduction
Model routing
Cost telemetry
```

Do this only after decisions have explicit state schemas.

---

## P3 — Recall

```text
Multi-sensor discovery
Security Evidence Graph
Specialist agents
Sibling sweeps
Remove artificial finding caps
```

---

## P4 — Fix Automation

```text
Command Code executor
Fix Contract
worktree isolation
permission policy
hooks
patch feedback loop
```

---

## P5 — Production Hardening

```text
memory versioning
full benchmark suite
cost optimization
performance optimization
production rollout
```

---

# 48. Initial File-Level Change Map

Highest-priority existing files:

```text
farm_agent/core/models.py
farm_agent/orchestrator/pipeline.py
farm_agent/analysis/analyzer.py
farm_agent/analysis/mapper.py
farm_agent/generator/poc.py
farm_agent/generator/engine.py
farm_agent/generator/reviewer.py
farm_agent/generator/scorer.py
farm_agent/core/sandbox.py
farm_agent/orchestrator/memory.py
farm_agent/llm/context.py
farm_agent/github/security_gate.py
```

New modules:

```text
farm_agent/security/
farm_agent/router/
farm_agent/fix/
farm_agent/skills/
farm_agent/telemetry/
```

---

# 49. Specific Refactoring of Existing Generator

Do not immediately delete:

```text
farm_agent/generator/engine.py
```

Refactor responsibility gradually.

Current concept:

```text
GeneratorEngine
  ↓
creates patch
```

Target:

```text
FixOrchestrator
       │
       ├── CommandCodeExecutor
       │
       └── InternalLLMExecutor
              fallback
```

Eventually:

```text
Command Code = default
Internal LLM = fallback/testing backend
```

This minimizes migration risk.

---

# 50. Command Code Integration Security Boundary

Recommended isolation:

```text
HOST
│
├── Agent-Farm coordinator
│
├── evidence database
│
├── immutable PoCs
│
└── verification oracle
│
└──── Docker / sandbox
         │
         └── isolated git worktree
               │
               └── Command Code
                     │
                     ├── read repository
                     ├── edit permitted code
                     ├── run permitted tests
                     └── return diff
```

Command Code should not need access to:

```text
bug bounty credentials
GitHub push credentials
production credentials
OpenRouter master keys
Agent-Farm evidence database write credentials
```

Agent-Farm performs external actions after verification.

---

# 51. Recommended Command Code Guardrails

Use Command Code's documented permission engine and hooks. Its permissions are enforced by Command Code rather than merely requested through prompts, which is an important property for unattended integration.

Additionally enforce:

```text
container filesystem boundary
network policy
CPU/memory limits
execution timeout
process limit
read-only oracle mount
isolated git branch/worktree
```

Never rely only on:

```text
"Do not edit the PoC"
```

inside the prompt.

---

# 52. Agent-Farm v2 Decision Ownership Matrix

| Responsibility | Owner |
|---|---|
| Repository profiling | Agent-Farm |
| Threat model | Agent-Farm + security reasoner |
| Coverage tracking | Agent-Farm |
| Routine routing | JEV |
| Skill selection | JEV |
| Model selection | JEV |
| Cost routing | JEV |
| Static scanning | deterministic tools |
| Deep vulnerability reasoning | security LLM |
| Counterevidence | independent security agent |
| Dynamic PoC | PoC worker |
| Evidence storage | Agent-Farm |
| Candidate closure | Agent-Farm state machine |
| Patch implementation | Command Code |
| Patch security validation | Agent-Farm |
| Regression validation | Agent-Farm sandbox |
| Severity | Agent-Farm after proof |
| Final reporting | Agent-Farm |
| Disclosure decision | Agent-Farm policy layer |

This separation should remain explicit in code.

---

# 53. What JEV Must Never Own

JEV should not be the authority for:

```text
CONFIRMED
RULED_OUT
CVSS
exploit success
patch success
final report validity
```

It can recommend which component should evaluate those questions.

---

# 54. What Command Code Must Never Own

Command Code should not be authoritative for:

```text
whether vulnerability exists
whether PoC proves vulnerability
whether exploit succeeded
whether patch fully fixes vulnerability
whether severity is correct
whether report should be submitted
```

Its authority is:

```text
repository modification
```

within a constrained environment.

---

# 55. Target Final Runtime

The complete target workflow becomes:

```text
1. Repository received
        ↓
2. Repository profiler
        ↓
3. Scan-local threat model
        ↓
4. Attack surface inventory
        ↓
5. JEV selects discovery paths
        ↓
6. Parallel discovery sensors
        ↓
7. Candidate normalization
        ↓
8. Evidence graph construction
        ↓
9. Coverage update
        ↓
10. JEV selects appropriate verifier
        ↓
11. Security specialist reasoning
        ↓
12. Counterevidence pass
        ↓
13. Static/runtime proof
        ↓
14. Closure state

        ├── RULED_OUT
        │
        ├── OPEN_PROOF_GAP
        │
        └── CONFIRMED
                 ↓
15. Severity calibration
                 ↓
16. Fix Contract
                 ↓
17. Command Code isolated worktree
                 ↓
18. Proposed patch
                 ↓
19. Canonical exploit replay
                 ↓
20. Benign control
                 ↓
21. Native tests
                 ↓
22. Security regression tests
                 ↓
23. Bypass review
                 ↓
        ┌────────┴────────┐
        │                 │
      ACCEPT            REJECT
        │                 │
        │          PatchFailureReport
        │                 │
        │          Command Code retry
        │
        ▼
24. Final evidence package
        ↓
25. Hard report gate
        ↓
26. Bug bounty dossier
```

---

# 56. Why This Architecture Is Stronger Than the Current Agent-Farm

The redesigned system improves precision because:

```text
hypotheses are separated from confirmed vulnerabilities;
uncertainty remains explicit;
counterevidence is mandatory;
runtime proof is replayable;
patch generation cannot validate itself;
reporting consumes structured evidence.
```

It improves recall because:

```text
Semgrep is no longer a bottleneck;
candidate count is not artificially capped;
sibling/caller sweeps are performed;
specialist agents inspect difficult vulnerability classes;
coverage gaps stay visible.
```

It reduces token usage because:

```text
JEV handles high-volume micro-decisions;
deterministic tools replace unnecessary LLM reasoning;
specialized contexts replace full-history prompts;
structured state replaces repeated explanations;
Command Code takes over repository modification work;
model routing prevents expensive models from handling trivial tasks.
```

It improves maintainability because:

```text
decision plane
execution plane
security state plane
patch plane
verification plane
```

are clearly separated.

---

# 57. Final Target Architecture

The final Agent-Farm should not be viewed as one large autonomous AI agent.

It should become:

> **A high-precision autonomous security orchestration, evidence, verification, and bug bounty operating system.**

Its core architecture should be:

```text
STRIX-STYLE SECURITY DISCIPLINE
+
AGENT-FARM SANDBOX AND DIFFERENTIAL VERIFICATION
+
JEV STRUCTURED DECISION ROUTING
+
SPECIALIZED SECURITY REASONERS
+
COMMAND CODE PATCH EXECUTION
+
DETERMINISTIC SECURITY ORACLES
+
EVIDENCE-DRIVEN REPORTING
```

The most important ownership principle is:

```text
JEV decides who should work.

Security agents reason about difficult security questions.

Command Code writes the fix.

Deterministic tools measure what actually happened.

Agent-Farm owns security truth.
```

---

# 58. Official Documentation Used

## Command Code

Official documentation confirms:

- CLI installation and execution;
- non-interactive/headless execution;
- JSON output;
- model selection;
- maximum-turn control;
- permissions;
- `dont-ask` unattended mode;
- hooks;
- skills;
- isolated git worktrees;
- extensive built-in coding tools.

## TypeSafe JEV

TypeSafe describes Jev as its first System One model, designed to turn state into fast structured probabilistic decisions rather than free-form text. Its intended use cases include routing and other structured automation decisions.

## OpenRouter JEV endpoint

OpenRouter currently provides:

```text
~typesafe/jev-latest
```

as an alias tracking the latest Jev-family model, with the currently listed family using a 32K context window.

---

# 59. Recommended First Implementation Milestone

Do **not** begin by integrating Command Code.

Do **not** begin by adding more vulnerability agents.

Do **not** begin by adding JEV everywhere.

The first milestone should be:

```text
Candidate
+
Evidence
+
Closure State
+
OPEN_PROOF_GAP
+
Coverage
+
Hard Report Gate
+
Differential PoC wiring
```

Then integrate:

```text
JEV
```

on top of explicit state.

Then improve:

```text
discovery + evidence graph
```

Then integrate:

```text
Command Code
```

after the security truth boundary is stable.

This order is important because automation should amplify a correct security state machine—not amplify ambiguous decisions.

---

# 60. Definition of Agent-Farm v2 Success

Agent-Farm v2 should eventually be able to make the following statement about every automatic bounty report:

> The system identified an attacker-reachable security condition, preserved the evidence required to reproduce it, actively searched for evidence that disproves the claim, independently confirmed the vulnerability, recorded what parts of the target were and were not assessed, generated remediation in an isolated coding environment, replayed the original security proof against the patched code, verified legitimate behavior remained functional, and produced the final report only after all mandatory security gates passed.

That should be the architectural standard for the project.