# Agent-Farm

![Python](https://img.shields.io/badge/Python-%3E%3D3.11-blue?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%3E%3D7.1-blue?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Overview

Agent-Farm is a robust, autonomous AI agent system designed to auto-discover open-source GitHub repositories and contribute to them 24/7. It operates as a fully independent software engineer—from codebase reconnaissance and vulnerability hunting to running local sandboxed QA tests and opening PRs.

## Key Features

*   **Omniscient Context Engine**: Uses ChromaDB-backed RAG to semantically index repository subsystem documentation before generating fixes, ensuring precise contextual alignment.
*   **Dynamic Bug Verification**: Implements a DockerSandbox environment where the agent synthesizes and executes Proof-of-Concept (PoC) tests to verify bugs *before* generating a patch.
*   **Blast Radius & Regression Auditing**: Employs native test suite execution in an isolated sandbox post-patching to catch regressions automatically.
*   **Multi-Model LLM Engine**: Routes tasks contextually across DeepSeek, Qwen, and Gemini models via OpenRouter to optimize cost and capability.
*   **DEV-QA Bounty Loop**: An internal red-team/blue-team dynamic where generated code is heavily audited by a separate QA agent before PR submission.
*   **Super Human Mode**: A 24/7 autonomous loop featuring unpredictable organic coding delays to mimic human contribution patterns and respect GitHub API rate limits.
*   **Anti-Farming Filter**: Implements zero-tolerance checks to block low-impact or documentation-only spam PRs.
*   **Security Disclosure Gate**: Automatically checks for private disclosure instructions within target repositories and routes critical vulnerabilities accordingly.
*   **PR Janitor**: A ruthless, independent sweeper that leverages Minimax LLM to scan and destroy garbage/exploratory PRs.

## System Architecture

Agent-Farm is orchestrated primarily via a central pipeline (`FarmAgentPipeline`):

1.  **Discovery**: Scans GitHub for active repositories matching predefined language and activity criteria.
2.  **Analysis**: Clones the repo and uses Bloodhound (ast-grep + Semgrep) coupled with LLM appraisal to uncover vulnerabilities.
3.  **Generation & Sandbox**: Triggers a DEV-QA loop where code fixes are generated, PoCs are written and tested, and regression tests are run natively in a Docker container.
4.  **Audit**: A Layer 2 Supreme Auditor (Gemini) makes the final decision on whether to submit the patch.
5.  **Submission**: If approved, pushes the branch to a fork and creates a pull request on the origin repository.

## Getting Started

### Prerequisites

*   Python >= 3.11
*   Docker >= 7.1

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/hieuit095/Agent-Farm.git
    cd Agent-Farm
    ```
2.  Run the Quick-Start Script:
    *   **Windows**:
        ```cmd
        start.bat
        ```
    *   **Unix (Linux/macOS)**:
        ```bash
        chmod +x start.sh
        ./start.sh
        ```

### Environment Variables

Configure your environment by duplicating `.env.example` to `.env` and setting the necessary tokens:

```env
GITHUB_TOKEN=your_github_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
MINIMAX_API_KEY=your_minimax_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

## Usage

Agent-Farm features a comprehensive CLI for managing autonomous contributions:

**Attach to the Agent CLI:**
```bash
docker exec -it agent-farm farm_agent superhuman
```

**Run the pipeline organically:**
```bash
farm_agent run
```

**Target a specific repository:**
```bash
farm_agent target https://github.com/owner/repo
```

**Launch aggressive hunt mode:**
```bash
farm_agent hunt --rounds 5
```

**Start the 24/7 Super Human loop:**
```bash
farm_agent superhuman
```

## Contributing

We welcome white-hat security researchers and AI engineers to contribute! Please follow conventional commit formats and ensure all patches are validated locally using our test suites.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
