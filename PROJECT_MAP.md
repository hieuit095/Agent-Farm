# 🗺️ Farm-Agent Project Blueprint

This document serves as a comprehensive architectural guide for new developers looking to understand the inner workings of Farm-Agent. It is strictly based on the real implementation of the codebase.

---

## 1. System Overview & Tech Stack

| Technology / Component | Role in Project |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| **Python 3.11+**       | The core language enforcing modern syntax and structured exception handling natively via `farm_agent.core.exceptions`.              |
| **Click & Rich**       | Powers the interactive, visually complex Command-Line Interface (`farm_agent/cli/main.py`) alongside dashboard/TUI functionalities. |
| **Hatchling**          | Primary modern Python build backend utilized via `pyproject.toml`.                                                                  |
| **Docker Engine (7.1+)**| Backs the `Polyglot Sandbox` (`DockerSandbox`), providing isolated, language-specific containers to validate compiled code or tests. |
| **SQLite (aiosqlite)** | Persistent, thread-safe (WAL mode enabled) local memory database storing interaction history, PR metadata, and "Alumni Repos".      |
| **ChromaDB**           | Ephemeral (RAM-only) Local Retrieval-Augmented Generation (RAG) backend mapped to codebase tokens for deep context resolution.      |
| **LLM Provider API**   | Model router (supports Minimax, Gemini, OpenAI, etc.) that directs tasks for code analysis, patch generation, and review responses. |
| **GitHub REST API**    | Handled efficiently via HTTPX (`GitHubClient`), performing discovery, PR creation, file reading, and PR interactions with rate-limiting constraints. |

---

## 2. Directory Structure

```text
farm_agent/
├── cli/
│   ├── main.py                # Main CLI entrypoint (commands: run, target, hunt, solve, superhuman, etc.)
│   └── tui.py                 # Optional interactive text UI
├── core/
│   ├── config.py              # Centralized Pydantic-based configuration system
│   ├── exceptions.py          # Custom exception hierarchy (e.g., GitHubAPIError, ContextMissingError)
│   ├── middleware.py          # DeerFlow pattern middleware execution for enforcing PR quality gates
│   ├── models.py              # System-wide Pydantic dataclasses (Finding, Contribution, PipelineResult)
│   ├── sandbox.py             # DockerSandbox implementation; handles polyglot containerized patch testing
│   └── memory.py              # SQLite wrapper for orchestrating 'Memory' (DB context)
├── orchestrator/
│   ├── pipeline.py            # Primary `ContribPipeline`: manages the discovery -> analysis -> PR lifecycle
│   └── human.py               # `SuperHumanLoop`: scheduling mechanisms mimicking realistic human patterns
├── analysis/
│   └── analyzer.py            # Code Analyzer using the LLM and specific strategies to inspect targets
├── generator/
│   └── engine.py              # Contribution Generator: builds patches/commits from verified findings
├── github/
│   ├── client.py              # Async HTTPX wrapper around the GitHub REST API
│   └── discovery.py           # Logic for hunting repositories based on star counts, activity, languages
├── issues/
│   └── solver.py              # Deep-solver module analyzing specific open issues and correlating context
├── llm/
│   ├── provider.py            # Instantiates the underlying LLM interface based on configuration
│   └── router.py              # Routes specialized tasks (coding, analysis) to the most cost-effective models
├── pr/
│   ├── manager.py             # Generates pull requests, commits, branches, and auto-checks CI compliance
│   └── patrol.py              # System daemon to auto-read PR comments and push LLM-generated fixes
└── web/                       # Backend serving the local Dashboard view of system statistics
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    %% Entry Points
    A[CLI (`cli/main.py`)] --> B(ContribPipeline)
    A --> SH(SuperHumanLoop)

    SH -.-> B

    %% Main Orchestration
    B -->|Discover| C[RepoDiscovery]
    B -->|Analyze| D[CodeAnalyzer / IssueSolver]
    B -->|Persist state| DB[(SQLite Memory)]

    %% API Connectors
    C --> GH[GitHubClient]
    D --> GH

    %% Code Gen Flow
    D -->|Yields Validated Findings| E[ContributionGenerator]
    E -->|Needs context| LLM[LLM Provider Router]
    E -->|Needs semantic lookup| RAG[ChromaDB RAG]

    %% Sandbox Guard
    E -->|Generates patch| F[DockerSandbox]
    F -->|Container Validation| F_Gate{Tests Pass?}

    %% Pull Request Management
    F_Gate -->|Yes| G[PRManager]
    F_Gate -->|No| E
    G -->|Create Branch/Commit| GH

    %% Post-Action
    G -->|Monitor| P[PRPatrol]
```

---

## 4. Core Execution Loops / Entry Points

### 1. The Standard Pipeline Execution (`farm_agent run`)
1. **Bootstrap:** The `cli` module parses arguments and initializes the `ContribPipeline`.
2. **Discovery:** The `RepoDiscovery` module queries GitHub for active repositories matching the configured star bounds and language priorities.
3. **Filtering:** Repositories are matched against the local SQLite database to prevent redundant crawling. The `Analyzer` additionally checks the "Maintainer Vibe" to skip toxic repositories.
4. **Analysis / Issues First:** The `IssueSolver` attempts to find actively opened issues. If unviable, `CodeAnalyzer` falls back to general static codebase inspection.
5. **Anti-Farming Gate:** Trivially low-value fixes (documentation only, format-level typos) are explicitly discarded.
6. **Code Generation:** `ContributionGenerator` works with the LLM to write code.
7. **Sandbox Execution:** The `DockerSandbox` creates a fleeting Docker container containing the target repository's environment (Node, Rust, Python, etc.) and tests the LLM's patch. If it fails, an auto-correct loop tries again up to 3 times.
8. **PR Creation:** `PRManager` writes the branch, pushes the changes, and initiates the Pull Request against the target repository, recording its status to the local Memory DB.

### 2. SuperHuman 24/7 Loop (`farm_agent superhuman`)
- Mimics a "Human Employee".
- Starts its day dynamically, decides a random "quota" of PRs for the day.
- Spends periods running standard discovery and PR-making.
- Simulates realistic keyboard typing latency using `asyncio.sleep()`.
- Engages the `PRPatrol` module periodically to respond to human code review comments on existing PRs.

---

## 5. Database & State Schema
The project manages its state purely through a local SQLite database (defaulting to WAL mode for concurrent access) accessed via `aiosqlite` in `farm_agent/orchestrator/memory.py`.

- **`run_log`:** Stores global pipeline execution metrics (Runs, PRs generated, Total findings).
- **`analyzed_repos`:** Deduplication ledger ensuring the bot doesn't spam identical repositories frequently.
- **`submitted_prs`:** Tracks the lifecycle (Open, Closed, Merged) of specific PR IDs associated with target URLs to calculate leaderboards and success rates.
- **`repo_preferences` (Alumni Repo Sync):** Persists "friendly" repos where PRs were successfully merged, ensuring these are prioritized during future hunts.
- **`findings_cache`:** Stores intermediate insights to reduce identical LLM reprocessing overheads.