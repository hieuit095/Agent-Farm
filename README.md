# 🛠️ Farm-Agent

**Senior Open Source Contributor — Human-like precision, zero friction.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)

## Overview

Farm-Agent is an autonomous AI agent designed to discover open-source GitHub repositories, identify bugs or quality issues, generate precise patches via LLMs, validate those patches in isolated Docker sandboxes, and submit pull requests or issues. It operates using a sophisticated 24/7 human-like schedule with simulated coding delays to provide genuine value to open-source maintainers.

## Key Features

- **Issue-First Pipeline:** Prioritizes solving open GitHub issues, using a RAG-based context vision across the repository before proposing solutions.
- **Polyglot Sandbox Validation:** Patches are validated inside an ephemeral Docker container. The agent enters a self-correction loop if tests or linters fail before ever creating a PR.
- **Bloodhound Security Scans:** Uses a pre-scan vulnerability analyzer (via Semgrep logic) combined with an LLM evaluation phase to surface production vulnerabilities.
- **Diplomat & Anti-Farming Protocols:** Features a zero-tolerance gatekeeper that filters out trivial findings, prevents doc-only spam, and aborts pipelines when repositories request private security disclosure or explicitly ban AI PRs.
- **Super Human Mode:** A 24/7 execution daemon using dynamic PR quotas, stochastic routines, and human-like delays.
- **PR Patrol & Janitor:** Autonomously monitors its open PRs to auto-respond to code review feedback, push auto-fixes, and delete garbage PRs using LLM classification.
- **Circular Target Loop:** Round-robin processes targeted repositories matching specific metrics out of a local memory tracking schema.

## System Architecture

Farm-Agent is driven by a Click-based CLI orchestrating the main `ContribPipeline`. During a pipeline run:
1. **Discovery:** The agent identifies candidate repositories via the GitHub REST API and filters out blacklisted ones or repos limiting interactions.
2. **Analysis:** Concurrently runs security, code quality, and style analyzers while aggressively dropping low-impact findings using the Anti-Farming gate.
3. **Generation:** Connects to an LLM provider (Minimax, OpenRouter via multi-model routing) to generate code patches, utilizing an ephemeral ChromaDB RAG index for localized context retrieval.
4. **Sandbox Validation:** Patches are pushed to an ephemeral, network-isolated Docker container where test suites are executed.
5. **PR Submission:** If successful, PRs are submitted, tracked in a local SQLite database (in WAL mode), and verified post-submit for compliance checks.

## Getting Started

### Prerequisites

- **Python:** 3.11 or higher
- **Docker:** 7.1 or higher
- **GitHub PAT:** A GitHub Personal Access Token (with `repo` scope)
- **LLM API Key:** Valid keys for Minimax or OpenRouter (or alternatives like Gemini, OpenAI, Anthropic, Ollama).

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package and development dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Environment Variables

You can configure Farm-Agent using `.env` variables or by copying `config.example.yaml` to `config.yaml`.
Required core variables:
- `GITHUB_TOKEN`: Your GitHub Personal Access Token.
- `MINIMAX_API_KEY`: The primary API key for the Minimax LLM integration.
- `OPENROUTER_API_KEY`: Primary key for Red Team/Redteaming LLM provider.
- `TELEGRAM_BOT_TOKEN`: The telegram notification integration token.

## Usage

Farm-Agent provides several core CLI commands accessible via `farm_agent`:

**Run a single automated discovery and contribution cycle:**
```bash
farm_agent run
```

**Target a specific repository directly:**
```bash
farm_agent target https://github.com/owner/repo
```

**Aggressively discover and loop through multiple repos (Hunt Mode):**
```bash
farm_agent hunt --rounds 5 --delay 30
```

**Process targeted repositories in a deterministic round-robin:**
```bash
farm_agent hunt-circular
```

**Monitor open PRs and auto-respond to maintainer feedback:**
```bash
farm_agent patrol
```

**Run the 24/7 autonomous human-like daemon:**
```bash
farm_agent superhuman
```

**Sweep and auto-close low-quality garbage PRs:**
```bash
farm_agent janitor
```

**Solve specific open issues on a repository:**
```bash
farm_agent solve https://github.com/owner/repo
```

## Contributing & License

We welcome contributions! Please follow standard open-source pull request workflows.

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
