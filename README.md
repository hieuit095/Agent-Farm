# Farm-Agent

![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-3.0.0-orange)
![Docker](https://img.shields.io/badge/docker-%3E%3D7.1-blue)

## Overview

**Farm-Agent** is an autonomous system that automatically contributes to open source projects on GitHub. Powered by advanced Large Language Models (LLMs) and a secure execution sandbox, it operates 24/7 through a relentless Terminator execution loop to discover repositories, identify issues or vulnerabilities, generate fixes, and submit Pull Requests.

## Key Features

- **Relentless Terminator Execution Loop:** 24/7 autonomous engine orchestrated via `docker-compose` to maximize PR throughput up to daily API caps.
- **Bloodhound Red Team Audits:** Employs advanced ast-grep and Semgrep radar for vulnerability discovery, routing audits through OpenRouter.
- **Polyglot Sandbox:** Highly restricted Docker-based sandbox environment executing code across 12 supported languages, fortified with strict timeouts and OS-level kill signals.
- **Anti-Farming Filter:** Prevents spam and trivial PRs by completely blocking docs-only changes (`README_FIX`, `DOCS_IMPROVE`) and enforcing impact-level gates.
- **Security Disclosure Gate:** Scans repository meta files (`SECURITY.md`, etc.) for private disclosure guidelines, automatically aborting pipelines for matching repositories to respect maintainer protocols.
- **Multi-LLM Strategy:** Flexible model routing with primary support for Minimax (ABAB) models, OpenRouter, and fallback to local Ollama.
- **Local RAG Integration:** Utilizes ChromaDB for Retrieval-Augmented Generation to provide contextually precise code fixes.

## System Architecture (High-Level)

Farm-Agent operates in a circular pipeline consisting of six key stages:
1. **Discovery:** Identifies prospective repositories based on criteria (stars, activity, languages).
2. **Gate:** Applies strict security, anti-farming, and maintainer vibe checks to validate targets.
3. **Analysis:** Deep-scans codebases utilizing the Bloodhound Red Team pipeline and static analysis tools.
4. **Engine:** Leverages multi-model LLMs to generate high-quality patches and PR descriptions.
5. **Sandbox:** Verifies patches in a fully-isolated, network-restricted Docker environment.
6. **PR:** Submits, tracks, and manages Pull Requests, automatically responding to comments via PR Patrol.

## Getting Started

### Prerequisites

- **Python:** >= 3.11
- **Docker:** >= 7.1

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install dependencies via pip:
   ```bash
   pip install -e .[dev]
   ```

### Configuration

Farm-Agent relies on a combination of environment variables and configuration files.

1. **Environment Variables:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   **Required variables in `.env`:**
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token (requires `repo`, `read:org`, and `workflow` scopes).
   - `MINIMAX_API_KEY`: API Key for the Minimax LLM provider.

   *Optional:*
   - `GITHUB_SECONDARY_TOKENS`: Additional tokens to distribute API load.
   - `OPENROUTER_API_KEY`: API Key for OpenRouter (used for White-Hat audits).
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`: For notifications.

2. **Configuration File:**
   Copy the example config:
   ```bash
   cp config.example.yaml config.yaml
   ```

### Running with Docker

Farm-Agent is designed to run persistently using Docker Compose:
```bash
docker-compose up -d
```

## Usage

Farm-Agent provides a rich CLI built with `click` and `rich`.

- **Auto-discover repos and contribute:**
  ```bash
  farm_agent run
  ```

- **Target a specific repository:**
  ```bash
  farm_agent target https://github.com/owner/repo
  ```

- **Analyze a repo without contributing:**
  ```bash
  farm_agent analyze https://github.com/owner/repo
  ```

- **Solve existing issues:**
  ```bash
  farm_agent solve https://github.com/owner/repo
  ```

- **View PR status and statistics:**
  ```bash
  farm_agent status
  farm_agent stats
  ```

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Ensure all tests pass using `python -m pytest tests/unit/`.
4. Submit a descriptive Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
