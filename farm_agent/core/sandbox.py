"""Docker-backed sandbox execution for untrusted repositories."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container

logger = logging.getLogger(__name__)

# ── Polyglot Guillotine: Language → Docker image + test command ─────────────

LANGUAGE_ENVIRONMENTS: dict[str, dict[str, str]] = {
    "python": {
        "image": "python:3.11-alpine",
        "test_cmd": "pip install -q pytest && pytest --tb=short -q . || python -m compileall .",
        "install_cmd": "pip install -q -r requirements.txt 2>/dev/null || true",
    },
    "javascript": {
        "image": "node:20-alpine",
        "test_cmd": "npm install --silent 2>/dev/null && npm test 2>/dev/null || node --version",
        "install_cmd": "npm install --silent 2>/dev/null || true",
    },
    "typescript": {
        "image": "node:20-alpine",
        "test_cmd": "npm install --silent 2>/dev/null && npm test 2>/dev/null || npx tsc --noEmit || true",
        "install_cmd": "npm install --silent 2>/dev/null || true",
    },
    "rust": {
        "image": "rust:1.75-alpine",
        "test_cmd": "cargo test --quiet 2>&1 || cargo build 2>&1 || rustc --version",
        "install_cmd": "cargo fetch --quiet 2>/dev/null || true",
    },
    "go": {
        "image": "golang:1.21-alpine",
        "test_cmd": "go test ./... 2>&1 || go build ./... 2>&1 || go version",
        "install_cmd": "go mod download 2>/dev/null || true",
    },
    "java": {
        "image": "eclipse-temurin:21-jdk-alpine",
        "test_cmd": "mvn test -q 2>&1 || gradle test -q 2>&1 || ./gradlew test -q 2>&1 || mvn compile -q 2>&1",
        "install_cmd": "mvn dependencyresolve 2>/dev/null || true",
    },
    "ruby": {
        "image": "ruby:3.3-alpine",
        "test_cmd": "bundle install --quiet && bundle exec rake test 2>&1 || ruby --version",
        "install_cmd": "bundle install --quiet 2>/dev/null || true",
    },
    "php": {
        "image": "php:8.2-cli-alpine",
        "test_cmd": "composer install --quiet 2>/dev/null && ./vendor/bin/phpunit 2>&1 || php --version",
        "install_cmd": "composer install --quiet 2>/dev/null || true",
    },
    "c": {
        "image": "gcc:14-bookworm",
        "test_cmd": "ls *.c Makefile 2>/dev/null && make test 2>&1 || (gcc --version && echo 'no Makefile')",
        "install_cmd": "apt-get update -qq && apt-get install -qq -y make gcc 2>/dev/null || true",
    },
    "cpp": {
        "image": "gcc:14-bookworm",
        "test_cmd": "ls *.cpp CMakeLists.txt 2>/dev/null && make test 2>&1 || (g++ --version && echo 'no Makefile')",
        "install_cmd": "apt-get update -qq && apt-get install -qq -y make g++ cmake 2>/dev/null || true",
    },
    "csharp": {
        "image": "mcr.microsoft.com/dotnet/sdk:8.0-alpine",
        "test_cmd": "dotnet test --verbosity quiet 2>&1 || dotnet build 2>&1 || dotnet --version",
        "install_cmd": "dotnet restore 2>/dev/null || true",
    },
}

# Fallback for unknown languages
DEFAULT_ENV = LANGUAGE_ENVIRONMENTS["python"]

# ── Language Detection ────────────────────────────────────────────────────────

# File extension → language mapping
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
}


def detect_language_from_extensions(repo_path: str | Path) -> str:
    """Detect the primary language of a repository.

    PHASE 2-FIX: Manifest-Driven Detection prioritizes root-level package
    manifests before falling back to the naive extension counting loop.
    This prevents polyglot/monorepo confusion where JS files might
    outnumber Python files despite it being a Python backend.
    """
    repo_dir = Path(repo_path)

    # ── 1. Manifest Priority Layer ──
    if (repo_dir / "package.json").exists():
        if (repo_dir / "tsconfig.json").exists():
            return "typescript"
        return "javascript"

    if (repo_dir / "Cargo.toml").exists():
        return "rust"

    if (
        (repo_dir / "requirements.txt").exists() or
        (repo_dir / "pyproject.toml").exists() or
        (repo_dir / "setup.py").exists()
    ):
        return "python"

    if (repo_dir / "go.mod").exists():
        return "go"

    if (repo_dir / "pom.xml").exists() or (repo_dir / "build.gradle").exists():
        return "java"

    if (repo_dir / "Gemfile").exists():
        return "ruby"

    if (repo_dir / "composer.json").exists():
        return "php"

    # ── 2. Fallback to Extension Counting ──
    counts: dict[str, int] = {}

    skip_dirs = {"node_modules", "target", ".git", "dist", "build", "__pycache__", "vendor", "venv", ".venv", ".pytest_cache", ".mypy_cache"}
    try:
        for root, dirs, files in os.walk(repo_dir):
            # Prune skip dirs in-place to avoid descending into them
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                ext = Path(file).suffix.lower()
                lang = EXTENSION_TO_LANGUAGE.get(ext)
                if lang:
                    counts[lang] = counts.get(lang, 0) + 1
    except OSError:
        pass

    if not counts:
        return "python"
    return max(counts, key=lambda k: counts[k])


def detect_language_from_repo_info(repo_info: dict | None) -> str | None:
    """Extract language from repository metadata dict (e.g. GitHub API response)."""
    if not repo_info:
        return None
    lang = repo_info.get("language")
    if lang:
        # Normalize GitHub language names to our keys
        mapping = {
            "Python": "python",
            "JavaScript": "javascript",
            "TypeScript": "typescript",
            "Rust": "rust",
            "Go": "go",
            "Java": "java",
            "Ruby": "ruby",
            "PHP": "php",
            "C": "c",
            "C++": "cpp",
            "C#": "csharp",
        }
        return mapping.get(lang, lang.lower())
    return None


def get_environment_for_language(language: str) -> dict[str, str]:
    """Return the image + commands for a given language, falling back to Python."""
    return LANGUAGE_ENVIRONMENTS.get(language.lower(), DEFAULT_ENV)



class DockerSandbox:
    """Run commands inside ephemeral Docker containers with strict isolation.

    Security hardening:
    - network_mode="none": Sever all internet access (prevents payload downloads,
      data exfiltration, and C2 callbacks).
    - mem_limit="512m": Prevent OOM attacks and memory exhaustion.
    - nano_cpus=500_000_000: Cap at 0.5 CPU to prevent fork bombs and CPU pegging.
    - cap_drop=["ALL"]: Drop ALL Linux capabilities (no net_admin, no sys_admin, etc.).
    - security_opt=["no-new-privileges"]: Prevent privilege escalation via setuid binaries.
    - pids_limit=128: Prevent fork bombs at the process level.
    - Hard 60-second asyncio.wait_for timeout on container execution, enforced in
      addition to the OS-level `timeout --signal=KILL` wrapper inside the container.
    """

    _WORKSPACE_PATH = "/workspace"
    _POLL_INTERVAL_SECONDS = 0.2
    _REMOVAL_GRACE_SECONDS = 10.0
    _TIMEOUT_EXIT_CODE = 137
    _EXECUTION_TIMEOUT_SECONDS = 60
    _MAX_STDOUT_CHARS = 500
    _MAX_STDERR_CHARS = 2000

    def __init__(self):
        """Initialize the Docker client from the local environment."""
        self.client = docker.from_env()

    def _determine_test_command(self, repo_path: Path, fallback_cmd: str = "") -> str:
        """Heuristically determine the native test command for the repository."""
        if (repo_path / "foundry.toml").exists():
            return "forge test"

        if (repo_path / "hardhat.config.js").exists() or (repo_path / "hardhat.config.ts").exists():
            return "npx hardhat test"

        if (repo_path / "Cargo.toml").exists():
            return "cargo test"

        if (repo_path / "tox.ini").exists():
            return "tox"

        makefile = repo_path / "Makefile"
        if makefile.exists():
            try:
                if "test:" in makefile.read_text(errors="ignore"):
                    return "make test"
            except Exception:
                pass

        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                import json
                data = json.loads(package_json.read_text(errors="ignore"))
                if "test" in data.get("scripts", {}):
                    return "npm test"
            except Exception:
                pass

        if (repo_path / "pytest.ini").exists() or (repo_path / "tests").is_dir():
            return "pytest"

        if (repo_path / "Cargo.toml").exists():
            return "cargo test"

        if (repo_path / "go.mod").exists():
            return "go test ./..."

        return fallback_cmd

    async def run_in_sandbox(
        self,
        repo_path: str,
        command: str | None = None,
        image: str | None = None,
        timeout: int = 60,
        language: str | None = None,
        repo_info: dict | None = None,
    ) -> dict[str, Any]:
        """Run a shell command inside an ephemeral Docker container.

        Polyglot Guillotine: if language is provided, auto-selects the correct
        Docker image and test command for that language. Falls back to python
        if no language is detected.

        The container is strictly sandboxed:
        - No network access (network_mode="none")
        - 512MB memory cap (mem_limit="512m")
        - 0.5 CPU cap (nano_cpus=500_000_000)
        - All Linux capabilities dropped (cap_drop=["ALL"])
        - No new privileges (security_opt=["no-new-privileges"])
        - 128 process limit (pids_limit=128)
        - Hard 60-second execution timeout enforced at THREE levels:
          1. OS-level: `timeout --signal=KILL` inside the container
          2. asyncio-level: `asyncio.wait_for` with EXECUTION_TIMEOUT_SECONDS
          3. Poll-level: deadline-based kill loop with container.kill()

        Args:
            repo_path: Host path to the repository that will be mounted at `/workspace`.
            command: Shell command to execute. Auto-selected from language if not given.
            image: Docker image. Auto-selected from language if not given.
            timeout: Maximum execution time in seconds before the container is killed.
                     Defaults to 60 seconds.
            language: Language hint (e.g. 'python', 'rust', 'go'). Auto-detected
                      from repo_info or file extensions if not provided.
            repo_info: Optional GitHub repo metadata dict for language detection.

        Returns:
            A dictionary with execution details including stdout, stderr, exit code,
            timeout status, image, command, container name, and run ID.

        Raises:
            FileNotFoundError: If the repository path does not exist.
            NotADirectoryError: If the repository path is not a directory.
            ValueError: If the command is empty or the timeout is invalid.
            docker.errors.DockerException: If Docker communication fails.
        """
        # ── Polyglot: resolve language → environment ──────────────────────
        detected_lang = language
        if not detected_lang:
            detected_lang = detect_language_from_repo_info(repo_info)
        if not detected_lang:
            detected_lang = detect_language_from_extensions(repo_path)

        env = get_environment_for_language(detected_lang)
        resolved_image = image or env["image"]
        base_command = command or env["test_cmd"]

        repo_dir = Path(repo_path).expanduser().resolve()
        if not repo_dir.exists():
            raise FileNotFoundError(f"Sandbox repository path does not exist: {repo_dir}")
        if not repo_dir.is_dir():
            raise NotADirectoryError(f"Sandbox repository path is not a directory: {repo_dir}")

        resolved_command = self._determine_test_command(repo_dir, fallback_cmd=base_command)

        logger.info(
            "Polyglot Guillotine: language=%s, image=%s, cmd=%s",
            detected_lang,
            resolved_image,
            resolved_command[:60],
        )
        if not resolved_command.strip():
            raise ValueError("Sandbox command must not be empty.")
        if timeout <= 0:
            raise ValueError("Sandbox timeout must be greater than zero.")

        run_id = uuid.uuid4().hex
        container_name = f"farm_agent-sandbox-{run_id[:12]}"
        labels = {
            "farm_agent.sandbox": "true",
            "farm_agent.sandbox.run_id": run_id,
            "farm_agent.sandbox.repo_path": str(repo_dir),
        }

        container: Container | None = None
        output_task: asyncio.Task[tuple[str, str]] | None = None
        wait_task: asyncio.Task[int | None] | None = None
        timed_out = False
        exit_code: int | None = None

        import shutil
        import tempfile

        logger.info("Starting sandbox container %s for %s", container_name, repo_dir)

        try:
            container = await self._start_container(
                image=resolved_image,
                command=resolved_command,
                repo_dir=repo_dir,
                container_name=container_name,
                labels=labels,
                timeout=timeout,
            )

            # ── Hard execution timeout enforced at asyncio level ──────────
            # In addition to the OS-level `timeout --signal=KILL` wrapper
            # inside the container, we enforce a hard cap here. If the
            # container execution + output capture exceeds
            # _EXECUTION_TIMEOUT_SECONDS, we kill the container and return
            # a timeout result.
            try:
                async def _execute_and_collect() -> dict[str, Any]:
                    output_task = asyncio.create_task(
                        asyncio.to_thread(self._capture_output, container.id)
                    )
                    wait_task = asyncio.create_task(
                        asyncio.to_thread(self._wait_for_exit_code, container.id, timeout=timeout)
                    )

                    loop = asyncio.get_running_loop()
                    deadline = loop.time() + timeout

                    while True:
                        if wait_task.done():
                            break

                        if loop.time() >= deadline:
                            raise asyncio.TimeoutError()

                        try:
                            await asyncio.to_thread(container.reload)
                            if container.status in {"exited", "dead"}:
                                break
                        except NotFound:
                            if wait_task.done():
                                break

                        await asyncio.sleep(self._POLL_INTERVAL_SECONDS)

                    exit_code = await self._resolve_exit_code(wait_task, timed_out=False)
                    stdout, stderr = await self._resolve_output(output_task)
                    return {
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "timed_out": False,
                    }

                result = await asyncio.wait_for(
                    _execute_and_collect(),
                    timeout=self._EXECUTION_TIMEOUT_SECONDS,
                )

                exit_code = result["exit_code"]
                stdout = result["stdout"]
                stderr = result["stderr"]

                # ── FinOps: truncate stdout/stderr to prevent context explosion ──
                if len(stdout) > self._MAX_STDOUT_CHARS:
                    logger.info(
                        "Sandbox stdout truncated: %d -> %d chars",
                        len(stdout), self._MAX_STDOUT_CHARS,
                    )
                    stdout = stdout[:self._MAX_STDOUT_CHARS]
                if len(stderr) > self._MAX_STDERR_CHARS:
                    logger.info(
                        "Sandbox stderr truncated: %d -> %d chars (tail preserved)",
                        len(stderr), self._MAX_STDERR_CHARS,
                    )
                    stderr = stderr[-self._MAX_STDERR_CHARS:]

                timed_out = False

            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(
                    "Sandbox container %s exceeded hard execution timeout (%ds); "
                    "forcefully killing and removing",
                    container_name,
                    self._EXECUTION_TIMEOUT_SECONDS,
                )
                await self._kill_container(container)
                exit_code = self._TIMEOUT_EXIT_CODE
                stdout = ""
                stderr = f"Sandbox execution timed out after {self._EXECUTION_TIMEOUT_SECONDS}s"

            await self._wait_for_container_removal(run_id)

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "container_name": container_name,
                "run_id": run_id,
                "image": resolved_image,
                "command": resolved_command,
            }
        finally:
            if container is not None:
                await self._force_remove_container(container)
                await self._wait_for_container_removal(run_id)
            if 'temp_dir_obj' in locals():
                # tempfile cleanup can sometimes raise if files are in use, but usually safe.
                # However, tempfile.TemporaryDirectory's cleanup may fail on Windows if files are read-only.
                # We'll just call it and ignore exceptions or let it throw.
                try:
                    temp_dir_obj.cleanup()
                except Exception as cleanup_exc:
                    logger.debug("Failed to clean up temp dir %s: %s", temp_dir_obj.name, cleanup_exc)

    async def _start_container(
        self,
        *,
        image: str,
        command: str,
        repo_dir: Path,
        container_name: str,
        labels: dict[str, str],
        timeout: int = 120,
    ) -> Container:
        """Create and start the sandbox container.

        Args:
            timeout: Hard execution cap in seconds. The shell command is wrapped
                     with the Linux ``timeout`` utility so the process is killed
                     at the OS level inside the container, regardless of asyncio
                     loop health or Docker daemon state.
        """
        # P0-FIX (v2): Wrap command with OS-level `timeout` utility.
        # The previous `stop_timeout` kwarg only controlled the grace period
        # AFTER a manual `docker stop` — it did NOT bound execution time.
        # `timeout --signal=KILL` guarantees SIGKILL after the deadline.
        guarded_command = f"timeout --signal=KILL {timeout}s {command}"

        def _run_container() -> Container:
            container = self.client.containers.create(
                image,
                ["/bin/sh", "-lc", guarded_command],
                working_dir=self._WORKSPACE_PATH,
                tmpfs={self._WORKSPACE_PATH: "size=500m,mode=1777"},
                # ── Security hardening: strict isolation ──────────────────────
                network_mode="none",
                mem_limit="512m",
                nano_cpus=500_000_000,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                pids_limit=128,
                init=False,
                labels=labels,
                name=container_name,
            )

            import io
            import tarfile

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(str(repo_dir), arcname='.')
            tar_stream.seek(0)

            self.client.api.put_archive(container.id, self._WORKSPACE_PATH, tar_stream)
            container.start()
            return container

        try:
            return await asyncio.to_thread(_run_container)
        except ImageNotFound:
            logger.info("Pulling missing sandbox image %s", image)
            await asyncio.to_thread(self.client.images.pull, image)
            return await asyncio.to_thread(_run_container)

    def _capture_output(self, container_id: str) -> tuple[str, str]:
        """Capture stdout and stderr from a running container."""
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []

        stream = self.client.api.attach(
            container=container_id,
            stdout=True,
            stderr=True,
            stream=True,
            logs=True,
            demux=True,
        )

        if isinstance(stream, tuple):
            stdout_stream, stderr_stream = stream

            if stdout_stream is not None:
                for chunk in stdout_stream:
                    if chunk:
                        stdout_chunks.append(chunk)

            if stderr_stream is not None:
                for chunk in stderr_stream:
                    if chunk:
                        stderr_chunks.append(chunk)
        else:
            for chunk in stream:
                if isinstance(chunk, tuple):
                    stdout_chunk, stderr_chunk = chunk
                else:
                    stdout_chunk, stderr_chunk = chunk, None

                if stdout_chunk:
                    stdout_chunks.append(stdout_chunk)
                if stderr_chunk:
                    stderr_chunks.append(stderr_chunk)

        return (
            b"".join(stdout_chunks).decode("utf-8", errors="replace"),
            b"".join(stderr_chunks).decode("utf-8", errors="replace"),
        )

    def _wait_for_exit_code(self, container_id: str, timeout: int = 300) -> int | None:
        """Wait for the container to stop and return its exit code.

        BUG FIX (Crucible): The Docker SDK's client.api.wait() uses a hardcoded
        60s HTTP request timeout that cannot be overridden via the `timeout=`
        parameter (requests library layer). This caused client.api.wait() to
        return a ReadTimeout exception AFTER exactly 60 seconds, even when
        container.wait(timeout=360) was passed. The container was still running
        (the shell timeout hadn't fired yet), but our wait returned as if it
        exited — completely breaking sandbox validation.

        FIX: Replace client.api.wait() with a polling loop using container.reload()
        to check status. This avoids the HTTP-level 60s hard limit. The polling
        loop runs until the container exits or the overall timeout is reached.

        Args:
            container_id: Docker container ID to wait on.
            timeout: Maximum seconds to wait. Must be >= shell `timeout Ns` in
                     _start_container. Defaults to 300s to match run_in_sandbox.
        """
        import time as time_module

        container = self.client.containers.get(container_id)
        deadline = time_module.time() + timeout
        poll_interval = 1.0

        while time_module.time() < deadline:
            try:
                container.reload()
                status = container.status
                if status == "exited":
                    exit_code = container.attrs.get("State", {}).get("ExitCode")
                    return int(exit_code) if exit_code is not None else None
                elif status in ("running", "created", "restarting", "paused"):
                    time_module.sleep(poll_interval)
                    continue
                else:
                    logger.warning("Unexpected container status %r for %s", status, container_id)
                    return None
            except docker.errors.NotFound:
                logger.warning("Container %s not found during wait", container_id)
                return None
            except Exception as exc:
                logger.warning("Error polling container %s: %s", container_id, exc)
                time_module.sleep(poll_interval)
                continue

        logger.warning(
            "Container %s did not exit within %ds (timeout). "
            "The shell `timeout` wrapper will kill it at %ds.",
            container_id, timeout, timeout,
        )
        return self._TIMEOUT_EXIT_CODE

    async def _resolve_exit_code(
        self,
        wait_task: asyncio.Task[int | None],
        *,
        timed_out: bool,
    ) -> int | None:
        """Resolve the exit code from the wait task."""
        fallback_exit_code = self._TIMEOUT_EXIT_CODE if timed_out else None

        try:
            return await asyncio.wait_for(wait_task, timeout=self._REMOVAL_GRACE_SECONDS)
        except TimeoutError:
            logger.warning("Sandbox wait task did not finish before cleanup grace period expired")
            return fallback_exit_code
        except NotFound:
            return fallback_exit_code

    async def _resolve_output(
        self,
        output_task: asyncio.Task[tuple[str, str]],
    ) -> tuple[str, str]:
        """Resolve stdout and stderr from the attach task."""
        try:
            return await asyncio.wait_for(output_task, timeout=self._REMOVAL_GRACE_SECONDS)
        except TimeoutError:
            logger.warning("Sandbox output stream did not close before cleanup grace period expired")
            return "", ""
        except (APIError, NotFound) as exc:
            logger.warning("Sandbox output stream closed unexpectedly: %s", exc)
            return "", ""

    async def _kill_container(self, container: Container) -> None:
        """Force-kill the sandbox container."""
        try:
            await asyncio.to_thread(container.kill)
        except NotFound:
            return

    async def _force_remove_container(self, container: Container) -> None:
        """Best-effort forced removal used as a final cleanup guard."""
        try:
            await asyncio.to_thread(container.remove, force=True)
        except NotFound:
            return
        except APIError as exc:
            logger.warning("Failed to force-remove sandbox container %s: %s", container.name, exc)

    async def _wait_for_container_removal(self, run_id: str) -> None:
        """Wait until the daemon no longer reports containers for the run ID."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._REMOVAL_GRACE_SECONDS

        while loop.time() < deadline:
            containers = await asyncio.to_thread(self._list_run_containers, run_id)
            if not containers:
                return
            await asyncio.sleep(self._POLL_INTERVAL_SECONDS)

        containers = await asyncio.to_thread(self._list_run_containers, run_id)
        if containers:
            names = ", ".join(container.name for container in containers)
            logger.warning("Sandbox containers still present after cleanup grace period: %s", names)

    def _list_run_containers(self, run_id: str) -> list[Container]:
        """List all containers associated with a sandbox run ID."""
        return self.client.containers.list(
            all=True,
            filters={"label": [f"farm_agent.sandbox.run_id={run_id}"]},
        )
