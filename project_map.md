# ContribAI Source Code Map

This document outlines the directory structure and core architectural components of the ContribAI project map.

## 📂 `contribai/` (Core Application)

### `/analysis/`
The brain of the agent's static code analysis.
* `analyzer.py` - Main `CodeAnalyzer` class executing concurrent strategies.
* `skills.py` - Core prompt generation and strategy definitions.
* `loc_counter.py` - Lines-of-Code heuristic limits (avoids massive files).

### `/cli/`
Command-line and Terminal User Interface.
* `main.py` - Click command definitions (`hunt`, `superhuman`, `patrol`, etc).
* `tui.py` - Rich-based interactive terminal interface.

### `/core/`
Data models, validation, and configuration.
* `models.py` - Core Pydantic types (`Finding`, `ImpactLevel`, `ContributionType`).
* `config.py` - `ContribAIConfig` schema handling YAML parsing.
* `exceptions.py` - Custom error hierarchy.
* `leaderboard.py` & `profiles.py` & `quotas.py` - System metrics and limits.

### `/generator/`
Responsible for interpreting findings and producing Git-native commits.
* `engine.py` - `ContribGenerator`. Generates code patches via LLM prompts.
* `scorer.py` - Analyzes findings and calculates Priority scores.

### `/github/`
GitHub integrations.
* `client.py` - Async httpx `GHAPI` wrapper. Rate limit handling and pagination.
* `guidelines.py` - Extracts `CONTRIBUTING.md` and checks for "Vibe" / hostility.

### `/issues/`
Targeted GitHub issue resolution.
* `solver.py` - Connects open issues to the analyzer prompt chains.

### `/llm/`
Language Model abstraction layer.
* `agents.py` & `models.py` & `router.py` - MiniMax M2.7 execution and YAML parsing.

### `/notifications/`
Multi-channel C2 (Command & Control).
* `notifier.py` - Persistent `httpx` async client emitting Slack, Discord, and Telegram webhooks.

### `/orchestrator/`
The execution loops tying everything together.
* `human.py` - `SuperHumanLoop`. Stochastic daily schedule with human-like delays/patterns.
* `pipeline.py` - `ContribPipeline`. Implements the discovery → analysis → generate → push flow. Includes Anti-Farming Gate filters.
* `memory.py` - SQLite WAL storage tracking processed repos, PR quotas, forks, and run history.

### `/pr/`
Pull Request lifecycle management.
* `manager.py` - Pushing commits, creating PRs, monitoring statuses, and generating self-healing diffs.

### `/scheduler/`
Daemon tasks.
* `daemon.py` - APScheduler wrappers for `cron`-like execution intervals.

### `/tools/`
External isolation and validation.
* `sandbox.py` - Shift-Left Docker validation executing generated patches in Alpine environments.
* `github_search.py` - Finding new targets.

### `/web/`
API and UI.
* `app.py` & `api.py` & `dashboard.py` - FastAPI application serving web hooks and the HTML dashboard on port `8787`.

---

## ⚙️ Root Infrastructure

* `Dockerfile.superhuman` - Multi-stage ARM64/AMD64 deployment locking `python:3.11-slim`.
* `docker-compose.superhuman.yml` - Production runtime config enforcing a 512MB RAM cap.
* `config.example.yaml` - Template for the 13 configuration sections (pydantic-settings).
* `pyproject.toml` - Hatchling configuration, strict dependency locking, and pytest/ruff integrations.
* `.pre-commit-config.yaml` - Quality gates.
