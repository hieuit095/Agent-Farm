# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Generated:** 2026-06-02 (Current Reality)
**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  
**Evidence Basis:** Direct code inspection. No assumptions. All line numbers verified against the v4.0.0 codebase.

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter (Qwen → Gemini), and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

Version 4.0.0 introduces the **Omniscient Context Engine**, which recursively discovers repository documentation, chunks it semantically by markdown headers, ingests it into ChromaDB, and maps local module/function dependency linkages to provide deep subsystem context to LLM agents. Furthermore, version 4.0.0 incorporates **Dynamic Bug Verification** (generating and executing Proof-of-Concept exploits in an isolated container sandbox, evaluated via LLM) and **Blast Radius & Regression Auditing** (using baseline test suite runs and downstream dependent analysis to guarantee zero regressions).

| Component | Technology | Source |
|-----------|------------|--------|
| Language | Python 3.11+ | `pyproject.toml` |
| HTTP client | `httpx` (async) | `pyproject.toml` |
| Primary LLM | `deepseek/deepseek-v4-flash` via OpenRouter | `farm_agent/core/config.py` |
| Code Gen LLM | `deepseek/deepseek-v4-pro` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Layer 1 Appraiser | `qwen/qwen3.7-max` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Layer 2 Supreme Auditor | `google/gemini-3.5-flash` via OpenRouter | `farm_agent/orchestrator/pipeline.py` |
| Red Team (Bloodhound) | `deepseek/deepseek-v4-flash` via OpenRouter | `farm_agent/core/config.py` |
| Semgrep rulesets | `p/security-audit`, `p/cwe-top-25`, `p/default`, `p/golang`, `p/rust`, `p/smart-contracts` | `farm_agent/core/config.py` |
| Database | SQLite (`aiosqlite`) — WAL mode, fallback to DELETE | `farm_agent/orchestrator/memory.py` |
| Docker Sandbox | `docker>=7.1` — complete network + capability isolation | `farm_agent/core/sandbox.py` |
| Config | Pydantic v2 + YAML + `.env` | `farm_agent/core/config.py` |
| CLI | `click>=8.1` + `rich>=13.0` | `farm_agent/cli/main.py` |
| Vector DB | `chromadb>=0.4` — RAG for file & documentation context | `farm_agent/core/rag.py` |
| Notifications | Telegram / Slack / Discord | `farm_agent/core/notifier.py` |

---

## 2. Directory Structure

```ascii
farm_agent/
├── __init__.py
├── agents/                 # Task agent configurations
│   ├── __init__.py
│   └── registry.py
├── analysis/               # CodeAnalyzer (security, quality scanners) & BloodhoundAnalyzer & RepoMapper
│   ├── __init__.py
│   ├── analyzer.py
│   └── mapper.py
├── cli/                    # Click-based CLI entry points
│   ├── __init__.py
│   └── main.py
├── core/                   # Core configurations, Pydantic models, sandbox, RAG context
│   ├── __init__.py
│   ├── config.py           # Application settings
│   ├── daily_log.py
│   ├── exceptions.py
│   ├── leaderboard.py
│   ├── logger.py
│   ├── middleware.py
│   ├── models.py           # Core Pydantic data structures
│   ├── notifier.py
│   ├── profiles.py
│   ├── quotas.py
│   ├── rag.py              # ChromaDB vector DB context loaders
│   ├── retry.py
│   └── sandbox.py          # DockerSandbox engine (Polyglot Guillotine)
├── generator/              # Code generation & DEV-QA loop engines
│   ├── __init__.py
│   ├── engine.py           # ContributionGenerator (Patch and file correction)
│   ├── poc.py              # PoCGenerator (PoC validation & LLM evaluation)
│   ├── reviewer.py         # ReviewerAgent
│   └── scorer.py           # QAHardcoreScorer (Qwen-based QA grader)
├── github/                 # GitHub API client and integration
│   ├── __init__.py
│   ├── client.py           # Async GitHub Client
│   ├── discovery.py        # Target discovery
│   ├── guidelines.py       # PR guidelines & subsystem doc discovery
│   └── security_gate.py    # Private security disclosure gate
├── issues/                 # Proactive issue finding & planning
│   ├── __init__.py
│   └── solver.py           # IssueSolver
├── llm/                    # LLM abstractions and routing
│   ├── __init__.py
│   ├── agents.py
│   ├── context.py
│   ├── models.py
│   ├── provider.py         # OpenRouter integration
│   └── router.py
├── notifications/          # Notification handlers
│   ├── __init__.py
│   └── notifier.py
├── orchestrator/           # Main execution pipelines
│   ├── __init__.py
│   ├── human.py            # SuperHumanLoop (relentless operation)
│   ├── memory.py           # Persistence memory (SQLite)
│   └── pipeline.py         # Main FarmAgentPipeline (Standard & Circular target loops)
├── plugins/
│   └── __init__.py
├── pr/                     # Pull Request management
│   ├── __init__.py
│   ├── manager.py          # PR Manager
│   └── patrol.py           # PR Patrol (comment reviews, CI auto-fix)
├── templates/              # PR and documentation templates
│   ├── __init__.py
│   ├── builtin/
│   └── registry.py
└── tools/                  # Extensible tools protocol
    ├── __init__.py
    └── protocol.py
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent/cli/main.py)] -->|Initiates| Pipeline[FarmAgentPipeline]
    CLI -->|Schedules| HumanLoop[SuperHumanLoop]
    HumanLoop -->|Invokes| Pipeline
    HumanLoop -->|Invokes| Patrol[PR Patrol]

    Pipeline -->|Find Targets| Discovery[RepoDiscovery / DatabaseTargetDiscovery]
    Pipeline -->|Assess vulnerabilities| Analyzer[CodeAnalyzer / BloodhoundAnalyzer]
    Pipeline -->|Store state/quota| Memory[Memory (SQLite)]
    Pipeline -->|Graph dependencies| Mapper[RepoMapper]
    Pipeline -->|Index Docs| RAG[RepoIndexer (ChromaDB)]

    Analyzer -->|API calls| GitHub[GitHubClient]
    Analyzer -->|Evaluate| PrimaryLLM[LLMProvider (DeepSeek-v4-flash)]

    Pipeline -->|Generate Patch| Generator[ContributionGenerator]
    Generator -->|Use| GenLLM[LLMProvider (DeepSeek-v4-pro)]

    Pipeline -->|Build PoC| PoCGen[PoCGenerator]
    Pipeline -->|Execute sandbox tests| Sandbox[DockerSandbox]
    PoCGen -->|Use| GenLLM

    Pipeline -->|Appraise (Gate 1)| Qwen[LLMProvider (Qwen-3.7-Max)]
    Pipeline -->|QA Score| QAScorer[QAHardcoreScorer]
    QAScorer -->|Use| Qwen

    Pipeline -->|Supreme Audit (Gate 2)| Gemini[LLMProvider (Gemini-3.5-Flash)]

    Pipeline -->|Submit contribution| PRManager[PRManager]
    PRManager -->|Create issue/PR| GitHub
```

---

## 4. Core Execution Loops / Entry Points

### Standard Pipeline Flow (`_process_repo()` in `pipeline.py`)

1. **Initialization:** Clones the repository early to a local temp dir to build a full codebase baseline.
2. **Baseline Native Test:** Runs unpatched native tests to establish a baseline state via `DockerSandbox`.
3. **Contextual Enrichment:**
   - Scans for repo guidelines (`CONTRIBUTING.md`).
   - Recursively discovers `.md`, `.txt`, `.rst` files, chunks them semantically, and indexes them into ChromaDB (`RepoIndexer`).
4. **Analysis & AST Mapping:** Parallelized code scanners find issues. `RepoMapper` injects module dependency trees into the findings metadata.
5. **Anti-Farming & Layer 1 Gates:** Filters drop low-impact/documentation PRs. The Layer 1 Qwen-3.7-Max model verifies the severity of remaining findings.
6. **PoC Generation:** Creates a self-contained PoC script using `deepseek-v4-pro` and validates it against the sandbox. If the PoC fails to trigger, the finding is dropped.
7. **Fix Generation:** `ContributionGenerator` proposes a fix.
8. **Sandbox Efficacy & Regression Validation:**
   - Pass 1 (Efficacy): Executes the PoC against patched code. The vulnerability MUST NOT be triggered.
   - Pass 2 (Regression): Executes the native tests. Rejects if they fail but passed previously.
9. **Layer 2 Supreme Audit:** Gemini-3.5-Flash audits the complete dossier and execution logs.
10. **Security & Submission Gate:** Bypasses PR for private security disclosures, otherwise uses `PRManager` to submit the PR on GitHub.

### 3-Cycle DEV-QA Bounty Loop (`run_circular()` in `pipeline.py`)

1. **Target Selection:** Picks the target with the oldest `scanned_at` timestamp from `target_repo.json` / SQLite.
2. **Bloodhound Scan:** Uses `BloodhoundAnalyzer` to pre-scan for vulnerabilities via Semgrep rules. Early exits if clean.
3. **DEV-QA Execution:**
   - DEV LLM generates patches based on failure context and structural AST maps.
   - QA LLM (Qwen) strictly scores patches out of 10.
   - Rejected patches write feedback to the `knowledge_base` (Memory) for the next DEV retry (max 3 cycles).
4. **Sandbox & Gate 2 Check:** Sandbox isolation tests followed by a Gemini Supreme Audit.
5. **Submission:** Successful patches become merged PRs or private issues, recorded in memory to avoid duplicate future work.

---

## 5. Database & State Schema

Agent-Farm utilizes an SQLite database (`data/memory.db`) running in Write-Ahead Logging (WAL) mode for concurrency.

- **`analyzed_repos`**: Keeps a history of analyzed repositories to prevent re-analyzing the same project multiple times needlessly.
- **`submitted_prs`**: Logs created PRs, their state (`open`, `merged`, `closed`), and tracking for CI fix attempts.
- **`run_log`**: Logs global statistics and durations of executions.
- **`pr_outcomes`**: Records final resolutions of PRs, driving data into the AI's learning modules.
- **`repo_preferences`**: A dynamically updated preference model (learned from PR outcomes) defining what a specific repository accepts vs rejects.
- **`blacklisted_repos`**: Tracks repositories to avoid due to hostile maintainers or policy restrictions.
- **`api_usage_log`**: Used to govern rate limits and calculate provider spending across defined sliding windows.
- **`task_schedule`**: Schedules operations, such as cyclic quota cleanups or future scans.
- **`knowledge_base`**: Serves as persistent "lessons learned". Tracks architectural contexts and rejected QA/Filter evaluations so the agent avoids repeating mistakes on subsequent runs for the same repository.
- **`target_repos`**: Primary table for circular hunting modes, ensuring deterministic round-robin behavior.
- **`repo_style_guides`**: Caches previously parsed style guides and `CONTRIBUTING.md` findings.
