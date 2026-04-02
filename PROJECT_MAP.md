# Architecture Blueprint & Project Map

This document serves as the architectural blueprint for the Farm-Agent codebase. It outlines the core components, directory structures, and execution flows.

## 1. System Overview & Tech Stack

| Component | Technology | Role in System |
|---|---|---|
| **Core Language** | Python (3.11+) | The foundation of the agent. Used for all primary logic and orchestration. |
| **Build System** | Hatchling | Modern Python build backend specified in `pyproject.toml`. |
| **CLI Framework** | Click | Powers the main interface and command-line parsing. |
| **Formatting/UI** | Rich | Provides color, styling, and structured output (panels/tables) for the terminal. |
| **API Client** | HTTPX | Used to handle asynchronous, non-blocking requests to the GitHub API. |
| **Memory / Storage** | SQLite (`aiosqlite`) | Provides a persistent memory layer to track analyzed repositories, API usage, and PR outcomes. Uses Write-Ahead Logging (WAL). |
| **LLM Integrations** | Minimax / Gemini / OpenAI / Anthropic | Generates code changes, analyzes findings, and determines project context. Managed via an extensible provider interface. |
| **Data Validation** | Pydantic | Powers the structured parsing and validation of the complex configuration files (`config.yaml`). |
| **RAG/Vector DB** | ChromaDB | Used specifically for local, ephemeral semantic search across a repository to find relevant code chunks. |

## 2. Directory Structure

```text
farm_agent/
├── agents/             # Optional sub-agents and registries
│   └── registry.py
├── analysis/           # Code analysis logic
│   ├── analyzer.py     # CodeAnalyzer core entrypoint
│   ├── language_rules.py
│   ├── mapper.py
│   ├── skills.py
│   └── strategies.py
├── cli/                # The main command-line interface
│   ├── main.py         # The primary entrypoint: defines run, solve, etc.
│   └── tui.py
├── core/               # Foundational classes and data models
│   ├── config.py       # Configuration parser via Pydantic
│   ├── daily_log.py
│   ├── exceptions.py
│   ├── leaderboard.py
│   ├── logger.py
│   ├── middleware.py
│   ├── models.py       # Typed definitions (Repository, PipelineResult, etc.)
│   ├── notifier.py
│   ├── profiles.py
│   ├── quotas.py
│   ├── rag.py          # Ephemeral ChromaDB integration
│   ├── retry.py
│   └── sandbox.py
├── generator/          # Logic for generating actual code changes
│   ├── engine.py       # Interacts with the LLM to output file patches
│   ├── reviewer.py
│   └── scorer.py
├── github/             # Interaction layer with GitHub's APIs
│   ├── client.py       # The HTTPX client implementation
│   ├── discovery.py    # Logic to search and find new repositories
│   └── guidelines.py
├── issues/             # Issue-specific code
│   └── solver.py       # Maps open issues to solvable tasks
├── llm/                # Providers for language models
│   ├── agents.py
│   ├── context.py
│   ├── models.py       # Tasks and routing logic
│   ├── provider.py     # Interface for the LLM integrations
│   └── router.py
├── notifications/
│   └── notifier.py
├── orchestrator/       # The brains orchestrating the entire lifecycle
│   ├── human.py
│   ├── memory.py       # SQLite database logic
│   └── pipeline.py     # ContribPipeline: connects discovery to generation to PR
├── plugins/
│   └── base.py
├── pr/                 # PR management layer
│   ├── janitor.py.DISABLED
│   ├── manager.py      # Creates and monitors pull requests
│   └── patrol.py
├── templates/
│   ├── builtin/
│   └── registry.py
└── tools/
    └── protocol.py
```

## 3. Core Module Dependency Graph

```mermaid
graph TD;
    CLI[CLI (main.py)] --> Orchestrator[Orchestrator (pipeline.py)];
    Orchestrator --> LLM[LLM Provider (minimax, etc.)];
    Orchestrator --> GitHub[GitHub API (client.py)];
    Orchestrator --> Memory[(SQLite DB)];

    Orchestrator --> Analyzer[Code Analyzer];
    Orchestrator --> Generator[Contribution Generator];
    Orchestrator --> PRManager[PR Manager];

    Generator --> RAG[RAG Engine (ChromaDB)];
    Analyzer --> GitHub;
    Generator --> LLM;
```

## 4. Core Execution Loops / Entry Points

### Single Repo Run Flow
When executed against a specific repository via `farm_agent target <url>`:
1. **Initialize:** Loads config, initializes the `ContribPipeline` orchestrator.
2. **Fetch:** Pulls the file tree and metadata from the GitHub API.
3. **Analyze:** The `CodeAnalyzer` scans the repository code, identifying potential bugs, security issues, or refactoring opportunities.
4. **Filter:** The findings are heavily filtered via the Anti-Farming gate.
5. **Context/RAG:** The `ContributionGenerator` uses the LLM (and ChromaDB) to pinpoint exact file modifications.
6. **Generate PR:** The patch is generated.
7. **Submit:** The `PRManager` submits the proposed patch to the remote GitHub repository.

### Issue Solver Flow
When executed via `farm_agent solve <url>`:
1. **Fetch Open Issues:** Connects to GitHub to fetch a list of open issues for the repository.
2. **Filter & Classify:** Determines which issues are reasonably solvable based on complexity heuristics.
3. **Deep Solve:** Triggers `solve_issue_deep()`. It analyzes the required code path and proposes a solution.
4. **Generate & PR:** Converts the proposed fix into a full Pull Request designed to automatically close the target issue.

## 5. Database/State Schema

The local persistent storage is managed by SQLite (via `aiosqlite`). Key schemas identified in `memory.py` include:

**Table: `analyzed_repos`**
- `full_name`: The unique identifier (e.g., `owner/repo`).
- `language`: The primary programming language.
- `stars`: Repository star count at time of analysis.
- `analyzed_at`: Timestamp.
- `findings`: Number of identified findings.

**Table: `submitted_prs`**
- `id`: Primary incremented key.
- `repo`: The target repository.
- `pr_number`: The assigned number on GitHub.
- `pr_url`: The direct link to the PR.
- `title`: PR title.
- `type`: Type of contribution (e.g., security_fix, refactor).
- `status`: Current status ('open', 'merged', 'closed').
- `branch`: The source branch.
- `ci_fix_attempts`: Number of automated CI fixes attempted.
- `discussion_replies`: Number of automated discussion replies.
