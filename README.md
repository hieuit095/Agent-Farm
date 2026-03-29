<div align="center">

# 🤖 Farm-Agent

**Autonomous AI Agent That Contributes to Open Source — Without Looking Like One.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.superhuman.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-561%20passed-brightgreen?logo=pytest)](tests/)

*An LLM-powered agent that discovers repositories, analyzes code for real bugs, generates fixes, opens Pull Requests, responds to maintainer feedback, and self-heals failed CI — all while mimicking human behavioral patterns to avoid spam detection.*

</div>

---

## The Problem

Most "AI contribution" bots spam repositories with trivial changes — adding docstrings nobody asked for, reformatting whitespace, or making subjective style changes. They get flagged, banned, and give AI-assisted development a bad name.

**Farm-Agent takes the opposite approach.** It operates under a strict **Anti-Farming** filter that blocks trivial changes at the pipeline level, focuses exclusively on bugs, security flaws, and performance issues, and disguises its operational patterns behind realistic human behavioral simulation.

---

## 7 Enterprise-Grade Protocols

### 1. Hybrid Contribution Router (Issue-First vs Direct PR)
Analyzes open GitHub Issues first — if a critical issue exists, the agent solves it directly. Falls back to static code analysis only when no actionable issues are found. Prevents wasted effort on cosmetic changes that maintainers don't want.

### 2. Familiar Grounds (Alumni Repo Prioritization)
Scores and prioritizes repositories the user has previously contributed to (Alumni repos). These repos have established trust — lower review friction, faster merges, and higher acceptance rates.

### 3. Immortal Memory (SQLite WAL Persistence)
All run state, PR history, analyzed repos, and API quota usage are persisted in SQLite with WAL mode. The agent survives restarts without losing state. Tracks 7-day rolling quota to prevent over-contributing.

### 4. Alumni Sync (24h Background PR Synchronization)
A background cron job runs every 24 hours, syncing the PR state database with live GitHub — tracking which PRs were merged, closed, or need attention. Keeps the patrol agent accurately informed at all times.

### 5. Polyglot Guillotine (Multi-language Docker Execution)
Every generated patch is validated inside an isolated Docker container specific to the target language before any PR is created. Supports Python, Node.js, TypeScript, Rust, Go, Java, C#, Ruby, PHP, C, C++ via Alpine-based images. If the patch fails to compile or tests red, it is rejected — no bad PRs reach GitHub.

### 6. X-Ray Vision (Local Ephemeral RAG via ChromaDB)
Before generating cross-file patches, the agent builds a local ChromaDB vector index of the repository using a word-frequency embedding model. It queries semantically relevant context (up to 8 chunks) to ensure patches are contextually accurate and don't break downstream code.

### 7. Red Team Adversarial Review (Independent Security Auditor Agent)
The Generator produces a patch, then an independently-instantiated ReviewerAgent (with its own LLM provider and paranoid security auditor system prompt) evaluates it. If REJECTED, the Generator rewrites with the critique injected — up to 2 retries. This adversarial loop ensures no substandard, exploratory, or incomplete PRs escape to GitHub.

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
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
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
farm_agent hunt --rounds 1 --dry-run

# Target a specific repo
farm_agent target https://github.com/owner/repo --dry-run

# 24/7 autonomous mode (Super Human)
farm_agent superhuman
```

### 4. Deploy (Production / 24/7)

```sh
# Create .env with secrets
echo "GITHUB_TOKEN=ghp_xxx" > .env
echo "MINIMAX_API_KEY=xxx" >> .env

# Build and launch the autonomous daemon
docker compose -f docker-compose.superhuman.yml up -d --build

# Monitor logs in real time
docker compose -f docker-compose.superhuman.yml logs -f

# View container status
docker compose -f docker-compose.superhuman.yml ps
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full edge deployment guide.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `farm_agent run` | Auto-discover repos and contribute |
| `farm_agent hunt` | Aggressive multi-round discovery + contribution |
| `farm_agent patrol` | Monitor open PRs and respond to feedback |
| `farm_agent superhuman` | 24/7 autonomous loop with human-like behavior |
| `farm_agent target <url>` | Target a specific repository |
| `farm_agent analyze <url>` | Analyze without creating PRs |
| `farm_agent solve <url>` | Solve open issues in a repo |
| `farm_agent janitor` | Scan and auto-close garbage PRs via LLM |
| `farm_agent reset-db` | Clear run history (keeps submitted_prs) |
| `farm_agent status` | Show submitted PR statuses |
| `farm_agent stats` | Overall contribution statistics |
| `farm_agent leaderboard` | Success rates per repository |
| `farm_agent cleanup-forks` | Delete forks with all PRs merged/closed |
| `farm_agent sysinfo` | System health, memory, rate limits |
| `farm_agent notify-test` | Send a test notification |
| `farm_agent serve` | Start web dashboard (port 8787) |
| `farm_agent config` | Show current configuration |

---

## Anti-Farming Pipeline

Every finding passes through a triple-gate filter before becoming a PR:

```
Finding → Gate 1: Impact Filter → Gate 2: Keyword Blacklist → Gate 3: Generator Sanity Check → PR
          ↓ drop MEDIUM/LOW/TRIVIAL  ↓ drop farming keywords       ↓ drop no-op patches
          (only CRITICAL/HIGH pass)   in title OR description        (search == replace)
```

**Gate 1 — Impact Level** drops any finding with `impact_level ∈ {TRIVIAL, LOW, MEDIUM}`. Only `CRITICAL` and `HIGH` survive.

**Gate 2 — Keyword Blacklist** drops any finding where the title OR description contains farming keywords (case-insensitive): `understand`, `explore`, `read`, `docs`, `typo`, `format`, `whitespace`, `comment`, `spell`, `styling`, `test`, `chore`, etc. No bypass — even a `HIGH` finding with "understand" in the title is dropped.

**Gate 3 — Generator Sanity Check** runs after patch generation. Any patch where `search == replace` (no-op) is immediately rejected and the PR is aborted.

---

## Project Structure

```
farm_agent/
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

Farm-Agent uses a YAML-based config system with Pydantic validation. See [`config.example.yaml`](config.example.yaml) for a complete reference with all 13 sections:

`github` · `llm` · `analysis` · `contribution` · `discovery` · `storage` · `pipeline` · `scheduler` · `web` · `quota` · `notifications` · `logging` · `multi_model`

---

## License

**AGPL-3.0** with **Commons Clause** — free to use, modify, and self-host. Commercial SaaS redistribution is restricted. See [LICENSE](LICENSE) for full terms.

Copyright © 2025-2026 [tang-vu](https://github.com/tang-vu)
