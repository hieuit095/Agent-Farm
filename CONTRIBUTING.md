# Contributing to Farm-Agent

Thank you for your interest in contributing to Farm-Agent! 🎉

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/tang-vu/Farm-Agent.git
cd Farm-Agent
python -m venv .venv
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate on Unix
pip install -e ".[dev]"

# Verify
pytest tests/ -v  # 247 tests must pass
farm_agent --help
```

## 📋 Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```

2. **Write code** following our standards:
   - Async-first for I/O operations (`async/await`)
   - `from __future__ import annotations` in every file
   - Full type hints on all public APIs (`str | None` style)
   - Google-style docstrings with Args/Returns/Raises
   - No bare `except` — always catch specific exceptions

3. **Write tests** in `tests/unit/`

4. **Lint & format**:
   ```bash
   ruff format farm_agent/ tests/
   ruff check farm_agent/ tests/ --fix
   ```

5. **Run tests**:
   ```bash
   pytest tests/ -v  # 247 tests
   ```

6. **Commit** with conventional messages + DCO signoff:
   ```bash
   git commit -s -m "feat: add Django security analyzer"
   ```
   Valid prefixes: `feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `chore`

7. **Push & create PR** using the PR template

## 🏗️ Project Structure (v2.4.0)

| Directory | Purpose |
|-----------|---------|
| `farm_agent/core/` | Config, models, middleware chain (5 middlewares) |
| `farm_agent/analysis/` | 7 analyzers + progressive skill loading (17 skills) |
| `farm_agent/agents/` | Sub-agent registry (Analyzer, Generator, Patrol, Compliance) |
| `farm_agent/tools/` | MCP-inspired tool protocol (GitHubTool, LLMTool) |
| `farm_agent/llm/` | LLM providers (Gemini, OpenAI, Anthropic, Ollama, Vertex AI) |
| `farm_agent/github/` | GitHub API client, discovery, guidelines |
| `farm_agent/generator/` | Code generation + self-review + quality scorer |
| `farm_agent/pr/` | PR lifecycle manager + patrol + CLA + DCO signoff |
| `farm_agent/orchestrator/` | Pipeline, hunt mode, outcome memory (SQLite) |
| `farm_agent/issues/` | Issue-driven contribution solver |
| `farm_agent/web/` | FastAPI dashboard, auth, webhooks |
| `farm_agent/cli/` | Rich CLI interface |
| `tests/` | 247 unit tests |
| `docs/` | Architecture documentation |
| `.agents/workflows/` | Development workflows |

## 🔑 Key Architecture Patterns

1. **Middleware Chain** — Pipeline processing with RateLimit, Validation, Retry, DCO, QualityGate
2. **Progressive Skills** — 17 analysis skills loaded on-demand by language/framework
3. **Sub-Agent Registry** — 4 agents with parallel execution (max 3 concurrent)
4. **Tool Protocol** — MCP-inspired interface for GitHub/LLM tools
5. **Outcome Learning** — Tracks PR merge/rejection to improve over time
6. **Context Summarization** — Compresses analysis results for LLM prompts

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture docs.

## 🤖 AI Agent Guide

If you're an AI assistant scanning this repo, see [AGENTS.md](AGENTS.md) for structured context.

## ✅ PR Requirements

- All CI checks pass (lint, tests, security)
- Tests for new/changed code
- Documentation updated (if user-facing)
- Follows conventional commits
- DCO signoff on all commits (`git commit -s`)
- CHANGELOG.md updated (if applicable)
