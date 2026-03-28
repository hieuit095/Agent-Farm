# Farm-Agent Deployment Guide

Farm-Agent is designed to run 24/7 as an autonomous background agent. It has been specifically optimized for low-power edge devices (like Raspberry Pi, Orange Pi, or cheap VPS instances) with a hard memory cap of 512MB and support for both ARM64 and AMD64 architectures.

This guide covers deploying the `superhuman` mode via Docker Compose, which includes the agent, the SQLite tracking database, and the web dashboard.

---

## 1. Prerequisites

- Docker and Docker Compose installed
- A GitHub Personal Access Token (Classic) with `repo` and `read:user` scopes
- A MiniMax API Key (for the `MiniMax-M2.7` LLM)
- (Optional) Telegram Bot Token & Chat ID for notifications

---

## 2. Configuration Setup

Before launching the container, you must prepare your environment variables and configuration files.

### Step 2.1: The `.env` File

Create a `.env` file in the project root to securely pass secrets to Docker:

```shell
# .env

# GitHub Authentication
GITHUB_TOKEN=ghp_your_actual_token_here

# LLM Provider
MINIMAX_API_KEY=your_actual_minimax_key_here

# (Optional) Telegram Notifications
TELEGRAM_TOKEN=123456789:ABCDEF...
TELEGRAM_CHAT_ID=-100123456789
```

### Step 2.2: The `config.yaml` File

Copy the template configuration file:

```shell
cp config.example.yaml config.yaml
```

You can leave most defaults as they are. The secrets you configured in `.env` will automatically inject into runtime memory via environment variables (they will take precedence over any empty values in `config.yaml`).

However, you may want to tweak your **Anti-Farming** or **Super Human** settings:

```yaml
quota:
  # The SuperHuman loop will pick a random target between 1 and 5 per day.
  # It will hunt infinitely until it reaches this target.
  daily_pr_limit: 5

analysis:
  # Important: To bypass Gate 2 (farming keyword filter), critical findings
  # need to be explicitly requested.
  focus_areas: ["security", "performance", "code_quality", "bugs"]
```

---

## 3. Launching

The repository includes a ready-to-use `docker-compose.superhuman.yml` file.

### Memory & CPU Limits
The compose file restricts the container to `512MB` RAM and `0.5` CPU cores to ensure it never crashes your edge device.

### Persistent Volumes
It mounts a local `./data` directory into the container at `/app/data` to ensure that standard SQLite databases (`memory.db` for PR counts, `system.db` for logs) survive container restarts.

Launch the agent in detached mode:

```shell
docker compose -f docker-compose.superhuman.yml up -d
```

### Viewing Logs

To watch the agent at work (including its human-like Vietnamese internal thoughts):

```shell
docker compose -f docker-compose.superhuman.yml logs -f
```

---

## 4. Understanding the Super Human Loop

When running via this deployment, Farm-Agent executes `farm_agent superhuman`, which behaves as follows:

1. **Wake Up:** Generates a random daily PR target (e.g., 3 PRs).
2. **Hunt:** Automatically discovers repositories matching your criteria and runs the CodeAnalyzer.
3. **Fail-Safe Gate:** Drops any findings without a clear impact classification, or trivial findings like docstring additions.
4. **Action:** Submits PRs for surviving high-impact findings.
5. **Organic Delays:** Injects simulated typing delays and randomly spaces out API calls to prevent rate-limit bans.
6. **Patrol Mode:** Once the daily PR quota is hit, the agent stops hunting and periodically checks existing PRs for maintainer comments, writing automated code fixes in response.

---

## 5. Exposing the Web Dashboard

The Docker network exposes port `8787` for the Farm-Agent status dashboard.

If you are running this on a VPS or Edge device, you can access the dashboard by navigating to:
`http://<SERVER_IP>:8787`

The dashboard provides real-time visibility into the agent's current state, PR success rate, and active quotas.

---

## 6. Updating the Agent

To upgrade to the latest version of Farm-Agent:

```shell
git pull
docker compose -f docker-compose.superhuman.yml build
docker compose -f docker-compose.superhuman.yml up -d
```
