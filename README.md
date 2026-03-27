<div align="center">

# 🤖 ContribAI

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile.superhuman)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-107%20passed-brightgreen?logo=pytest)](tests/)

*An LLM-powered agent that discovers repositories, analyzes code for real bugs, generates fixes, opens Pull Requests, responds to maintainer feedback, and self-heals failed CI — all while mimicking human behavioral patterns to avoid spam detection.*

</div>

---

## The Problem

Most "AI contribution" bots spam repositories with trivial changes — adding docstrings nobody asked for, reformatting whitespace, or making subjective style changes. They get flagged, banned, and give AI-assisted development a bad name.

**ContribAI takes the opposite approach.** It operates under a strict **Anti-Farming** filter that blocks trivial changes at the pipeline level, focuses exclusively on bugs, security flaws, and performance issues, and disguises its operational patterns behind realistic human behavioral simulation.

---

## Key Features

### 🧠 Agentic LLM Engine

- **Multi-strategy analysis** — Security, code quality, performance, and UI/UX analyzers run concurrently against repository file trees
- **Issue-first pipeline** — Solves open GitHub issues before falling back to static analysis, prioritizing what maintainers actually want fixed
- **Self-healing CI** — Detects failed CI checks on submitted PRs, prompts the LLM with the failure log + previous diffs, and pushes corrective commits (up to 3 retries with killswitch)
- **PR Patrol** — Monitors open PRs for maintainer comments and auto-generates code fixes, answers questions, re-signs CLAs, and addresses style feedback
- **Impact-scored findings** — Every finding is scored by `severity × confidence × impact_level`. A dual-gate anti-farming filter drops trivial/low-impact results before they ever become PRs

### 🥷 Deep Cover Stealth Mode

- **Circadian rhythm simulation** — Operates on a stochastic daily schedule with randomized wake times, coffee breaks, lunch hours, and sleep cycles
- **WPM typing delay** — Response latency correlates with payload size, simulating a real developer's typing speed
- **Probabilistic ghosting** — Randomly skips some notification responses to mimic developer burnout/busy patterns
- **Git timestamp spoofing** — Commits carry slightly backdated timestamps to simulate local offline coding sessions
- **Vibe Check** — Fetches recent maintainer comments and uses LLM classification (WELCOMING / STRICT / HOSTILE) to skip hostile repositories before wasting tokens
- **Stochastic PR quota** — Daily target is randomly set between 1-5 PRs, then shifts to patrol-only mode once met

### 🛡️ Sandbox Guillotine

- **Shift-Left Docker testing** — Runs generated patches inside isolated Docker containers before PR creation
- **Fail-safe defaults** — Findings without explicit impact classification default to `TRIVIAL` (auto-dropped)
- **Killswitch limits** — Hard caps on CI retries (3), discussion replies (3), and patch re-prompts (2)
- **Duplicate PR detection** — Title similarity matching prevents re-submitting equivalent fixes

### 📱 Telegram C2 Center

- **Real-time alerts** — PR merged, PR closed, pipeline errors, and run-complete notifications via Telegram Bot API
- **Multi-channel support** — Also supports Slack webhooks and Discord embeds
- **Persistent HTTP session** — Connection-pooled `httpx.AsyncClient` for stable long-running notification delivery

### 🏗️ Edge-First Architecture

- **512MB RAM cap** — Designed for Orange Pi, Raspberry Pi, and other ARM64/AMD64 SBCs
- **Multi-stage Docker build** — Builder stage compiles wheels, runtime stage carries only `python:3.11-slim` + `git`
- **SQLite WAL mode** — Lock-free concurrent reads for quota tracking across async tasks
- **Persistent state volumes** — `memory.db`, `config.yaml`, and `logs/` survive container restarts

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI (Click + Rich)                    │
│  run · hunt · patrol · superhuman · analyze · solve     │
│  cleanup · status · stats · leaderboard · sysinfo       │
├─────────────────────────────────────────────────────────┤
│              SuperHumanLoop (Orchestrator)               │
│  Stochastic daily routine · Hunt/Patrol interleaving    │
│  Circadian delays · PR quota management                 │
├──────────────────────┬──────────────────────────────────┤
│   ContribPipeline    │         PR Patrol                │
│  Discovery → Analyze │  Monitor → Respond → Self-Heal   │
│  → Generate → Submit │  CI retry · Discussion reply     │
├──────────────────────┼──────────────────────────────────┤
│    CodeAnalyzer      │       ContribGenerator           │
│  Security · Quality  │  Jinja2 templates · GitPython    │
│  Perf · UI/UX        │  Conventional commits · DCO      │
├──────────────────────┼──────────────────────────────────┤
│    GitHub Client     │      LLM Provider (MiniMax)      │
│  httpx async · GHAPI │  MiniMax-M2.7 · Structured YAML │
├──────────────────────┼──────────────────────────────────┤
│  SQLite Memory (WAL) │  Notifier (TG · Slack · Discord) │
└──────────────────────┴──────────────────────────────────┘
```

---

## Quick Start

### 1. Clone & Install

```sh
git clone https://github.com/hieuit095/ContribAI.git
cd ContribAI
pip install -e ".[dev]"
```

### 2. Configure

```sh
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your credentials:

```yaml
github:
  token: "ghp_your_token"       # or set GITHUB_TOKEN env var

llm:
  provider: "minimax"
  api_key: "your_minimax_key"   # or set MINIMAX_API_KEY env var

notifications:
  telegram_token: "123456:ABC-DEF"
  telegram_chat_id: "your_chat_id"
```

### 3. Run

```sh
# Single hunt round (discover repos, analyze, create PRs)
contribai hunt --rounds 1 --dry-run

# Target a specific repo
contribai target https://github.com/owner/repo --dry-run

# 24/7 autonomous mode (Super Human)
contribai superhuman
```

### 4. Deploy (Edge Device)

```sh
# Create .env with secrets
echo "GITHUB_TOKEN=ghp_xxx" > .env
echo "MINIMAX_API_KEY=xxx" >> .env

# Launch containerized agent
docker compose -f docker-compose.superhuman.yml up -d

# Monitor logs
docker compose -f docker-compose.superhuman.yml logs -f
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full edge deployment guide.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `contribai run` | Auto-discover repos and contribute |
| `contribai hunt` | Aggressive multi-round discovery + contribution |
| `contribai patrol` | Monitor open PRs and respond to feedback |
| `contribai superhuman` | 24/7 autonomous loop with human-like behavior |
| `contribai target <url>` | Target a specific repository |
| `contribai analyze <url>` | Analyze without creating PRs |
| `contribai solve <url>` | Solve open issues in a repo |
| `contribai status` | Show submitted PR statuses |
| `contribai stats` | Overall contribution statistics |
| `contribai leaderboard` | Success rates per repository |
| `contribai cleanup` | Delete forks with all PRs merged/closed |
| `contribai sysinfo` | System health, memory, rate limits |
| `contribai notify-test` | Send a test notification |
| `contribai serve` | Start web dashboard (port 8787) |
| `contribai config` | Show current configuration |

---

## Anti-Farming Pipeline

Every finding passes through a dual-gate filter before becoming a PR:

```
Finding → Gate 1: Impact Filter → Gate 2: Keyword Filter → PR
          ↓ drop if TRIVIAL/LOW     ↓ drop if farming keyword
          (default: TRIVIAL)        (bypass for HIGH/CRITICAL)
```

**Gate 1** drops any finding with `impact_level ∈ {TRIVIAL, LOW}`. Since the default is `TRIVIAL`, any finding the LLM fails to classify is automatically rejected (fail-safe).

**Gate 2** scans titles for farming keywords (`docstring`, `format`, `style`, `whitespace`, etc.) but **only** for `LOW`/`MEDIUM` severity findings. A `CRITICAL` finding like "Format string injection" will never be accidentally filtered.

---

## Project Structure

```
contribai/
├── analysis/       # CodeAnalyzer, skills, multi-strategy scan
├── cli/            # Click CLI + Rich TUI
├── core/           # Pydantic models, config, exceptions
├── generator/      # ContribGenerator, scorer, Jinja2 templates
├── github/         # GitHub API client, guidelines parser
├── issues/         # Issue solver, category classifier
├── llm/            # LLM provider abstraction (MiniMax)
├── notifications/  # Telegram, Slack, Discord notifier
├── orchestrator/   # Pipeline, SuperHumanLoop, SQLite memory
├── pr/             # PR manager, commit, push
├── scheduler/      # APScheduler cron daemon
├── tools/          # Docker sandbox, utility scripts
└── web/            # FastAPI dashboard + webhooks
```

---

## Configuration Reference

ContribAI uses a YAML-based config system with Pydantic validation. See [`config.example.yaml`](config.example.yaml) for a complete reference with all 13 sections:

`github` · `llm` · `analysis` · `contribution` · `discovery` · `storage` · `pipeline` · `scheduler` · `web` · `quota` · `notifications` · `logging` · `multi_model`

---

## License

**AGPL-3.0** with **Commons Clause** — free to use, modify, and self-host. Commercial SaaS redistribution is restricted. See [LICENSE](LICENSE) for full terms.

Copyright © 2025-2026 [tang-vu](https://github.com/tang-vu)
