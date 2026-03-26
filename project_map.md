# ContribAI Project Architecture & File Map

This document outlines the definitive target architecture of the ContribAI agent, mapping the responsibility of every core file within the Python module tree.

## `/contribai` (Core Module)

### Core Interfaces & Configuration (`/core`)
- `config.py`: Pydantic-based system configurations, including settings for GitHub, LLM providers (Minimax), and Notifications (Telegram).
- `daily_log.py`: Daily rotating Markdown logger for tracking autonomous lifecycle events.
- `exceptions.py`: Custom error classes including `ContribAIError` and `GitHubAPIError`.
- `leaderboard.py`: Manages statistics and scoring for generated PRs.
- `logger.py`: Centralized logging configuration for the agent.
- `middleware.py`: Execution chain handling rate limits, retry policies, and quality gating.
- `models.py`: Shared Pydantic data models for repositories, files, issues, and PR feedback.
- `notifier.py`: Contains `TelegramNotifier` for non-blocking, async broadcast of system alerts via the Telegram API.
- `profiles.py`: Presets defining different hunt personalities.
- `quotas.py`: Tracks GitHub and LLM API usage limits to prevent suspension.
- `retry.py`: Exponential backoff handlers for network resilience.

### Orchestration (`/orchestrator`)
- `human.py`: The `SuperHumanLoop` brain. Orchestrates stochastically interleaved periods of searching, pushing, resting, and patrolling. Inherits traits of a dedicated open-source maintainer.
- `memory.py`: SQLite-backed state persistence for PR tracking, repo blacklisting, and the sliding-window tracker for the Minimax Overdrive API quota.
- `pipeline.py`: The primary execution engine integrating discovery, AST analysis, LLM iteration, and cleanup.

### PR Management & Patrol (`/pr`)
- `manager.py`: Handles Git and GitHub API abstractions for branching, pushing commits, and opening PRs.
- `patrol.py`: The `PRPatrol` engine. Continuously polls open PRs for failing CI runs (to auto-heal) or maintainer comments. Simulates a human persona across all repository interactions.

### Language Learning Models (`/llm`)
- `provider.py`: Implements LLM REST interfaces. Contains the "Minimax Overdrive" logic, overriding conservative rate limits to execute tasks with maximum asyncio concurrency.
- `agents.py`, `models.py`, `router.py`, `context.py`: Multi-model coordination, system prompt generation, and dynamically injected style-mimicry context generation.

### Code Generation (`/generator`)
- `engine.py`: Ingests AST analysis and repository guidelines to generate targeted, localized code fixes.
- `scorer.py`: Evaluates proposed patches against safety and completeness heuristics prior to push.

### Target Discovery (`/github`)
- `client.py`: Core async GitHub REST and GraphQL client implementation.
- `discovery.py`: The `DiscoveryEngine` used by the agent to autonomously search the GitHub network.
- `guidelines.py`: Analyzes `CONTRIBUTING.md` and repository culture to format PR metadata.

### Deep Repository Analysis (`/analysis`)
- `analyzer.py`: Coordinates semantic and syntactic evaluation engines.
- `language_rules.py`, `mapper.py`, `skills.py`, `strategies.py`: Language-specific logic for parsing Python, JS/TS, Rust, building file ASTs, and slicing context for LLMs.

### CLI & Web Interface (`/cli` & `/web`)
- `cli/main.py`: The root Click command group. Exposes the autonomous `contribai superhuman` command.
- `cli/tui.py`: Text User Interface elements for rich terminal dashboard outputs.
- `web/*`: FastAPI REST endpoints designed to serve remote dashboards and handle ingestion of GitHub webhooks.

### Supplementary Directories
- `/agents`: Agent registry abstractions mapping capabilities to instances.
- `/issues`: Specialized solver engine targeted purely at resolving specific user-assigned GitHub issues.
- `/notifications`: Legacy notification endpoints superseded structurally by `core/notifier.py`.
- `/plugins`: External entry points allowing dynamic loading of third-party analyzer extensions.
- `/scheduler`: APScheduler configurations executing routine sweeps outside of Super Human Mode.
- `/templates`: Declarative YAML schemas that inject routine standards (e.g., adding `security-headers.yaml`).
- `/tools`: Function-calling and tool protocol handlers bridging string inferences with native filesystem and terminal execution.
