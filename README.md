# Agent-Farm

![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)
![Python Version](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![Docker](https://img.shields.io/badge/docker-%3E%3D7.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)

An autonomous system that automatically discovers repositories, identifies bugs or open issues, and contributes to open-source projects on GitHub. Agent-Farm handles the entire lifecycle of a contribution: from codebase analysis and finding generation, to sandbox verification, pull request creation, and ongoing PR review patrol.

## Key Features

- **Issue-First Pipeline:** Seamlessly solves existing GitHub open issues by pulling them, filtering solvable targets, creating code changes, and opening PRs.
- **PR Patrol:** Automatically scans open PRs for maintainer feedback, actively responding to comments and pushing fixes when needed.
- **Terminator Mode (Super Human Mode):** A relentless, continuous execution loop that dynamically operates without artificial delays, hunting for targets and acting on them 24/7.
- **Security Disclosure Gate:** Employs protective checks to scan repositories for security guidelines and private disclosure phrases, preventing unwanted automated reports.
- **Local RAG Integration:** Utilizes ChromaDB to construct localized context mappings, achieving precise fixes for complex codebases.
- **Multi-LLM Routing Support:** Flexibly leverages models like DeepSeek, Qwen, and Gemini across different tasks for optimal analysis and execution.
- **Dynamic Bug Verification:** Runs generated code fixes inside isolated Docker environments to confidently verify changes prior to pushing.

## System Architecture (High-Level)

Agent-Farm is built around a custom registry-based agent architecture ("DeerFlow"). It orchestrates several core components:
1. **GitHub Client:** For interacting with the GitHub API to discover repositories and manage PRs.
2. **Orchestrator Pipeline:** Central nervous system coordinating targets, task models, and execution loops.
3. **Execution Sandbox:** A secure Docker container environment for safely running unverified codebase tests and builds.
4. **Persistent Memory:** Uses an SQLite database to store analysis caches, PR run logs, configurations, and RAG knowledge-base indices.

## Getting Started

### Prerequisites

- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for dynamic bug verification and isolated sandbox execution)

### Installation

Clone the repository and install the project along with its development dependencies using `make`:

```bash
git clone https://github.com/hieuit095/Agent-Farm.git
cd Agent-Farm
make install
```

### Environment Variables

Agent-Farm requires specific credentials to operate. Create a `.env` file (you can copy `.env.example` if available) with the following essential keys:

```env
GITHUB_TOKEN=your_github_personal_access_token
MINIMAX_API_KEY=your_minimax_key  # Optional depending on LLM config
OPENROUTER_API_KEY=your_openrouter_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token  # For notifications (optional)
```

## Usage

Agent-Farm provides a comprehensive CLI for managing tasks.

**Auto-discover and contribute:**
```bash
farm_agent run
```

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve specific open issues on a repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 5
```

**Run PR Patrol to respond to review feedback:**
```bash
farm_agent patrol
```

**Launch Terminator Mode (Super Human continuous loop):**
```bash
farm_agent superhuman
```

## Contributing & License

Contributions are welcome! Please run `make lint` and `make test` before submitting changes.

This project is licensed under the MIT License.
