@echo off
setlocal enabledelayedexpansion

echo =================================================================
echo         Agent-Farm (v4.0.0) Docker Quick-Start (Windows)
echo =================================================================

:: 1. Check/initialize .env file
echo [+] Checking for .env file...
if not exist .env (
    if exist .env.example (
        echo [+] Creating .env from .env.example...
        copy .env.example .env
        echo [!] Please configure your .env file with GITHUB_TOKEN and API keys.
    ) else (
        echo [!] Warning: .env file is missing, and .env.example was not found.
    )
)

:: 2. Pull the latest code from Git
echo [+] Detecting current Git branch...
set BRANCH=main
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%i

echo [+] Attempting to pull latest code from branch: %BRANCH%...
git pull origin %BRANCH%
if %ERRORLEVEL% equ 0 (
    echo [+] Git pull completed successfully.
) else (
    echo =================================================================
    echo  [!] WARNING: 'git pull' failed.
    echo  This might be due to offline status, local uncommitted changes,
    echo  or network issues. Proceeding with existing local codebase...
    echo =================================================================
)

:: 3. Build/Update the Docker image
echo [+] Building/updating the Docker image...
docker compose build
if %ERRORLEVEL% equ 0 (
    echo [+] Docker image built successfully.
) else (
    echo [!] Error: Docker build failed. Exiting.
    exit /b 1
)

:: 4. Start the daemon
echo [+] Starting Agent-Farm daemon in the background...
docker compose up -d
if %ERRORLEVEL% equ 0 (
    echo [+] Containers started successfully.
) else (
    echo [!] Error: Failed to start containers. Exiting.
    exit /b 1
)

:: 5. Provide a helpful message
echo =================================================================
echo  Agent-Farm (v4.0.0) is now running in the background.
echo.
echo  To attach to the CLI and run the agent in superhuman mode, use:
echo    docker exec -it agent-farm farm_agent superhuman
echo.
echo  To view the running logs, use:
echo    docker compose logs -f
echo =================================================================

pause
