# PROJECT_MAP.md — Agent-Farm Ground Truth

**Version:** v4.0.0 — Omniscient Context Engine  
**Entry Point:** `farm_agent/cli/main.py` → `cli()` (Click-based CLI)  
**Language:** Python 3.11+  

---

## 1. System Overview & Active Tech Stack

**What it does:** Autonomous AI agent system that discovers open-source GitHub repositories or scans targets for issues and vulnerabilities. It analyzes code via multi-phase LLM prompts, generates patches, validates them in isolated Docker sandboxes, runs a two-layer expert filter (Qwen → Gemini), and submits pull requests or private disclosures. It also runs a PR Patrol loop to auto-reply to comments, address code reviews, and self-correct CI failures.

| Component | Technology | Role |
|-----------|------------|------|
| Language | Python 3.11+ | Core engine language |
| HTTP client | `httpx` (async) | Async HTTP requests, API communications |
| Primary LLM | OpenRouter (`deepseek-v4-flash`, `deepseek-v4-pro`, `qwen3.7-max`, `gemini-3.5-flash`) | Core analytical and generation logic |
| Database | SQLite (`aiosqlite`) | Persistent state, findings, and tracking |
| Docker Sandbox | `docker>=7.1` | Complete network + capability isolation for test evaluation |
| Config | Pydantic v2 + YAML + `.env` | Config validation and management |
| CLI | `click>=8.1` + `rich>=13.0` | Comprehensive user interface |
| Vector DB | `chromadb>=0.4` | RAG for file & documentation context |
| Tooling | Pytest, Ruff, Hatchling | Linting, Testing, and Packaging |

---

## 2. Directory Structure

```text
farm_agent/
    __init__.py
    agents/                  # Core LLM Agents and Registries
        __init__.py
        registry.py
    analysis/                # Codebase scanning, mapping, and analysis
        __init__.py
        analyzer.py
        mapper.py
    cli/                     # Click-based Rich CLI
        __init__.py
        main.py
    core/                    # Configuration, Middleware, Logging, quotas, retries, etc.
        __init__.py
        config.py
        daily_log.py
        exceptions.py
        leaderboard.py
        logger.py
        middleware.py
        models.py
        notifier.py
        profiles.py
        quotas.py
        rag.py
        retry.py
        sandbox.py
    generator/               # Generation engines (Patches, Review, Scoring, PoCs)
        __init__.py
        engine.py
        poc.py
        reviewer.py
        scorer.py
    github/                  # GitHub API interactions, guidelines, security gate
        __init__.py
        client.py
        discovery.py
        guidelines.py
        security_gate.py
    issues/                  # Solving specific issue tracking logic
        __init__.py
        solver.py
    llm/                     # Context management, LLM Providers, Routing, Modeling
        __init__.py
        agents.py
        context.py
        models.py
        provider.py
        router.py
    notifications/           # Telegram, Discord, Slack integrations
        __init__.py
        notifier.py
    orchestrator/            # Top-level pipelines, human-simulation, and persistent memory
        __init__.py
        human.py
        memory.py
        pipeline.py
    plugins/
        __init__.py
    pr/                      # Pull Request management and patrolling daemon
        __init__.py
        manager.py
        patrol.py
    templates/               # Builtin contribution templates
        __init__.py
        registry.py
        builtin/
            add-gitignore.yaml
            add-license.yaml
            add-type-hints.yaml
            fix-readme-badges.yaml
            security-headers.yaml
    tools/                   # Tool protocol definition
        __init__.py
        protocol.py
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (main.py)] --> Pipeline[FarmAgentPipeline (pipeline.py)]
    Pipeline --> Discovery[GitHub Discovery]
    Pipeline --> Memory[SQLite Memory]
    Pipeline --> Analysis[Bloodhound & CodeAnalyzer]
    Analysis --> Generator[Generator Engine & PoC Sandbox]
    Generator --> Sandbox[Docker Sandbox Validation]
    Generator --> QA[Layer 1 & Layer 2 QA Filters]
    QA --> PRManager[PR Manager & Submitter]

    CLI --> PRPatrol[PR Patrol Daemon]
    PRPatrol --> GitHubAPI[GitHub Client]

    CLI --> Solver[IssueSolver]
    Solver --> Generator
```

---

## 4. Core Execution Loops

* `run`: Triggers auto-discovery of repos based on config (`target_repo.json` or `config.yaml`), followed by scanning and PR contribution.
* `target`: Operates exactly like `run` but forces execution against a specifically provided repository URL.
* `solve`: Targets a specific repository to ingest existing issues and automatically propose PRs fixing them.
* `hunt`: Aggressively loop-discovers repositories across several rounds.
* `hunt_circular`: A continuous hunt looping mechanism reading off `target_repo.json`.
* `superhuman`: The ultimate 24/7 relentless loop, managing human-like behavior (delays) while context-switching between generating fixes and patrolling open PRs.
* `patrol`: Scans previously submitted, open PRs for comments, code reviews, and CI test pipeline results. Iteratively pushes auto-fixes.
* `janitor`: Triggers standalone maintenance workflows (cleaning up or abandoning dead/garbage PRs).

---

## 5. Database/State Schema (`farm_agent/orchestrator/memory.py`)

The persistent memory state relies heavily on `aiosqlite`. Key tables:

* `analyzed_repos`: Logs `full_name`, `language`, `stars`, `analyzed_at`, `findings`, and `metadata` to avoid duplicate scanning.
* `submitted_prs`: Logs `id`, `repo`, `pr_number`, `pr_url`, `title`, `type`, `status`, `branch`, `fork`, `created_at`, `updated_at`, `ci_fix_attempts`, and `discussion_replies` to manage active pull requests.
* `findings_cache`: Tracks specific findings (e.g., vulnerabilities) via `id`, `repo`, `type`, `severity`, `title`, `file_path`, `status`, and `created_at`.
* `run_log`: Historical aggregate metrics logging `started_at`, `finished_at`, `repos_analyzed`, `prs_created`, `findings`, `errors`, and `metadata`.
* `pr_outcomes`: Evaluation feedback loop logging `repo`, `pr_number`, `pr_url`, `pr_type`, `outcome`, `feedback`, `time_to_close_hours`, and `recorded_at`.
* `repo_preferences`: Maintainer vibe analysis tracking `preferred_types`, `rejected_types`, `merge_rate`, `avg_review_hours`, and `notes`.
* `blacklisted_repos`: Explicitly bans repositories by `repo`, `reason`, `pr_number`, and `blacklisted_at`.
* `api_usage_log`: Logs specific API usage across providers for cost calculations (`timestamp`, `provider`).
* `task_schedule`: Tracks time-based triggers (`task_key`, `next_run`, `updated_at`).
* `knowledge_base`: Deep context logs via `repo_name`, `entry_type`, `content`, and `created_at`.
* `target_repos`: Manages pipeline queue across `repo_url`, `status`, `scanned_at`, `language`, `bounty_amount`, and `diamond_target`.
* `repo_style_guides`: Pre-computed LLM guidelines (`repo`, `style_summary`, `contributing_md`, `pr_template`, `created_at`, `updated_at`).
