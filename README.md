# 🛠️ Farm-Agent

**Autonomous Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is a highly advanced autonomous system designed to automatically contribute to open-source GitHub repositories. It discovers repositories matching specific criteria, analyzes code for bugs or quality issues, generates patches using LLM providers, and validates those patches in an isolated polyglot Docker sandbox before submitting precise Pull Requests.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving open GitHub issues before falling back to static analysis for security, code quality, and documentation fixes.
- **Polyglot Sandbox Validation:** Patches are rigorously validated inside isolated, network-restricted Docker containers (supporting 12+ languages), complete with a self-correction loop on test failures.
- **Multi-Model Routing:** Auto-routes code generation, reviewing, and scoring to multiple LLM providers, including MiniMax, OpenRouter (Anthropic/OpenAI/Gemini), and Ollama.
- **PR Patrol & Janitor:** Autonomously monitors open PRs to push auto-fixes, answer maintainer questions, sign CLAs, and aggressively sweep and close low-quality 'garbage' PRs.
- **Super Human Mode:** A 24/7 stochastic daemon that mimics human developer rhythms, with random PR quotas, simulated typing delays, and organic behavior.
- **Bloodhound Red Team & Sentinel Radar:** Implements security auditing via Semgrep rulesets and OpenRouter white-hat models.
- **Anti-Farming Gatekeeper:** Drops trivial changes, filters out AI-banned repositories, and blocks pure documentation PRs to ensure only impactful contributions are pushed.
- **X-Ray Context Vision:** Builds a local ChromaDB Retrieval-Augmented Generation (RAG) index to ensure code patches are contextually accurate across multiple files.

## System Architecture (High-Level)

Farm-Agent follows the **"DeerFlow"** registry-based agent architecture. The pipeline orchestrator triggers an end-to-end execution loop via the `farm_agent` CLI, flowing sequentially: **Discovery -> Gate -> Analysis -> Engine -> Sandbox -> PR**.

State and operation logs are persisted in a local SQLite database utilizing WAL mode (`aiosqlite`). Code context for large repositories is augmented by ChromaDB RAG. Generated patches are critically evaluated by a QA Hardcore Scorer, executed in Docker, and only pushed to GitHub if validation passes the security gates.

## Getting Started

### Prerequisites

- **Python:** 3.11+
- **Docker:** 7.1+ (Required for Sandbox Validation)
- **Git:** 3.1+

### Installation

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Variables

To set up the environment, copy the example configurations and provide your keys:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Required variables in your `.env` file:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires repo, read:org, workflow scopes).
- `MINIMAX_API_KEY`: API key for the default Minimax LLM provider.

Optional/Advanced `.env` variables:
- `GITHUB_SECONDARY_TOKENS`: Comma-separated secondary tokens for GET request rotation to manage rate limits.
- `OPENROUTER_API_KEY`: Required for Bloodhound Red Team audits.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For push notifications.

## Usage

Farm-Agent offers a rich set of CLI commands for different operational modes:

**Run the 24/7 autonomous daemon (Super Human Mode):**
```bash
farm_agent superhuman
```

**Hunt mode: auto-discover repos and contribute aggressively:**
```bash
farm_agent hunt --rounds 5 --delay 30 --mode both
```

**Solve open issues in a specific repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Analyze a repo without creating contributions:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Check open PRs for review feedback and auto-respond (PR Patrol):**
```bash
farm_agent patrol
```

**Sweep and auto-close garbage PRs via LLM evaluation (Janitor):**
```bash
farm_agent janitor
```

**View overall performance statistics:**
```bash
farm_agent stats
```

## Contributing & License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
