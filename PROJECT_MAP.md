# Agent-Farm Architecture Blueprint

This document serves as a deep-dive architectural guide for Agent-Farm. It reflects the raw reality of the codebase and outlines the system overview, directory structure, core module dependencies, execution loops, and database schema.

## 1. System Overview & Tech Stack

| Technology | Role in Project |
| :--- | :--- |
| **Python 3.11+** | Core programming language. |
| **Docker 7.1+** | Used to run the dynamic bug verification and regression sandboxes locally in isolation. |
| **Hatchling** | Build backend and project management (`pyproject.toml`). |
| **aiosqlite** | Asynchronous SQLite database connector used for the persistent memory system. |
| **click & rich** | Powers the comprehensive and highly-styled Command Line Interface. |
| **gitpython** | Handles programmatic interactions with the local git repository (e.g., creating branches, pushing code). |
| **chromadb** | Used by the Omniscient Context Engine to semantically index repository subsystem documentation for RAG. |
| **google-genai, openai, anthropic** | Integrations for interacting with various LLM models (e.g., Gemini, OpenAI, Claude). |

## 2. Directory Structure

```ascii
farm_agent/
├── agents/            # Registry and definitions for specialized AI agents
├── analysis/          # Code analysis engine (Bloodhound, Semgrep, AST-grep)
├── cli/               # Command-Line Interface built with Click and Rich
│   └── main.py        # Main CLI entry point
├── core/              # Core utilities, configurations, and middleware
│   ├── config.py      # Pydantic-based configuration management
│   ├── exceptions.py  # Custom exception classes
│   └── ...
├── generator/         # Code generation and QA Loop
│   ├── engine.py      # Core generator logic
│   └── scorer.py      # QA scorer for the DEV-QA loop
├── github/            # Interactions with the GitHub API
│   ├── client.py      # Async HTTP client for GitHub
│   ├── discovery.py   # Repository discovery logic
│   └── security_gate.py # Security disclosure gate
├── issues/            # Issue-solving logic
│   └── solver.py      # Logic to parse and solve GitHub issues
├── llm/               # LLM provider abstractions and routing
│   ├── provider.py    # Factory and provider implementations
│   └── router.py      # Multi-model routing
├── notifications/     # Notifications logic (e.g., Telegram)
├── orchestrator/      # High-level pipeline and loops
│   ├── human.py       # Super Human Mode loop
│   ├── memory.py      # Persistent SQLite memory operations
│   └── pipeline.py    # The main FarmAgentPipeline orchestrator
├── plugins/           # Extension plugins
├── pr/                # Pull Request management and patrolling
│   ├── manager.py     # Logic for opening and managing PRs
│   ├── patrol.py      # PR Patrol for addressing feedback
│   └── janitor.py     # PR Janitor for sweeping garbage PRs
├── templates/         # Contribution templates
└── tools/             # Tool definitions for the agents
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent.cli.main)] --> Orchestrator[Orchestrator (farm_agent.orchestrator.pipeline)]
    CLI --> HumanLoop[Super Human Loop (farm_agent.orchestrator.human)]
    HumanLoop --> Orchestrator

    Orchestrator --> GitHub[GitHub Client (farm_agent.github.client)]
    Orchestrator --> Memory[(SQLite Memory (farm_agent.orchestrator.memory))]
    Orchestrator --> Analyzer[Analyzer (farm_agent.analysis.analyzer)]
    Orchestrator --> Generator[Generator (farm_agent.generator.engine)]

    Analyzer --> LLM[LLM Provider (farm_agent.llm.provider)]
    Generator --> LLM

    Orchestrator --> Sandbox{Docker Sandbox}

    Orchestrator --> PRManager[PR Manager (farm_agent.pr.manager)]
    PRManager --> GitHub
```

## 4. Core Execution Loops / Entry Points

### The Pipeline (`FarmAgentPipeline`)

This is the primary flow when targeting a repository:

1. **Discovery**: Identifies candidate repositories via `RepoDiscovery` or `DatabaseTargetDiscovery` (using the GitHub API).
2. **Analysis**: Uses the `CodeAnalyzer` (specifically `BloodhoundAnalyzer`) to scan the codebase for vulnerabilities. It also filters out spam/low-impact issues using an Anti-Farming Filter.
3. **Layer 1 Appraisal**: Findings are passed to an LLM appraiser to verify if the vulnerability is genuine and high/critical.
4. **Generation (DEV-QA Loop)**: `ContributionGenerator` generates a code fix. The code undergoes rigorous internal QA.
5. **Sandbox Verification**: The patch and generated Proof-of-Concept are executed in the `DockerSandbox`. The patch must fix the PoC and pass regression tests.
6. **Layer 2 Audit**: A supreme auditor LLM (e.g., Gemini) reviews the entire dossier and sandbox logs before final approval.
7. **PR Submission**: `PRManager` submits the Pull Request via the GitHub API.

### Super Human Mode (`SuperHumanLoop`)

This loop is designed to run 24/7 autonomously:

1. Wakes up and sets a random daily PR quota to simulate human unpredictability.
2. Interleaves rounds of the `FarmAgentPipeline` (Hunting/Targeting) with `PRPatrol` (checking for and replying to maintainer comments).
3. Injects unpredictable, organic delays (sleeping) to respect API rate limits and avoid robotic patterns.
4. Shifts to patrol-only mode once the daily PR quota is reached.

## 5. Database/State Schema

State is maintained via an asynchronous SQLite database managed in `farm_agent/orchestrator/memory.py`.

### Key Tables

*   **`analyzed_repos`**: Tracks repositories that have already been scanned to avoid redundant work.
*   **`submitted_prs`**: Records all Pull Requests opened by the agent, tracking their status (open, merged, closed).
*   **`run_log`**: Logs statistics for each pipeline run (repos analyzed, PRs created, findings, errors).
*   **`api_usage_log`**: Tracks LLM API usage to enforce quotas and prevent hitting secondary rate limits.
*   **`knowledge_base`**: Stores past QA critiques and Filter rejections to improve future code generation (learning mechanism).
*   **`target_repos`**: Powers the circular target loop, ensuring a deterministic round-robin selection of repositories to process.

## 6. Directory & Module Architecture

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
│   │   ├── exceptions.py               # System exception types hierarchy
│   │   ├── leaderboard.py              # Leaderboard stat collections
│   │   ├── logger.py                   # Rotating file logging system setup
│   │   ├── middleware.py               # Context middleware chain layers
│   │   ├── models.py                   # Core Pydantic data structures definitions
│   │   ├── notifier.py                 # Telegram notifications integration
│   │   ├── profiles.py                 # Thorough, quick, and standard run configurations
│   │   ├── quotas.py                   # OpenRouter usage quota controllers
│   │   ├── rag.py                      # ChromaDB vector DB context loaders
│   │   └── sandbox.py                  # DockerSandbox engine with Polyglot Guillotine
│   │
│   ├── analysis/
│   │   ├── analyzer.py                 # CodeAnalyzer & BloodhoundAnalyzer
│   │   └── mapper.py                   # RepoMapper (AST/regex dependency graphing)
│   │
│   ├── generator/
│   │   ├── engine.py                   # ContributionGenerator (Patch and file correction)
│   │   ├── poc.py                      # PoCGenerator (PoC validation & LLM evaluation)
│   │   ├── reviewer.py                 # ReviewerAgent
│   │   └── scorer.py                   # QAHardcoreScorer
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
│   │   ├── agents.py                   # LLM agent prompts and routing models
│   │   ├── context.py                  # Generator system instruction builders
│   │   ├── models.py                   # Model registry definitions
│   │   ├── provider.py                 # OpenRouter integration handlers
│   │   └── router.py                   # Task router mapping
│   │
│   ├── orchestrator/
│   │   ├── memory.py                   # Persistence memory sqlite connection interface
│   │   ├── pipeline.py                 # Pipeline orchestrator
│   │   └── human.py                    # SuperHumanLoop relentless daily scheduler
│   │
│   ├── pr/
│   │   ├── manager.py                  # Pull Request manager (forking, branches, commits)
│   │   ├── patrol.py                   # PR Patrol (reviews comments, fixes CI errors)
│   │   └── janitor.py                  # PR Janitor (sweeps and destroys garbage PRs)
│   │
│   ├── agents/
│   │   └── registry.py                 # Task agent configurations
│   │
│   └── tools/
│       └── protocol.py                 # CLI tool protocols
```
