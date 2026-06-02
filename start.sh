#!/bin/bash
# -----------------------------------------------------------------------------
# Agent-Farm 1-Click Docker Desktop Quick-Start Script (v4.0.0)
#
# NOTE FOR UNIX USERS:
# Remember to make this script executable before running:
#   chmod +x start.sh
# -----------------------------------------------------------------------------

echo "================================================================="
echo "        Agent-Farm (v4.0.0) Docker Quick-Start"
echo "================================================================="

# 1. Check/initialize .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[+] Creating .env from .env.example..."
        cp .env.example .env
        echo "[!] Please configure your .env file with GITHUB_TOKEN and API keys."
    else
        echo "[!] Warning: .env file is missing, and .env.example was not found."
    fi
fi

# 2. Pull the latest code from Git
echo "[+] Detecting current Git branch..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

echo "[+] Attempting to pull latest code from branch: $CURRENT_BRANCH..."
if git pull origin "$CURRENT_BRANCH"; then
    echo "[+] Git pull completed successfully."
else
    echo "================================================================="
    echo " [!] WARNING: 'git pull' failed."
    echo " This might be due to offline status, local uncommitted changes, "
    echo " or network issues. Proceeding with existing local codebase..."
    echo "================================================================="
fi

# 3. Build/Update the Docker image
echo "[+] Building/updating the Docker image..."
if docker compose build; then
    echo "[+] Docker image built successfully."
else
    echo "[!] Error: Docker build failed. Exiting."
    exit 1
fi

# 4. Start the daemon
echo "[+] Starting Agent-Farm daemon in the background..."
if docker compose up -d; then
    echo "[+] Containers started successfully."
else
    echo "[!] Error: Failed to start containers. Exiting."
    exit 1
fi

# 5. Provide a helpful message
echo "================================================================="
echo " Agent-Farm (v4.0.0) is now running in the background."
echo ""
echo " To attach to the CLI and run the agent in superhuman mode, use:"
echo "   docker exec -it agent-farm farm_agent superhuman"
echo ""
echo " To view the running logs, use:"
echo "   docker compose logs -f"
echo "================================================================="
