# Farm-Agent Project Map

This document serves as a deep-dive architectural guide and structural map for the Farm-Agent project, providing an objective overview of its codebase, component flows, and data structures.

## 1. System Overview & Tech Stack

| Component               | Technology / Service | Description                                                                                   |
| ----------------------- | -------------------- | --------------------------------------------------------------------------------------------- |
| **Core Language**       | Python >= 3.11       | The primary implementation language, providing typing, async capabilities, and scripting speed. |
| **Orchestration**       | asyncio              | Manages concurrent repository pipelines, LLM calls, and external API requests.                |
| **CLI Framework**       | Click / Rich         | Drives the user interface, logging, and command parsing logic.                                |
| **Code Understanding**  | ast-grep / Semgrep   | Identifies anti-patterns, code vulnerabilities, and context-specific AST nodes.               |
| **LLM Inference**       | OpenRouter / Minimax | Routes tasks to the best-fit large language model based on required context (e.g., Qwen, Gemini, DeepSeek).  |
| **Database**            | SQLite (aiosqlite)   | Persistent state management holding run logs, PR outcomes, execution schedules, and learning data. |
| **Container Sandbox**   | Docker >= 7.1        | Polyglot execution sandbox for Proof-of-Concept testing, regression testing, and code validation. |
| **RAG Component**       | ChromaDB             | Local vector database used to store repository style guidelines and documentation indexes.    |
| **Version Control API** | GitHub API / GitPython | Powers repository discovery, code diffing, file fetching, and PR lifecycle management.        |

## 2. Directory Structure

```ascii
Farm-Agent/
├── .github/                # GitHub-specific workflows and meta-files
├── farm_agent/             # Core application package
│   ├── agents/             # Task-specific agents (DeerFlow components)
│   ├── analysis/           # Codebase parsing, mapping, and vulnerability scanning
│   ├── cli/                # Command Line Interface routing and commands
│   ├── core/               # Configuration, logging, exception models, and utilities
│   ├── generator/          # Patch generation logic and Proof-of-Concept builders
│   ├── github/             # GitHub API client, discovery rules, and security gating
│   ├── issues/             # Issue classification and multi-file solvers
│   ├── llm/                # Model abstraction, token tracking, and provider integrations
│   ├── notifications/      # Alert routing to external services (Slack, Discord, Telegram)
│   ├── orchestrator/       # The pipeline, Super Human loop, and persistent memory DB
│   ├── plugins/            # Extensibility plugins
│   ├── pr/                 # PR generation, Patrol (auto-healing), and Janitor (sweeper)
│   ├── templates/          # Standard contribution template registries
│   └── tools/              # Toolkit configurations for agents
├── scripts/                # Development and environment utilities
├── tests/                  # Unit and integration test suites
├── Dockerfile              # Docker image definition for Farm-Agent isolated deployment
├── docker-compose.yml      # Service composition including required networks and volumes
├── Makefile                # Dev automation (install, test, lint, build, docker)
├── pyproject.toml          # Project metadata, Hatchling build backend, and Ruff configuration
├── requirements.txt        # Base dependencies including pip constraints
├── start.bat               # Windows Quick-Start
└── start.sh                # Unix Quick-Start
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent.cli.main)] --> Orchestrator[Orchestrator Pipeline]
    CLI --> SuperHuman[Super Human Loop]
    CLI --> Patrol[PR Patrol]

    Orchestrator --> Memory[(SQLite DB)]
    Orchestrator --> GitHub[GitHub Client]
    Orchestrator --> CodeAnalyzer[Code Analyzer / Bloodhound]
    Orchestrator --> IssueSolver[Issue Solver]
    Orchestrator --> Gen[Contribution Generator]
    Orchestrator --> PRManager[PR Manager]
    Orchestrator --> RAG[(ChromaDB)]

    SuperHuman --> Orchestrator
    Patrol --> GitHub
    Patrol --> LLM[LLM Provider]

    CodeAnalyzer --> LLM
    Gen --> Sandbox[Docker Sandbox]
    Gen --> LLM
    IssueSolver --> GitHub
    IssueSolver --> LLM
    PRManager --> GitHub

    Sandbox --> Gen: Feedback / Validation Logs
```

## 4. Core Execution Loops / Entry Points

The primary execution flows begin from `farm_agent/cli/main.py`, invoking the pipeline defined in `farm_agent/orchestrator/pipeline.py`.

### A. Hunt / Pipeline Loop (`hunt`)
1. **Discovery:** Scans GitHub or the local `target_repos` database for repositories matching configuration rules.
2. **Analysis:** Runs static analysis (`BloodhoundAnalyzer`) to locate vulnerabilities or queries open issues (`IssueSolver`).
3. **Filtering:** Applies the `Anti-Farming Filter` and `Security Disclosure Gate` to remove false positives and trivial changes.
4. **Generation & QA:** The `ContributionGenerator` proposes a fix. A QA sub-agent evaluates the patch.
5. **Sandbox Validation:** The `DockerSandbox` runs a dynamic PoC exploit and local tests (Regression Checks) on the modified code. If tests fail, it attempts self-correction.
6. **Submission:** Upon successful validation, the agent pushes the patch to a branch on a fork and opens a Pull Request.

### B. PR Patrol Loop (`patrol`)
1. **Ingestion:** Fetches all open PRs created by the bot.
2. **Review Feedback Parsing:** Reads maintainer comments using the GitHub API, passing them to the LLM to classify feedback (e.g., code changes, questions, hostility).
3. **Action:** Modifies code based on feedback, replies contextually to questions, or signs a CLA if required.
4. **Auto-Healing:** If CI checks fail on the open PR, it fetches the traceback and attempts an automated sandbox-validated fix.

### C. Super Human Loop (`superhuman`)
1. An infinite `asyncio` execution loop combining the Pipeline and PR Patrol.
2. Dynamically alters contribution quotas per day, executing long variable delays (WPM simulator) to avoid machine-like bursts.
3. Automatically transitions to issue patrol when the daily quota is exhausted.

## 5. Database/State Schema

Farm-Agent uses an `aiosqlite` backend (`memory.db`) to persist knowledge, caching, and rate limiting data.

- `analyzed_repos`: Tracks previously analyzed repositories to prevent redundant scans.
- `submitted_prs`: Logs PR submissions alongside meta information like branch paths and retry attempts.
- `findings_cache`: Caches vulnerability scanner findings.
- `run_log`: Historical metrics on repos processed, PRs created, and total errors per run.
- `pr_outcomes`: Tracks PR resolutions (merged vs. closed) to compute success rates.
- `repo_preferences`: Caches style guides and rejected templates for individual repositories.
- `blacklisted_repos`: Forbids repositories due to hostile interactions or interaction limits.
- `api_usage_log`: Logs OpenRouter or Minimax API calls for local rate limiting.
- `task_schedule`: Tracks time-based tasks and delayed event hooks.
- `knowledge_base`: Persists LLM feedback loops, recording Layer 1 / Layer 2 rejections and code review QA lessons.
- `target_repos`: A queuing table for predefined target repositories (used by the `hunt-circular` loop).
- `repo_style_guides`: Summarizes `CONTRIBUTING.md` rules and project styling guidelines for code generation.
