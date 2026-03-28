"""Docker-backed sandbox execution for untrusted repositories."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container

logger = logging.getLogger(__name__)


class DockerSandbox:
    """Run commands inside ephemeral Docker containers."""

    _WORKSPACE_PATH = "/workspace"
    _POLL_INTERVAL_SECONDS = 0.2
    _REMOVAL_GRACE_SECONDS = 10.0
    _TIMEOUT_EXIT_CODE = 137

    def __init__(self):
        """Initialize the Docker client from the local environment."""
        self.client = docker.from_env()

    async def run_in_sandbox(
        self,
        repo_path: str,
        command: str,
        image: str = "python:3.10-alpine",
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Run a shell command inside an ephemeral Docker container.

        Args:
            repo_path: Host path to the repository that will be mounted at `/workspace`.
            command: Shell command to execute inside the sandbox.
            image: Docker image used for the sandbox container.
            timeout: Maximum execution time in seconds before the container is killed.

        Returns:
            A dictionary with execution details including stdout, stderr, exit code,
            timeout status, image, command, container name, and run ID.

        Raises:
            FileNotFoundError: If the repository path does not exist.
            NotADirectoryError: If the repository path is not a directory.
            ValueError: If the command is empty or the timeout is invalid.
            docker.errors.DockerException: If Docker communication fails.
        """
        repo_dir = Path(repo_path).expanduser().resolve()
        if not repo_dir.exists():
            raise FileNotFoundError(f"Sandbox repository path does not exist: {repo_dir}")
        if not repo_dir.is_dir():
            raise NotADirectoryError(f"Sandbox repository path is not a directory: {repo_dir}")
        if not command.strip():
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

        logger.info("Starting sandbox container %s for %s", container_name, repo_dir)

        try:
            container = await self._start_container(
                image=image,
                command=command,
                repo_dir=repo_dir,
                container_name=container_name,
                labels=labels,
            )

            output_task = asyncio.create_task(
                asyncio.to_thread(self._capture_output, container.id)
            )
            wait_task = asyncio.create_task(
                asyncio.to_thread(self._wait_for_exit_code, container.id)
            )

            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout

            while True:
                if wait_task.done():
                    break

                if loop.time() >= deadline:
                    timed_out = True
                    logger.warning(
                        "Sandbox container %s exceeded timeout after %s seconds; killing it",
                        container_name,
                        timeout,
                    )
                    await self._kill_container(container)
                    break

                try:
                    await asyncio.to_thread(container.reload)
                    if container.status in {"exited", "dead"}:
                        break
                except NotFound:
                    if wait_task.done():
                        break

                await asyncio.sleep(self._POLL_INTERVAL_SECONDS)

            if wait_task is not None:
                exit_code = await self._resolve_exit_code(wait_task, timed_out=timed_out)

            stdout = ""
            stderr = ""
            if output_task is not None:
                stdout, stderr = await self._resolve_output(output_task)

            await self._wait_for_container_removal(run_id)

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "container_name": container_name,
                "run_id": run_id,
                "image": image,
                "command": command,
            }
        finally:
            if container is not None:
                await self._force_remove_container(container)
                await self._wait_for_container_removal(run_id)

    async def _start_container(
        self,
        *,
        image: str,
        command: str,
        repo_dir: Path,
        container_name: str,
        labels: dict[str, str],
    ) -> Container:
        """Create and start the sandbox container."""

        def _run_container() -> Container:
            return self.client.containers.run(
                image,
                ["/bin/sh", "-lc", command],
                detach=True,
                # DEBT-05: Removed auto_remove=True — rely on explicit finally cleanup
                # block for deterministic container removal and to avoid 409 Conflict
                # warnings when the daemon races with container exit.
                working_dir=self._WORKSPACE_PATH,
                volumes={
                    str(repo_dir): {
                        "bind": self._WORKSPACE_PATH,
                        "mode": "rw",
                    }
                },
                mem_limit="512m",
                network_disabled=True,
                cap_drop=["ALL"],
                pids_limit=128,
                init=True,
                labels=labels,
                name=container_name,
            )

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

    def _wait_for_exit_code(self, container_id: str) -> int | None:
        """Wait for the container to stop and return its exit code."""
        result = self.client.api.wait(container_id, condition="not-running")
        if isinstance(result, dict):
            status_code = result.get("StatusCode")
            return int(status_code) if status_code is not None else None
        return None

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
        except asyncio.TimeoutError:
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
        except asyncio.TimeoutError:
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
