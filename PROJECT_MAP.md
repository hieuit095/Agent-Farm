# 🗺️ Agent-Farm Project Architecture Map

This document serves as the deep-dive architectural blueprint for the Agent-Farm codebase.

---

## 1. System Overview & Tech Stack

| Component | Technology | Description |
|-----------|------------|-------------|
| **Core Language** | Python 3.11+ | The primary backend language orchestrating all logic. |
| **CLI Framework** | Click & Rich | Provides the terminal interface and styled console outputs (`farm_agent/cli/main.py`). |
| **Database** | SQLite (aiosqlite) | Persistent memory store for caching PRs, analyzed repos, usage logs, and knowledge base (`farm_agent/orchestrator/memory.py`). |
| **Vector Database** | ChromaDB | Local vector store for the Omniscient Context Engine to index documentation (RAG). |
| **LLM Integrations** | OpenRouter (DeepSeek, Qwen, Gemini), Minimax | Used for bug discovery, patch generation, PR review responses, and system auditing. |
| **Containerization** | Docker | Provides the sandbox environments (`DockerSandbox`) for executing PoCs and test suites. |
| **Build System** | Hatchling | Modern PEP 517 build backend configured in `pyproject.toml`. |
| **Version Control** | GitPython | Local repository manipulation and diff patch generation. |

---

## 2. Directory Structure

```ascii
Agent-Farm/
├── farm_agent/                   # Core application module
│   ├── agents/                   # Agent registry and core definitions
│   ├── analysis/                 # Bug finding (BloodhoundAnalyzer, CodeAnalyzer)
│   ├── cli/                      # Command-line interface definitions (main.py)
│   ├── core/                     # Configuration, logging, models, RAG, memory, quotas
│   ├── generator/                # Fix patch/PoC generation and scoring
│   ├── github/                   # GitHub API wrappers, security gates, discovery logic
│   ├── issues/                   # Autonomous issue solver module
│   ├── llm/                      # Provider abstractions (OpenRouter, Minimax) & routers
│   ├── notifications/            # Multi-channel webhooks (Slack, Telegram, Discord)
│   ├── orchestrator/             # Main execution pipelines (pipeline.py, memory.py, human.py)
│   ├── plugins/                  # Extensibility modules
│   ├── pr/                       # PR lifecycle (Manager, Patrol, Janitor)
│   ├── templates/                # Contribution templates
│   └── tools/                    # Tools registry (Bash, grep, replace_with_git_merge_diff)
├── scripts/                      # Helper maintenance scripts
├── tests/                        # Pytest suite
├── .env.example                  # Template for required environment variables
├── docker-compose.yml            # Defines the agent-farm service and bridge networks
├── Dockerfile                    # Container instructions
├── Makefile                      # Make targets for linting, testing, and Docker builds
├── pyproject.toml                # Project metadata and dependencies (Hatchling)
├── requirements.txt              # Core runtime dependencies
├── start.bat                     # Windows Docker fast-start script
└── start.sh                      # Unix Docker fast-start script
```

---

## 3. Core Module Dependency Graph

```mermaid
graph TD
    CLI[CLI (main.py)] --> Pipeline[FarmAgentPipeline (pipeline.py)]
    CLI --> HumanLoop[SuperHumanLoop (human.py)]
    CLI --> PRPatrol[PRPatrol (patrol.py)]

    Pipeline --> GitHubClient[GitHubClient (client.py)]
    Pipeline --> Memory[SQLite Memory (memory.py)]
    Pipeline --> CodeAnalyzer[CodeAnalyzer / Bloodhound]
    Pipeline --> Generator[ContributionGenerator & PoCGenerator]
    Pipeline --> Sandbox[DockerSandbox (sandbox.py)]
    Pipeline --> PRManager[PRManager (manager.py)]

    Generator --> Qwen[Qwen (Layer 1 Appraiser)]
    Generator --> DeepSeek[DeepSeek (Dev-QA Loop)]
    Sandbox -.-> Generator

    Pipeline --> Gemini[Gemini (Layer 2 Supreme Audit)]
    Gemini -.-> PRManager
```

---

## 4. Core Execution Loops / Entry Points

### 🎯 Standard Pipeline Execution (`farm_agent run` / `target` / `hunt`)
1. **Discovery:** Finds high-value repositories via `RepoDiscovery` matching stars, languages, and activity filters.
2. **Analysis:** Runs `BloodhoundAnalyzer` (Semgrep) followed by `CodeAnalyzer` (LLM) to identify critical/high severity security flaws or bugs.
3. **Appraisal Gate:** Findings are filtered through the Layer 1 Appraiser (Qwen) to weed out false positives.
4. **DEV-QA Loop:**
    * Creates a PoC, runs it in `DockerSandbox`, and confirms the vulnerability exists.
    * Generates a patch via `ContributionGenerator`.
    * `QAHardcoreScorer` evaluates the patch against styles and guidelines.
5. **Sandbox Validation:** Applies the patch in the sandbox. Ensures the PoC now fails and the native test suite still passes.
6. **Supreme Audit Gate:** Gemini audits the incident dossier (bug, fix, logs) to ensure no regressions or hallucinations occurred.
7. **Submission:** `PRManager` opens the Pull Request or issue.

### 🧠 Terminator Mode (`farm_agent superhuman`)
An endless 24/7 background loop that:
1. Orchestrates circular target processing (`hunt-circular`).
2. Interleaves `patrol` sweeps to check on active Pull Requests.
3. Dynamically limits quotas to avoid hitting GitHub/LLM API rate limits.

### 🔍 PR Patrol (`farm_agent patrol`)
1. Scans the SQLite DB for open PRs created by the agent.
2. Checks GitHub for unread maintainer comments.
3. Routes the comment to either generate a code fix (which triggers a new git push to the PR branch) or conversational answer.

---

## 5. Database/State Schema (`memory.db`)

Agent-Farm leverages an SQLite-based (`aiosqlite`) persistent memory instance with WAL (Write-Ahead Logging) enabled.

* **`analyzed_repos`**: Keeps track of which repositories have been scanned and the number of findings discovered to prevent redundant API queries.
* **`submitted_prs`**: Stores all submitted Pull Requests (Repo, PR Number, Branch, Title, Status, and Metrics like CI fix attempts).
* **`run_log`**: Tracks complete execution history (duration, repos analyzed, errors).
* **`pr_outcomes`**: Stores the result (merged, closed, rejected) and time-to-close metrics, forming the basis for predictive behavior.
* **`repo_preferences`**: Analyzes the outcomes to determine which contribution types are favored or rejected by specific repo maintainers.
* **`blacklisted_repos`**: Permanently records repositories that exhibit toxic/hostile vibes or explicitly ban AI.
* **`target_repos`**: Manages the circular loop queue of repos targeted for bug hunting, along with their last scan timestamps.
* **`knowledge_base`**: Stores AI-generated "lessons learned" (QA critiques, filter rejections) which are injected as context into future patches to prevent repeating mistakes.
* **`api_usage_log`**: Detailed metrics on LLM provider usage (timestamps, tokens) to enforce safe sliding-window quotas.
* **`repo_style_guides`**: Caches parsed `CONTRIBUTING.md` rules and style summaries.
