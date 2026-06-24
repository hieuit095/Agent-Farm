# Agent-Farm Project Architecture Blueprint

This document provides a deep-dive architectural map of the active `farm_agent` codebase. It serves to orient developers to the system overview, tech stack, codebase structure, dependency graph, execution flows, and persistent state management.

## 1. System Overview & Tech Stack

Agent-Farm leverages an array of modern tools and frameworks to construct its autonomous pipeline:

| Technology | Purpose |
| --- | --- |
| **Python 3.11+** | Core runtime for the entire orchestration and CLI. |
| **Hatchling** | Build backend and project package manager. |
| **SQLite (aiosqlite)** | Persistent memory layer for PR tracking, analysis cache, and agent knowledge base. |
| **ChromaDB** | Local RAG store indexing codebase maps for context-aware resolutions. |
| **Docker (docker-py)** | Spin up isolated sandboxes (`sandbox_isolated` network) for dynamic execution and verification. |
| **LLM Providers** | OpenRouter, OpenAI, Anthropic, Minimax (DeepSeek, Qwen, Gemini models) to perform analysis and generate code. |
| **Click & Rich** | CLI framework, argument parsing, formatting, and interactive terminal tables. |
| **Pydantic** | Configuration modeling, environment management, and data validation. |
| **GitPython** | Cloning repositories, patching, and branching inside the sandbox. |

## 2. Directory Structure

Below is an ASCII tree of the active `farm_agent` module:

```text
farm_agent/
├── agents/             # Handlers and definitions for agent roles
│   └── registry.py     # DeerFlow custom agent registry pattern
├── analysis/           # Codebase parsing, abstract syntax tree (ast-grep) integration
├── cli/
│   └── main.py         # Entrypoint for CLI commands (run, target, solve, patrol, etc.)
├── core/               # Configuration, middleware, and low-level system elements
│   ├── config.py       # Pydantic settings loading from config.yaml & .env
│   ├── logger.py       # Centralized file and rich terminal logging
│   ├── memory.py       # Orchestrator persistent memory setup and SQLite migrations
│   ├── rag.py          # ChromaDB RAG mappings and retrieval logic
│   └── sandbox.py      # Docker execution environment instantiation
├── generator/          # Modules for generating concrete patch files or PR texts
├── github/             # Interaction layer for GitHub APIs
│   ├── client.py       # API abstraction (repo discovery, PR submission)
│   └── security_gate.py# Discovers security policies and avoids private disclosure repos
├── issues/             # Target-issue oriented processing
│   └── solver.py       # Logic for picking, filtering, and resolving GitHub issues
├── llm/                # Adapter layers for various LLM capabilities
│   ├── models.py       # Model definitions and task categorization
│   ├── provider.py     # Provider instantiation Factory
│   └── router.py       # Routes tasks to optimal LLMs
├── notifications/      # Notifications out to webhooks (Slack, Discord, Telegram)
├── orchestrator/       # The central logic pipelines driving Agent-Farm execution
│   ├── human.py        # Super Human / Terminator mode operational loop
│   ├── memory.py       # Persistent database interactions (SQLite memory.db)
│   └── pipeline.py     # The primary target, analyze, and submission flow
├── plugins/            # Extensible plugins for various custom behaviors
├── pr/                 # Post-generation logic
│   ├── patrol.py       # PR review loop, addressing feedback automatically
│   └── manager.py      # Handles merging/closing PRs and updating the DB status
├── templates/          # Contribution formatting and registry
└── tools/              # Standalone utility functions used by the agents
```

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (farm_agent/cli/main.py)] --> Pipeline[Orchestrator Pipeline]
    CLI --> HumanLoop[Super Human / Terminator Loop]
    CLI --> Patrol[PR Patrol]

    Pipeline --> GitHubClient[GitHub API Client]
    Pipeline --> Solver[Issue Solver]
    Pipeline --> Analysis[Code Analyzer]

    HumanLoop --> Pipeline
    HumanLoop --> Patrol

    Solver --> Sandbox[Docker Sandbox]
    Solver --> LLMRouter[LLM Provider / Router]

    Analysis --> Sandbox
    Analysis --> LLMRouter

    Patrol --> GitHubClient
    Patrol --> LLMRouter
    Patrol --> Memory[SQLite / ChromaDB]

    Pipeline --> Memory
    Solver --> Memory
```

## 4. Core Execution Loops / Entry Points

The fundamental starting point for the tool is the `farm_agent` CLI wrapper calling `farm_agent/cli/main.py`.

### Primary Workflow (e.g., `farm_agent run` / `farm_agent target`)
1. **Configuration Setup**: Pydantic loads `.env` variables and `config.yaml`.
2. **Repository Discovery/Fetch**: The `GitHubClient` searches or accesses the target repository.
3. **Security Gate**: The system evaluates `.github/SECURITY.md` or similar meta-files. If private disclosure phrases exist, the pipeline aborts for this repository.
4. **Codebase RAG Indexing**: `farm_agent/core/rag.py` ingests codebase context to ChromaDB for localized querying.
5. **Issue Sourcing / Analysis**: Either `farm_agent.issues.solver` fetches open issues, or `farm_agent.analysis` scans for new optimization opportunities.
6. **Task Routing**: `LLMRouter` delegates the work to a specialized model (e.g., Gemini for Layer 2 auditing).
7. **Sandbox Verification**: Code patches are created, and `DockerSandbox` runs relevant checks/tests isolated from the host machine.
8. **PR Generation**: Commits are pushed, and `GitHubClient` opens a PR. Details are logged into persistent SQLite memory.

### PR Patrol Flow (`farm_agent patrol`)
1. Fetches "open" PRs submitted by Agent-Farm from SQLite memory.
2. The GitHub client checks for new comments or reviews from maintainers.
3. The LLM formulates replies or generates code corrections.
4. Pushes changes to the existing branch or posts comments.

## 5. Database/State Schema (`memory.db`)

Agent-Farm leverages an SQLite instance, typically initialized by `Memory.init()` in `farm_agent/orchestrator/memory.py`. Key tables include:

- **`analyzed_repos`**: Keeps a log of repositories that have undergone Code Analyzer scanning.
- **`submitted_prs`**: Crucial table containing all PR metadata (`pr_number`, `repo`, `status`, `created_at`, `updated_at`). Used heavily by PR Patrol and Cleanup tasks.
- **`run_log`**: Tracks execution history and basic metrics for statistical reporting.
- **`target_repos`**: Tracks dynamically discovered targets waiting for processing (used heavily by Circular Target Loop).
- **`knowledge_base`**: Stores insights and accumulated history (with a Garbage Collection loop purging items older than 90 days).
- **`findings_cache`**: Caches specific bugs/issues discovered in repositories to avoid redundant scans.
- **`blacklisted_repos` & `repo_preferences`**: Configuration overrides and exclusions tailored dynamically per repository based on historical success or failure.