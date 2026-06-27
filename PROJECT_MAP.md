# PROJECT_MAP.md — Agent-Farm Architecture Blueprint

**Entry Point:** `farm_agent/cli/main.py` → `cli()`
**Language:** Python 3.11+

---

## 1. System Overview & Tech Stack

Agent-Farm is an autonomous pipeline that crawls, analyzes, patches, validates, and submits fixes to open-source GitHub repositories. It integrates tightly with LLM providers, persistent local storage, and isolated Docker environments to ensure secure, high-confidence contributions.

| Component | Technology | Role / Usage |
|-----------|------------|--------------|
| **Core Language** | Python 3.11+ | Backend logic, CLI, and orchestration. |
| **HTTP Client** | `httpx` | Asynchronous API interactions with GitHub. |
| **Primary LLMs** | `deepseek-v4-flash`, `deepseek-v4-pro` | General routing, code generation, and Red Team bug hunting via OpenRouter. |
| **Expert Appraisers** | `qwen3.7-max`, `gemini-3.5-flash` | Strict validation logic (Layer 1 Appraiser, Layer 2 Supreme Auditor). |
| **Vector Database** | ChromaDB (`chromadb>=0.4`) | RAG-based context injection for codebase documentation chunks. |
| **Relational Database**| SQLite (`aiosqlite`) | Persistent state memory (WAL mode). Tracks targets, PRs, runs, quotas, and cache. |
| **Execution Sandbox** | Docker (`docker>=7.1`) | Network-isolated container execution for Dynamic Bug Verification and native testing. |
| **Configuration** | Pydantic v2 | Type-safe environment variable and YAML config resolution (`config.py`). |
| **CLI & UI** | Click & Rich | Command-line interface definitions and dynamic console outputs. |

---

## 2. Directory Structure

```text
.
├── Dockerfile                  # Stage 1 builder & Stage 2 runtime definitions
├── docker-compose.yml          # Agent-farm services with isolated networks
├── start.sh / start.bat        # Entry scripts for environment initialization
├── Makefile                    # Targets for dev install, testing, and linting
├── farm_agent/                 # Main application package
│   ├── __init__.py
│   ├── cli/
│   │   └── main.py             # CLI commands (run, target, hunt, patrol, etc.)
│   ├── core/
│   │   ├── config.py           # Configuration models (Pydantic)
│   │   ├── exceptions.py       # Custom exception hierarchy
│   │   ├── memory.py           # Legacy reference/shim (main memory is in orchestrator/memory.py)
│   │   ├── models.py           # Core data structures (Repository, Finding, Contribution)
│   │   ├── rag.py              # ChromaDB interactions for document ingestion
│   │   └── sandbox.py          # DockerSandbox logic for isolated validations
│   ├── analysis/
│   │   ├── analyzer.py         # CodeAnalyzer and BloodhoundAnalyzer execution
│   │   └── mapper.py           # AST-based dependency graphing for module relations
│   ├── generator/
│   │   ├── engine.py           # Generates patches and file modifications
│   │   ├── poc.py              # Generates PoC scripts to verify vulnerabilities
│   │   └── scorer.py           # QA scoring logic for evaluating drafted patches
│   ├── github/
│   │   ├── client.py           # Resilient GitHub REST/GraphQL async client
│   │   ├── discovery.py        # Logic for scraping and discovering target repositories
│   │   ├── guidelines.py       # Extraction of CONTRIBUTING.md and style guides
│   │   └── security_gate.py    # Checks repository metadata for private disclosure mandates
│   ├── issues/
│   │   └── solver.py           # Analyzes and solves open GitHub issues directly
│   ├── llm/
│   │   ├── provider.py         # OpenRouter integration and API request handling
│   │   ├── router.py           # Task router for model selection
│   │   └── agents.py           # Prompt and system instruction configurations
│   ├── orchestrator/
│   │   ├── pipeline.py         # Central `FarmAgentPipeline` logic and DEV-QA execution loop
│   │   ├── human.py            # `SuperHumanLoop` implementation for 24/7 autonomous hunting
│   │   └── memory.py           # Main SQLite logic (`Memory` class and schemas)
│   └── pr/
│       ├── manager.py          # Fork, branch creation, commit, and PR generation
│       └── patrol.py           # Daemon to check open PRs, respond to feedback, fix CI errors
└── tests/                      # Pytest unit and integration test suites
```

---

## 3. Core Execution Loops & Data Flow

### The Pipeline Flow (`FarmAgentPipeline.run`)

1. **Discovery:** The agent fetches candidate repositories based on constraints (stars, languages, activity).
2. **Analysis (`BloodhoundAnalyzer` & `CodeAnalyzer`):**
   - Runs Semgrep pre-scans and deep LLM code sweeps.
   - Discards targets without issues or with non-production context matches.
3. **Context Injection (`RepoMapper` & RAG):**
   - Maps module relationships via AST.
   - Fetches and chunks codebase documentation to inform the LLMs.
4. **Validation (Layers 1 & 2):**
   - Found vulnerabilities are rigorously checked by Appraisers to discard false positives.
5. **Generation & Verification (`DockerSandbox` & `PoCGenerator`):**
   - The agent drafts a PoC to trigger the bug.
   - It drafts a patch, applies it, and runs the PoC again (Efficacy check).
   - Runs the repository's native test suite to ensure no breakage (Regression check).
6. **Submission (`PRManager`):**
   - The agent forks the repo, applies verified patches, and submits a PR (or private disclosure).

### Super Human Loop (`SuperHumanLoop`)
A relentless, randomized 24/7 loop simulating human developer behavior. It randomly dictates how many PRs it will merge per day, pauses organically, loops over targets deterministically from `target_repo.json` (Circular Target Loop), and actively monitors open PRs via `PRPatrol`.

### PR Patrol Loop (`PRPatrol`)
Continuously monitors active PRs submitted by the agent:
- Answers maintainer questions.
- Addresses Code Review adjustments and auto-pushes updates.
- Reads CI logs from failing checks, synthesizes fixes, and pushes auto-healing commits.

---

## 4. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (main.py)] --> Pipeline[FarmAgentPipeline]
    CLI --> HumanLoop[SuperHumanLoop]
    HumanLoop --> Pipeline
    HumanLoop --> Patrol[PRPatrol]

    Pipeline --> GitHub[GitHubClient]
    Pipeline --> DB[Memory / SQLite]
    Pipeline --> Analyzer[Bloodhound / CodeAnalyzer]
    Pipeline --> RAG[RepoIndexer / ChromaDB]

    Analyzer --> LLM[LLM Provider / OpenRouter]
    Analyzer --> Mapper[RepoMapper]

    Pipeline --> Generator[ContributionGenerator]
    Generator --> Sandbox[DockerSandbox]
    Generator --> PoC[PoCGenerator]

    Pipeline --> Auditor[Supreme Auditor Layer]
    Auditor --> PRManager[PRManager]

    PRManager --> GitHub
```

---

## 5. Database & State Schema (`memory.db`)

The system relies on SQLite operating in WAL mode for persistent tracking. Key tables include:

- **`analyzed_repos`**: Tracks repositories that have already been evaluated to prevent duplication (`full_name`, `analyzed_at`, `findings`).
- **`submitted_prs`**: Records all Agent-generated PRs and issues (`repo`, `pr_number`, `pr_url`, `status`, `ci_fix_attempts`).
- **`run_log`**: Contains summary metadata for global pipeline executions (`started_at`, `repos_analyzed`, `prs_created`).
- **`pr_outcomes` & `repo_preferences`**: Absorbs historical data regarding merged/closed PR states and maintainer feedback to fine-tune future contribution choices dynamically.
- **`api_usage_log`**: Granular tracking for API provider rate limits (includes indices optimized for sliding-window counts).
- **`knowledge_base`**: Retains critical lessons from past Q/A failures, rejections, or architectural critiques to avoid repeating mistakes (`repo_name`, `entry_type`, `content`).
- **`target_repos`**: Controls the sequential execution queue for the Circular Target Loop (`repo_url`, `status`, `scanned_at`).
