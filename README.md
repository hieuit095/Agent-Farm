# Agent-Farm

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Docker](https://img.shields.io/badge/Docker-7.1%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Version](https://img.shields.io/badge/Version-4.0.0-purple.svg)

## Overview

Agent-Farm is an autonomous, self-healing system designed to continuously hunt for, analyze, and remediate vulnerabilities and bugs across open-source GitHub repositories. Through sophisticated pipeline orchestration, polyglot sandbox validation, and multi-layered LLM auditing, Agent-Farm automatically submits highly verified pull requests that meet the strict standards of human maintainers.

## Key Features

- **Bloodhound Red Team:** Leverages `ast-grep` and `Semgrep` to actively scan and pre-filter vulnerable patterns before invoking LLMs.
- **Dynamic Bug Verification:** Synthesizes Proof-of-Concepts (PoCs) and strictly executes them within an isolated `DockerSandbox` to confirm bug presence and patch efficacy.
- **Blast Radius & Regression Auditing:** Executes native test suites pre- and post-patch in the sandbox, ensuring fixes do not introduce regressions.
- **Omniscient Context Engine:** Employs RAG (Retrieval-Augmented Generation) codebase mapping via ChromaDB to deeply understand subsystem dependencies and maintain architectural integrity.
- **3-Cycle DEV-QA Bounty Loop:** An internal adversarial loop where a generator and an automated QA scorer iteratively refine patches until they meet hardcore quality standards.
- **Anti-Farming Filter:** A zero-tolerance gatekeeper that aggressively drops superficial, trivial, or documentation-only PRs, guaranteeing high-impact contributions.
- **Terminator Mode & Circular Target Loop:** A relentless execution loop (`farm_agent superhuman` & `farm_agent hunt-circular`) that persistently cycles through targeted repositories without artificial delays.
- **PR Patrol:** Autonomously patrols open PRs, addresses maintainer feedback, and pushes subsequent code fixes.
- **Multi-Layered Appraisal:** Harnesses Qwen (Layer 1 Appraisal) for initial severity checks and Gemini (Layer 2 Supreme Audit) for the ultimate veto on pipeline execution.

## System Architecture (High-Level)

The system is coordinated by a main orchestrator pipeline (`FarmAgentPipeline`), dividing tasks among dedicated sub-components:
1. **Reconnaissance & Discovery:** The system discovers repositories and uses the Bloodhound Red Team module to flag initial vulnerable patterns.
2. **Context Engine & Analysis:** A RAG-based context engine ingests the repo's file structures and subsystem docs to inject vital architectural knowledge.
3. **Generation & QA Loop:** The Contribution Generator writes a patch, which is immediately scrutinized by the QA Hardcore Scorer. Failed patches iterate up to three times with feedback lessons.
4. **Validation & Sandboxing:** Patches are deployed into a `DockerSandbox`. The system executes a PoC to trigger the bug, runs native tests to capture regressions, and compiles the codebase to guarantee syntactic correctness.
5. **Auditing & Submission:** A Layer 2 Supreme Auditor reviews sandbox logs and the generated patch. If approved, the `PRManager` initiates the GitHub pull request.

## Getting Started

### Prerequisites

- **Python:** `>= 3.11`
- **Docker:** `>= 7.1` (Required for `DockerSandbox` isolated patch validation)

### 1-Click Docker Launch

The most reliable way to run Agent-Farm is through the provided Docker scripts:

1. Clone the repository:
   ```bash
   git clone https://github.com/hieuit095/Agent-Farm.git
   cd Agent-Farm
   ```
2. Set up your environment variables by copying the example file:
   ```bash
   cp .env.example .env
   ```
3. Run the start script:
   - On Linux / macOS:
     ```bash
     ./start.sh
     ```
   - On Windows:
     ```cmd
     start.bat
     ```

### Environment Variables

Agent-Farm requires specific credentials to operate. Define the following in your `.env` file:

- `OPENROUTER_API_KEY`: API key for OpenRouter, used to drive core LLM generations (e.g., DeepSeek, Qwen, Gemini).
- `GITHUB_TOKEN`: Your primary GitHub Personal Access Token (requires `repo`, `read:org`, and `workflow` scopes).
- `GITHUB_SECONDARY_TOKENS`: Additional tokens for GET request rotation (comma-separated).
- `TELEGRAM_BOT_TOKEN`: Token for Telegram push notifications.
- `TELEGRAM_CHAT_ID`: Destination chat ID for Telegram.
- `SLACK_WEBHOOK_URL`: Webhook URL for Slack alerts.
- `DISCORD_WEBHOOK_URL`: Webhook URL for Discord alerts.
- `EXCLUDED_LANGUAGES`: Languages to bypass during discovery (e.g., `javascript,typescript`).
- `MINIMAX_API_KEY`: (Secondary) API key for Minimax if used.
- `MINIMAX_GROUP_ID`: (Secondary) Group ID for Minimax.

## Usage

Agent-Farm provides a rich CLI to drive operations.

**Run the pipeline on a single target:**
```bash
farm_agent target https://github.com/owner/repo
```

**Circular Target Loop:**
```bash
farm_agent hunt-circular --json-path target_repo.json
```

**Terminator Mode (Relentless Operation):**
```bash
farm_agent superhuman
```

**PR Patrol (Respond to maintainer feedback):**
```bash
farm_agent patrol
```

**Solve specific issues:**
```bash
farm_agent solve https://github.com/owner/repo --max-issues 5
```

## Contributing

We welcome open-source contributions. When contributing, please ensure you maintain testing standards and run the CI checks. Do not modify protected metadata or CI configuration files unnecessarily.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.