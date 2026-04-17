# Farm-Agent 🚀

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Support](https://img.shields.io/badge/Docker-7.1%2B-blue.svg)](https://www.docker.com/)

**Farm-Agent** is an autonomous AI system that automatically discovers repositories, analyzes codebases, solves issues, and contributes to open-source projects on GitHub.

## 🌟 Overview

Farm-Agent v3.0.0 acts as a highly intelligent, self-directed developer that scouts for suitable open-source repositories or targets specific ones, identifies actionable issues or security vulnerabilities, authors fixes within a secure sandboxed environment, and pushes fully-formed Pull Requests. It even features a "PR Patrol" mode to autonomously respond to maintainer feedback.

## ✨ Key Features

- **Autonomous Discovery & Hunting:** Uses GitHub API to hunt for high-star, active repositories matching language criteria and automatically queues them for analysis.
- **Polyglot Sandbox:** Executes and validates generated code for untrusted repositories within isolated Docker networks (`internet_access` and `sandbox_isolated`) before PR submission.
- **Bloodhound Red Team Pipeline:** Employs AST-Grep and Semgrep to proactively discover vulnerabilities and code quality issues, routed through OpenRouter for White-Hat audits.
- **Issue Solving:** Automatically filters and categorizes open GitHub issues, assigning the most solvable ones to the internal LLM for resolution.
- **PR Patrol:** Scans open PRs created by Farm-Agent, evaluates maintainer review comments, generates code fixes, signs CLAs, and pushes updates autonomously.
- **Super Human Mode:** A relentless "Terminator execution loop" that operates 24/7, interleaving hunting and patrolling to maximize PR throughput up to daily API caps.
- **Local RAG Engine:** Leverages ChromaDB for an ephemeral (RAM-only) Local Retrieval-Augmented Generation engine.
- **Rich CLI:** Powered by `click` and `rich`, providing interactive execution, statistics tracking, status reporting, and leaderboard visualizations.

## 🏗️ System Architecture (High-Level)

At its core, Farm-Agent relies on an orchestrator pipeline that coordinates operations.
1. **Targeting & Discovery:** Repositories are selected either via direct URL or continuous hunting.
2. **Analysis:** The repository is cloned into a temporary directory. Code scanners and AST tools detect issues.
3. **Generation:** The AI engine (powered by Minimax, OpenRouter, or other LLMs) drafts code changes to address found issues.
4. **Validation:** The polyglot sandbox securely runs standard tests and builds to ensure no regressions.
5. **Submission:** Using `PRManager`, a fork and branch are created, changes are committed, and a Pull Request is opened on GitHub.
6. **Persistent Memory:** All run history, analyzed repos, and PR states are stored in a local SQLite database (`memory.db`), allowing continuous tracking and garbage collection.

## 🚀 Getting Started

### Prerequisites

- **Python:** 3.11, 3.12, or 3.13
- **Docker:** 7.1+ (Required for the polyglot sandbox)
- **Git:** Required for local repo manipulation

### Installation

1. Clone the canonical repository:
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. Install the package with dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
# Required GitHub Authentication
GITHUB_TOKEN=your_github_personal_access_token

# Optional Secondary Tokens for rate-limiting mitigation
GITHUB_SECONDARY_TOKENS=token1,token2

# Required LLM Provider API Key (Minimax is the primary model)
MINIMAX_API_KEY=your_minimax_api_key

# Optional OpenRouter API Key for Red Team Bloodhound audits
OPENROUTER_API_KEY=your_openrouter_api_key

# Excluded Languages (comma-separated)
EXCLUDED_LANGUAGES=javascript,typescript
```

## 💻 Usage

Farm-Agent is driven via a comprehensive CLI.

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Analyze without creating PRs (Dry Run):**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Solve open issues in a repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 5
```

**Run continuous hunt mode:**
```bash
farm_agent hunt --language python --mode both
```

**Monitor and auto-respond to PR feedback:**
```bash
farm_agent patrol
```

**Start the 24/7 Super Human loop:**
```bash
farm_agent superhuman
```

**View your submission status and stats:**
```bash
farm_agent status
farm_agent stats
```

## 🤝 Contributing

We welcome contributions! Please see our `CONTRIBUTING.md` (if available) or simply open an issue or pull request. The project strictly enforces a 100-character line limit and uses `ruff` for code linting and formatting. Ensure you run tests before submitting:

```bash
make lint
make test
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
