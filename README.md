# Farm-Agent 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Version](https://img.shields.io/badge/version-3.0.0-blue)](https://github.com/hieuit095/Farm-Agent)

Farm-Agent is a powerful, autonomous agent orchestration framework designed to automatically discover, analyze, and contribute to open-source projects on GitHub. It operates through advanced LLM-driven pipelines to identify issues, propose fixes, and submit Pull Requests with a high degree of autonomy and quality.

## Key Features

- **Autonomous Discovery & Contribution Pipeline:** Scans high-value GitHub repositories, analyzes code for bugs, missing tests, or documentation gaps, and submits high-quality Pull Requests completely autonomously.
- **Issue-First Architecture (Solver):** Finds and resolves open GitHub issues intelligently by understanding context, analyzing complexity, and applying code fixes directly.
- **PR Patrol (Auto-Response & Resolution):** Actively monitors submitted Pull Requests to read maintainer feedback, perform automatic CI fixes, sign CLAs, and reply to comments without human intervention.
- **Super Human Mode:** A continuous 24/7 operational loop with simulated human coding delays, daily PR quotas, and interleaved hunting and patrolling phases to behave like a dedicated human developer.
- **Multi-LLM Strategy & Routing:** Supports dynamic routing between models (Minimax, OpenAI, Anthropic, Gemini, Ollama) and utilizes specialized engines like the Bloodhound Red Team (OpenRouter) for security audits.
- **Persistent SQLite Memory:** Tracks analyzed repositories, submitted PRs, caching findings, and automatically builds a Knowledge Base of lessons learned from previous PR outcomes to avoid repeating architectural mistakes.

## System Architecture (High-Level)

Farm-Agent operates on a cyclic execution loop divided into distinct phases:
1. **Discovery:** Finds active repositories based on configurable constraints (stars, activity, languages).
2. **Gate:** Enforces Security Disclosure gates and anti-spam filters to ensure only high-impact repositories are targeted.
3. **Analysis:** Deeply scans codebase using AST grep, Semgrep (Sentinel Radar), and LLM static analysis.
4. **Engine:** The LLM generator drafts fixes, implements new code, or resolves GitHub issues based on analysis findings.
5. **Sandbox:** The drafted changes are applied and tested locally within an isolated Docker-based execution environment to prevent regressions.
6. **PR / Patrol:** Submits the fix via Pull Request and enters the Patrol phase to negotiate with maintainers and satisfy CI/CD checks.

## Getting Started

### Prerequisites

- **Python:** `>= 3.11`
- **Docker:** `^7.1` (Required for the isolated sandbox environment)
- **GitHub Account:** A Personal Access Token with `repo`, `read:org`, and `workflow` scopes.

### Installation

Clone the repository and install the project dependencies:

```bash
git clone https://github.com/hieuit095/Farm-Agent.git
cd Farm-Agent
pip install -e .[dev]
```

### Environment Configuration

Copy the example configuration files and fill in your keys:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Your `.env` file should include at minimum:

```env
GITHUB_TOKEN=your_github_personal_access_token
MINIMAX_API_KEY=your_minimax_api_key
OPENROUTER_API_KEY=optional_key_for_red_team_audits
TELEGRAM_BOT_TOKEN=optional_for_notifications
```

## Usage

Farm-Agent is driven entirely through a rich command-line interface.

**Target a Specific Repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Solve Issues in a Repository:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 3
```

**Run in Super Human Mode (24/7 continuous operation):**
```bash
farm_agent superhuman
```

**Check the Status of Submitted PRs:**
```bash
farm_agent status
```

**Run the PR Patrol to check for maintainer feedback:**
```bash
farm_agent patrol
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. Ensure you have run all pre-commit tests and validations using `pytest` prior to submission.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
