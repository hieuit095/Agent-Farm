# Farm-Agent 🚀

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-3.0.0-orange)
![Build](https://img.shields.io/badge/build-Docker-blue)

Farm-Agent is an autonomous system that automatically discovers open-source projects on GitHub, analyzes them for vulnerabilities or improvement opportunities, and automatically generates high-quality Pull Requests. Utilizing a state-of-the-art LLM engine, a polyglot sandbox, and a strict deterministic execution loop, Farm-Agent aims to supercharge open-source contributions.

## 🌟 Key Features

- **🧠 Super Human Mode**: A relentless 24/7 autonomous execution engine orchestrating code analysis, PR generation, and PR patrol.
- **🐳 Polyglot Sandbox**: Executes and validates generated patches locally using Docker to ensure all submitted PRs are robust and pass basic compilation/tests before submission.
- **🛡️ Red Team Auditing**: Integrated with `Semgrep` and `Bloodhound` for white-hat security auditing.
- **🔄 Circular Target Loop**: Crash-safe round-robin targeting based on a local `target_repo.json` list, maintaining state within an embedded SQLite memory.
- **🕵️ PR Patrol**: Automatically checks open PRs for maintainer review feedback, auto-responds, and generates subsequent fix commits.
- **❌ Anti-Farming Filter**: Implements zero-tolerance checks to drop spam/exploratory/documentation PRs (e.g., README fixes, format tweaks), ensuring high-impact contributions only.

## 🏗️ System Architecture (High-Level)

Farm-Agent operates heavily through the `ContribPipeline`. Its `SuperHumanLoop` runs continuously to pick targets.
1. **Discovery & Targeting**: Targets are fed through the circular target loop (`target_repo.json`).
2. **Analysis**: Uses the `BloodhoundAnalyzer` to scan for code quality and security vulnerabilities, dropping non-code and spam issues.
3. **Generation & Sandbox Validation**: An LLM agent generates patches which are subsequently verified inside a polyglot Docker sandbox. If validation fails, it triggers self-correction up to a retry limit.
4. **Pull Request & Patrol**: Validated code is submitted as a PR. `PRPatrol` keeps track of the PR's status, automatically fixing any incoming CI/CD failures or maintainer requests.

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker 7.1+ (Required for the Polyglot Sandbox execution)
- Git, Go (1.21.6), Node.js, npm, Rust (for local dev/sandbox build)

### Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/hieuit095/Farm-Agent.git
   cd Farm-Agent
   ```

2. **Install via pip**
   ```bash
   pip install -e .[dev]
   ```

   *Alternatively, build and run via Docker:*
   ```bash
   docker build -t farm_agent:latest .
   ```

### Configuration & Environment Variables

Copy the provided `.env.example` file to `.env`:
```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

**Required `.env` Variables:**
- `GITHUB_TOKEN`: Your GitHub personal access token (with `repo`, `read:org`, and `workflow` scopes).
- `MINIMAX_API_KEY`: API Key for the primary LLM provider (Minimax).
- `OPENROUTER_API_KEY`: *(Optional)* API Key for OpenRouter, used specifically by the Red Team Bloodhound audit pipeline.

## 💻 Usage

Farm-Agent is driven by its rich command-line interface.

**Target a Specific Repo:**
```bash
farm_agent target https://github.com/owner/repo
```

**Continuous Super Human Mode (Production 24/7):**
```bash
farm_agent superhuman
```

**Analyze Without PR Creation:**
```bash
farm_agent analyze https://github.com/owner/repo
```

**Auto-Solve Existing Issues:**
```bash
farm_agent solve https://github.com/owner/repo
```

**Other Useful Commands:**
- `farm_agent run`: Auto-discover repos and contribute based on criteria.
- `farm_agent status`: Show status of submitted PRs.
- `farm_agent stats`: Show overall project statistics.
- `farm_agent config`: Show current configuration.

## 🤝 Contributing & License

Farm-Agent is licensed under the MIT License. See `LICENSE` for more information. Please read the `CONTRIBUTING.md` (if available) before submitting pull requests.