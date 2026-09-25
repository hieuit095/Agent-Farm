"""A real Docker container can read, but cannot modify, the canonical oracle."""

import asyncio

import docker
import pytest

from farm_agent.core.sandbox import DockerSandbox
from farm_agent.security.artifacts import ArtifactStore
from farm_agent.security.oracles import OracleKind, OracleSpec, ProbeRequest
from farm_agent.security.state import SecurityGateError


def _artifact(store):
    owner = ProbeRequest(
        method="GET", url="http://127.0.0.1:8080/orders/7", role="owner", impact="read_only",
    )
    attacker = ProbeRequest(
        method="GET", url="http://127.0.0.1:8080/orders/7", role="attacker", impact="read_only",
    )
    return store.save(OracleSpec(
        kind=OracleKind.IDOR, surface="/orders/7", risk_class="idor",
        benign_before=owner, malicious_before=attacker,
        malicious_after=attacker, benign_after=owner,
        benign_marker="order", exploit_marker="secret",
        owner_tenant="alpha", attacker_tenant="beta", object_id="7",
    ))


def test_content_addressed_artifact_detects_actual_disk_change(tmp_path):
    store = ArtifactStore(tmp_path / "oracles")
    ref = _artifact(store)
    assert store.load(ref).digest == ref.digest
    ref.path.chmod(0o666)
    ref.path.write_bytes(b"changed")
    with pytest.raises(SecurityGateError, match="hash changed"):
        store.load(ref)


@pytest.mark.asyncio
async def test_real_docker_mount_is_read_only_and_external_to_patch_workspace(tmp_path):
    try:
        sandbox = DockerSandbox()
        await asyncio.to_thread(sandbox.client.ping)
    except docker.errors.DockerException:
        pytest.skip("Docker daemon is inaccessible to this test process")

    workspace = tmp_path / "patch-workspace"
    workspace.mkdir()
    store = ArtifactStore(tmp_path / "canonical-oracles")
    ref = _artifact(store)
    original = ref.path.read_bytes()
    command = (
        "cat /oracle/oracle.json >/dev/null && "
        "if echo changed > /oracle/oracle.json 2>/dev/null; "
        "then exit 9; else echo READ_ONLY; fi"
    )
    outcome = await sandbox.run_in_sandbox(
        repo_path=str(workspace), command=command, image="python:3.12-slim-bookworm",
        timeout=30, oracle_artifact=ref, artifact_store=store,
    )
    assert outcome["exit_code"] == 0, outcome
    assert "READ_ONLY" in outcome["stdout"]
    assert ref.path.read_bytes() == original
    assert store.load(ref).digest == ref.digest
    plain = await sandbox.run_in_sandbox(
        repo_path=str(workspace), command="echo BASELINE_OK",
        image="python:3.12-slim-bookworm", timeout=30,
    )
    assert plain["exit_code"] == 0 and "BASELINE_OK" in plain["stdout"]

    nested_store = ArtifactStore(workspace / "oracles")
    nested_ref = _artifact(nested_store)
    with pytest.raises(ValueError, match="outside the patch workspace"):
        await sandbox.run_in_sandbox(
            repo_path=str(workspace), command="true", image="python:3.12-slim-bookworm",
            oracle_artifact=nested_ref, artifact_store=nested_store,
        )
