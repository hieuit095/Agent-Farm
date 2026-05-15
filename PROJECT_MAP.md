# PROJECT_MAP.md — Architecture Blueprint

This document serves as the canonical architectural blueprint for Farm-Agent v3.0+. It provides a deep-dive into the active technologies, directory structure, module dependency graph, core execution loops, and database state schema.

## 1. System Overview & Tech Stack

| Technology / Library | Role | Version Constraint |
| --- | --- | --- |
| **Python** | Primary programming language | `>= 3.11` |
| **Hatchling** | Build backend (PEP 517) | |
| **SQLite / aiosqlite** | Persistent state memory in WAL mode | `aiosqlite >= 0.19` |
| **ChromaDB** | Local RAG (Retrieval-Augmented Generation) indexing for context retrieval | `>= 0.4` |
| **Docker SDK** | Polyglot Sandbox Validation for testing code patches | `docker >= 7.1` |
| **Minimax** | Primary LLM Provider (code generation, analysis, PR evaluation) | |
| **OpenRouter** | Secondary LLM Provider (Red Team / Bloodhound White-Hat Audits) | |
| **Click** | CLI framework for orchestration commands | `>= 8.1` |
| **Rich** | Terminal formatting and rich TUI logs | `>= 13.0` |
| **Pydantic** | Configuration management & data validation | `>= 2.5` |
| **Httpx** | Async HTTP requests to GitHub API | `>= 0.27` |
| **Pytest** | Unit testing framework | `>= 8.0` |

## 2. Directory Structure

Below is an ASCII tree annotating the major directories and their primary roles in the `farm_agent` project structure.

```text
Farm-Agent/
├── farm_agent/                   # Core application root
│   ├── cli/                      # CLI entry points (Click commands)
│   │   └── main.py               # Main CLI commands (run, hunt, target, patrol, superhuman)
│   ├── core/                     # Foundational utilities and config
│   │   ├── config.py             # Pydantic configuration schemas
│   │   ├── memory.py             # Alias for orchestrator/memory.py or shared memory interfaces
│   │   ├── sandbox.py            # Docker Sandbox execution environment
│   │   └── rag.py                # ChromaDB vector index operations
│   ├── github/                   # GitHub interaction layer
│   │   ├── client.py             # Async GitHub REST/GraphQL API client (handles rate limits & secondary tokens)
│   │   ├── discovery.py          # Repository discovery mechanisms
│   │   └── security_gate.py      # Checks for private disclosure guidelines (Compliance Skip)
│   ├── orchestrator/             # Core pipelines and state management
│   │   ├── pipeline.py           # ContribPipeline: coordinates the full analysis -> generation -> PR flow
│   │   ├── human.py              # SuperHumanLoop: 24/7 daemon simulating human delays and PR quotas
│   │   └── memory.py             # SQLite persistence layer mapping (analyzed repos, PR outcomes)
│   ├── issues/                   # Issue-driven contribution logic
│   │   └── solver.py             # IssueSolver: fetches open issues, estimates complexity, deep multi-file planning
│   ├── analysis/                 # Codebase analysis
│   │   ├── analyzer.py           # CodeAnalyzer & BloodhoundAnalyzer for vulnerabilities and code quality
│   │   └── mapper.py             # RepoMapper for structural project skeleton mapping
│   ├── generator/                # AI Code Generation
│   │   ├── engine.py             # ContributionGenerator: creates multi-file diffs and commit messages
│   │   └── scorer.py             # QAHardcoreScorer: evaluates generated code in DEV-QA loop
│   ├── pr/                       # Pull Request management
│   │   ├── manager.py            # PRManager: submits PRs and checks compliance
│   │   ├── patrol.py             # PRPatrol: monitors open PRs, auto-responds to feedback, pushes fixes
│   │   └── janitor.py            # PRJanitor: sweeps and closes LLM-identified garbage PRs
│   ├── llm/                      # LLM Provider integrations
│   │   ├── provider.py           # Factory for instantiating LLM providers
│   │   └── router.py             # TaskRouter for multi-model task assignment
│   ├── notifications/            # External messaging
│   │   └── notifier.py           # Multi-channel push notifications (Telegram, Slack, Discord)
│   ├── agents/                   # Agent registry and definitions
│   ├── plugins/                  # Extensibility plugins
│   ├── templates/                # Contribution template definitions
│   └── tools/                    # Tool definitions and protocols
├── tests/                        # Unit tests for the application
├── pyproject.toml                # Project metadata and dependencies (Hatchling)
├── docker-compose.yml            # Docker services definition (sandbox networks)
├── README.md                     # High-level overview and instructions
└── PROJECT_MAP.md                # This architecture blueprint
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    %% CLI Entry Points
    CLI[CLI (farm_agent/cli/main.py)]

    %% Orchestrators
    SHL[SuperHumanLoop (orchestrator/human.py)]
    Pipe[ContribPipeline (orchestrator/pipeline.py)]
    Memory[(SQLite Memory (orchestrator/memory.py))]

    %% GitHub Integration
    GH[GitHubClient (github/client.py)]
    Disc[RepoDiscovery (github/discovery.py)]

    %% LLM & AI
    LLM[LLM Provider (llm/provider.py)]

    %% Analysis & Solvers
    ISolver[IssueSolver (issues/solver.py)]
    Analyzer[CodeAnalyzer / BloodhoundAnalyzer (analysis/analyzer.py)]

    %% Code Generation & Validation
    Gen[ContributionGenerator (generator/engine.py)]
    Sandbox[DockerSandbox (core/sandbox.py)]
    QAScorer[QAHardcoreScorer (generator/scorer.py)]

    %% Pull Requests
    PRMgr[PRManager (pr/manager.py)]
    PRPat[PRPatrol (pr/patrol.py)]
    Janitor[PRJanitor (pr/janitor.py)]

    %% Edges
    CLI -->|Starts| SHL
    CLI -->|Executes| Pipe
    CLI -->|Runs| PRPat
    CLI -->|Runs| Janitor

    SHL -->|Invokes| Pipe
    SHL -->|Uses| Memory

    Pipe -->|Initializes| Memory
    Pipe -->|Uses| GH
    Pipe -->|Uses| LLM
    Pipe -->|Calls| Disc
    Pipe -->|Routes| ISolver
    Pipe -->|Routes| Analyzer

    ISolver -->|Plans| Gen
    Analyzer -->|Feeds| Gen

    Gen -->|Uses| LLM
    Gen -->|Uses| RAG(ChromaDB Indexing)
    Gen -->|Generates Patch| Sandbox
    Gen -->|Checked by| QAScorer

    Sandbox -->|Validates Patch| PRMgr
    QAScorer -->|Approves Patch| PRMgr

    PRMgr -->|Submits| GH
    PRMgr -->|Records| Memory

    PRPat -->|Monitors| GH
    PRPat -->|Uses| Gen
    PRPat -->|Records| Memory
```

## 4. Core Execution Loops / Entry Points

Farm-Agent operates through a unified pipeline that coordinates GitHub discovery, LLM code generation, and sandboxed validation. The primary execution loops are:

### The Super Human Mode (`farm_agent superhuman`)
1. **Simulation Layer:** Randomly determines a daily PR quota and interleaves execution delays to mimic human work patterns (including lunch breaks and circadian rhythms).
2. **Circular Target Loop:** Repeatedly fetches targets via `DatabaseTargetDiscovery` from `target_repo.json` data stored in SQLite.
3. **Execution Pipeline:** Invokes the `ContribPipeline`.

### The `ContribPipeline` Flow
1. **Discovery:** Finds repositories via `RepoDiscovery` matching defined criteria (stars, language, recent activity).
2. **Pre-Filtering:** Checks for active AI bans (`AI_POLICY.md`), interaction limits, and private disclosure requirements (`security_gate.py`). Evaluates Maintainer vibe using LLMs on past comments.
3. **Issue-First Solving:** `IssueSolver` identifies solvable issues (e.g. `good first issue`), estimates complexity (1-5), and performs deep multi-file planning using a structural codebase map (`RepoMapper`).
4. **Static Analysis (Fallback):** If no issues exist, `CodeAnalyzer`/`BloodhoundAnalyzer` scan the file tree to uncover bugs, vulnerabilities, or code quality issues.
5. **Anti-Farming Gate:** Filters out trivial issues, documentation changes (`README_FIX`), and formatting improvements. Only `CRITICAL`, `HIGH`, `MEDIUM` vulnerabilities or targeted `FEATURE_ADD` pass.
6. **Code Generation:** `ContributionGenerator` uses the primary LLM to create specific code diffs (`FileChange`). A localized ChromaDB RAG index assists in cross-file context.
7. **DEV-QA Bounty Loop:** The `QAHardcoreScorer` grades the generated patch. If rejected, QA lessons are cached to persistent memory and generation restarts (max 3 cycles).
8. **Sandbox Guillotine:** The patch is deployed to an ephemeral Polyglot Docker Sandbox. The pipeline runs relevant CI commands (`npm test`, `pytest`, `cargo test`). If tests fail, it enters an automatic self-correction cycle.
9. **Pull Request Submission:** If all checks pass, `PRManager` commits the branch to a fork and raises the PR. Memory stores the outcome.

### PR Patrol (`farm_agent patrol`)
- Independently polls open PRs submitted by Farm-Agent.
- Scans maintainer review comments to categorize the required action (e.g., `CODE_CHANGE`, `QUESTION`, `CLA`, `STYLE_FIX`).
- Automatically generates and pushes new commits to address review feedback or automatically closes the PR if a hostile response is detected or reply limits are reached.

## 5. Database/State Schema

Farm-Agent utilizes SQLite with Write-Ahead Logging (WAL) to provide robust concurrent read/write state memory. Handled in `farm_agent/orchestrator/memory.py`.

### Key Tables

- **`analyzed_repos`**: Tracks repositories that have been fully analyzed to avoid repetitive scanning. Caches language, star count, and findings total.
- **`submitted_prs`**: Records all Pull Requests (and Issue Proposals) submitted. Tracks repository, PR number, title, contribution type, branch, and current status (`open`, `merged`, `closed`).
- **`pr_outcomes` & `repo_preferences`**: Analyzes the fate of PRs (`time_to_close_hours`, feedback). The agent learns to favor types of contributions in repositories where it successfully merges (`merge_rate`).
- **`knowledge_base`**: Stores 'QA Lessons' extracted from rejected code patches or maintainer feedback to prevent repeating the same architectural mistakes.
- **`target_repos`**: Stores the Circular Target Loop queue, processing targets sequentially and crash-safely updating their `scanned_at` timestamps.
- **`run_log` & `api_usage_log`**: Execution metrics and Token Pool tracking for rate limit management against LLM API quotas.
- **`blacklisted_repos`**: Permanently blocklists repositories based on maintainer hostility or AI policy rejections.
- **`repo_style_guides`**: Caches condensed style guides parsed from `CONTRIBUTING.md` and past PR feedback.
