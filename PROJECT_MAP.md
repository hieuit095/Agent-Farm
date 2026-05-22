# PROJECT_MAP.md — Farm-Agent Architectural Blueprint

This document provides a deep-dive architectural map of the Farm-Agent codebase, reflecting the true state and inner workings of the active codebase.

## 1. System Overview & Tech Stack

Farm-Agent is a fully autonomous AI agent designed to discover open-source GitHub repositories, identify meaningful issues (e.g., security vulnerabilities, code quality bugs), generate precise patches via LLMs, validate patches within a polyglot Docker sandbox, and create Pull Requests (PRs) or GitHub Issues.

### Active Tech Stack

| Component | Technology | Description |
|-----------|------------|-------------|
| Language | Python 3.11+ | The entire system is built in modern Python, leveraging `asyncio`. |
| Orchestrator | DeerFlow Architecture | A custom registry-based agent and tool middleware built specifically for Farm-Agent. |
| HTTP Client | `httpx` (async) | Manages asynchronous API calls (e.g., to GitHub REST and GraphQL). |
| LLM Providers | MiniMax (default), OpenRouter, Gemini, OpenAI, Anthropic | Code generation, bug analysis, PR summarization, and RAG capabilities. Configurable via `config.yaml`. |
| Database / Memory | SQLite via `aiosqlite` | Persistent memory mapping repo stats, target loops, PR outcomes, quotas, and logs in WAL mode. |
| Patch Validation | `docker` (>= 7.1) | Isolated sandboxing environments used to execute and validate generated code patches across 12+ programming languages. |
| Configuration | `pydantic` v2 + `pyyaml` | Strongly-typed configurations initialized from `.env`, `config.yaml`, and explicit profiles. |
| Vector DB (RAG) | `chromadb` (local) | Contextual memory and semantic search to aid in patch validation across multiple files. |
| CLI / TUI | `click` + `rich` | The primary operational interfaces containing commands like `hunt`, `run`, `superhuman`, `patrol`, and `janitor`. |

## 2. Directory Structure

This structure represents the core, active components of Farm-Agent, omitting trivial and removed logic.

```
farm_agent/
├── cli/
│   └── main.py              # Click-based CLI entry point defining all operational commands.
├── core/
│   ├── config.py            # Pydantic configuration definitions.
│   ├── exceptions.py        # Custom exceptions for pipeline failure states.
│   ├── middleware.py        # DeerFlow pattern middleware execution engine.
│   ├── memory.py            # SQLite database interactions and persistent storage schema.
│   ├── rag.py               # ChromaDB-based retrieval logic.
│   └── sandbox.py           # Docker isolation ("Sandbox Guillotine") for patch validation.
├── generator/
│   ├── engine.py            # The ContributionGenerator creating patches from findings.
│   └── scorer.py            # QA evaluation loop logic and code critiques.
├── github/
│   ├── client.py            # GitHub API implementations (REST + GraphQL with retry wrappers).
│   ├── discovery.py         # Logic for finding new repositories or picking from a circular loop.
│   ├── guidelines.py        # Parsing logic for CONTRIBUTING.md and PR templates.
│   └── security_gate.py     # Parses SECURITY.md files to respect private disclosures.
├── analysis/
│   ├── analyzer.py          # Static CodeAnalyzer leveraging LLMs.
│   └── bloodhound.py        # Semgrep and Red-Team pre-scanning logic.
├── llm/
│   ├── provider.py          # LLM instantiation and provider interfaces.
│   ├── models.py            # Model definitions, cost logic, and task-specific routing.
│   └── router.py            # Intelligent model routing depending on task type.
├── issues/
│   └── solver.py            # Issue-First Pipeline prioritizing existing repository issues over static scan findings.
├── orchestrator/
│   ├── pipeline.py          # The master ContribPipeline that connects Discovery -> Analysis -> Gen -> PR.
│   ├── human.py             # SuperHumanLoop defining the 24/7 human-like autonomous operational loop.
│   └── memory.py            # (Alias mapping to core/memory.py)
├── pr/
│   ├── manager.py           # Handles branch creation, commits, PR submissions, and auto-fixes.
│   ├── patrol.py            # Re-evaluates open PRs, auto-responds to feedback, pushes CLA signatures.
│   └── janitor.py           # Scans and purges low-quality, garbage, or stale PRs.
├── agents/                  # DeerFlow Agent definitions.
├── notifications/           # System webhooks (Slack/Discord/Telegram).
├── templates/               # Standardized PR templates.
└── tools/                   # DeerFlow Tool integrations.
```

## 3. Core Module Dependency Graph

```mermaid
graph TD;
    CLI[CLI (main.py)] --> Pipeline[ContribPipeline];
    CLI --> SuperHuman[SuperHumanLoop];

    SuperHuman --> Pipeline;
    SuperHuman --> PRPatrol[PR Patrol];

    Pipeline --> Discovery[Repo Discovery];
    Pipeline --> GithubClient[GitHub Client];
    Pipeline --> Analyzer[Code Analysis & Bloodhound];
    Pipeline --> IssueSolver[Issue Solver];
    Pipeline --> Generator[Contribution Generator];
    Pipeline --> Memory[SQLite Memory];

    Analyzer --> LLMProvider[LLM Provider];
    IssueSolver --> LLMProvider[LLM Provider];

    Generator --> Sandbox[Docker Sandbox];
    Generator --> LLMProvider[LLM Provider];

    Sandbox --> PRManager[PR Manager];
    PRManager --> GithubClient;
    PRManager --> Memory;
```

## 4. Core Execution Loops & Entry Points

The primary entry point is the CLI (`farm_agent/cli/main.py`), utilizing commands to execute variations of the pipeline.

### Standard Pipeline Flow (`run` and `target` commands)
Located in `farm_agent/orchestrator/pipeline.py`.

1. **Discovery:** Identifies a repository or list of repositories based on specific parameters (`stars`, `language`).
2. **Gate:** Checks against `AI_POLICY.md`, protected meta-files, interaction limits, the Security Disclosure Gate, and filters trivial/farming findings.
3. **Analysis / Issue Fetching:** Analyzes files via the Bloodhound analyzer or fetches and categorizes solvable open issues (Issue-First Pipeline).
4. **DEV-QA Bounty Loop (Generation):** Prompts the LLM to write a patch. It involves up to 3 Dev-QA cycles using the `QAHardcoreScorer`.
5. **Sandbox Validation:** Mandates the code runs in an isolated, ephemeral Docker container. Failure initiates an LLM self-correction loop.
6. **PR Creation:** Forks, branches, pushes changes, and creates a GitHub Pull Request or an Issue Proposal if appropriate.

### Super Human Mode Flow
Located in `farm_agent/orchestrator/human.py`.

1. An autonomous 24/7 loop runs.
2. Evaluates daily PR quotas and schedules tasks.
3. Interleaves aggressive `Hunt` actions, `PR Patrol` sweeps to respond to feedback, and introduces organic delays (simulated lunch breaks, coding pauses) to prevent secondary rate limits and mimic a human schedule.

## 5. Database & State Schema

The persistent state is maintained using SQLite (`aiosqlite`) located via `storage.db_path` config (default `data/memory.db`) with WAL journal mode enabled.

Located in `farm_agent/orchestrator/memory.py`:

- **`analyzed_repos`**: Keeps a history of scanned repositories to prevent redundant analysis.
- **`submitted_prs`**: Stores all agent-submitted PRs, URLs, branch names, and metadata like CI fix attempts and discussion reply counts.
- **`pr_outcomes` & `repo_preferences`**: Tracks the long-term history of what merged, what failed, and why. Used for Repo Learning (Alumni Sync).
- **`run_log`**: Audit trail of every pipeline execution.
- **`blacklisted_repos`**: Tracks repositories that explicitly requested exclusion or exhibited hostile behavior.
- **`api_usage_log`**: Manages sliding-window quotas for LLM usage to prevent runaway costs.
- **`target_repos`**: Manages the circular rotation queue of targets.
- **`knowledge_base`**: RAG-style lesson repository indexing past QA failures to prevent the generator from making the same mistakes twice.
