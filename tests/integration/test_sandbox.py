"""Live Docker integration test for the sandbox runner."""

from __future__ import annotations

import asyncio

import pytest

from farm_agent.core.sandbox import DockerSandbox


@pytest.mark.asyncio
async def test_run_in_sandbox_executes_code_and_removes_container(tmp_path):
    """Verify the sandbox writes back to the host volume and leaves no containers behind."""
    output_path = tmp_path / "sandbox_wrote_this.txt"

    sandbox = DockerSandbox()

    try:
        ping_ok = await asyncio.to_thread(sandbox.client.ping)
        assert ping_ok is True

        result = await sandbox.run_in_sandbox(
            repo_path=str(tmp_path),
            command=(
                "python -c "
                "\"from pathlib import Path; "
                "Path('sandbox_wrote_this.txt').write_text('RW Works!', encoding='utf-8'); "
                "print('Sandbox write successful!')\""
            ),
        )

        assert result["exit_code"] == 0
        assert result["timed_out"] is False
        assert "Sandbox write successful!" in result["stdout"]
        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "RW Works!"

        await _assert_no_lingering_containers(sandbox, result["run_id"])
    finally:
        sandbox.client.close()


async def _assert_no_lingering_containers(sandbox: DockerSandbox, run_id: str) -> None:
    """Poll the Docker daemon until the sandbox containers are gone."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 5.0

    while loop.time() < deadline:
        containers = await asyncio.to_thread(sandbox._list_run_containers, run_id)
        if not containers:
            return
        await asyncio.sleep(0.2)

    containers = await asyncio.to_thread(sandbox._list_run_containers, run_id)
    names = [container.name for container in containers]

    for container in containers:
        try:
            await asyncio.to_thread(container.remove, force=True)
        except Exception:
            pass

    pytest.fail(f"Lingering sandbox containers detected for run_id={run_id}: {names}")
