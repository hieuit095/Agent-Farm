"""M2 proof-gate slice: tamper detection, URL redaction, after-endpoint truth.

Real loopback services, a real SQLite database and the canonical artifact store.
Loopback helpers are reused from the M2 oracle integration module.
"""

import json

import pytest

from farm_agent.core.models import ContributionType, Finding, Severity
from farm_agent.orchestrator.memory import Memory
from farm_agent.security.artifacts import ArtifactStore
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.oracles import OracleKind, _redacted_url
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import SecurityGateError
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.verifier import SemanticVerifier
from tests.integration.test_m2_oracles_real import (
    _cli_harness,
    _headers_file,
    _policy,
    _spec,
    _start_service,
    _start_witness,
    _write_spec,
)

ROLES = {"owner": {"X-Actor": "owner"}, "attacker": {"X-Actor": "attacker"}}
COMMIT = "a" * 40


def _program(origins, *, public=True):
    return ProgramScope(
        program_id="proof-gate", repo="owner/repo", target_commit=COMMIT,
        allowed_origins=origins, max_requests=16,
        test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
        allow_live_testing=True, allow_public_pr=public,
        policy_reference="fixture authorization",
        surfaces=["/idor"], risk_classes=["idor"],
        trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["id"], attacker_stories=["cross tenant read"],
    )


def _finding(candidate_id):
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR", description="fixture", file_path="src/app.py",
        metadata={"security_candidate_id": candidate_id, "security_target_commit": COMMIT},
    )


def _shutdown(*servers):
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


async def _confirm(tmp_path, *, after_mode="fixed", name="gate", secret=None):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service(after_mode, witness_url, side_effect)
    db_path = tmp_path / f"{name}.db"
    memory = Memory(db_path)
    await memory.init()
    try:
        manifest = ScanManifest(
            scan_id=f"scan-{name}", scope=_program([before, after]), mode="live",
        )
        await memory.store_scan_manifest(manifest)
        await memory.store_threat_model(ThreatModel.from_manifest(manifest))
        await memory.initialize_coverage(manifest)
        candidate_id = await memory.create_security_candidate(
            scan_id=f"scan-{name}", repo="owner/repo", target_commit=COMMIT,
            file_path="src/app.py", title="IDOR",
        )
        store = ArtifactStore(tmp_path / f"oracles-{name}")
        artifact = store.save(_poisoned_spec(before, after, secret) if secret
                              else _spec(OracleKind.IDOR, before, after))
        result = await SemanticVerifier(memory).verify_candidate(
            candidate_id, artifact, store, role_headers=ROLES,
        )
        return db_path, candidate_id, result
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))


MUTATIONS = [
    ("record_json", json.dumps({"tampered": True})),
    ("record_hash", "0" * 64),
    ("oracle_digest", "f" * 64),
    ("scan_id", "other-scan"),
    ("repo", "other/repo"),
    ("surface", "/other"),
    ("risk_class", "other-class"),
    ("evidence_hash", "0" * 64),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("column", "value"), MUTATIONS)
async def test_corrupted_proof_never_authorizes_publication(tmp_path, column, value):
    db_path, candidate_id, result = await _confirm(tmp_path)
    assert result.outcome.value == "verified"
    control = Memory(db_path)
    await control.init()
    try:
        assert await control.security_candidate_has_semantic_proof(candidate_id)
        await control._db.execute(
            f"UPDATE security_proofs SET {column} = ?", (value,),
        )
        await control._db.commit()
    finally:
        await control.close()
    reopened = Memory(db_path)
    await reopened.init()
    try:
        assert not await reopened.security_candidate_has_semantic_proof(candidate_id)
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                reopened, _finding(candidate_id), "owner/repo", channel="public_pr",
            )
    finally:
        await reopened.close()


def _poisoned_spec(before, after, secret):
    base = _spec(OracleKind.IDOR, before, after)
    return base.model_copy(update={
        field: getattr(base, field).model_copy(
            update={"url": f"{getattr(base, field).url}?token={secret}&id=7"}
        )
        for field in ("benign_before", "malicious_before", "malicious_after", "benign_after")
    })


def test_redacted_url_strips_secret_values_and_fragments():
    assert _redacted_url("http://127.0.0.1:1/x?token=SECRET#frag") == (
        "http://127.0.0.1:1/x?token=REDACTED"
    )
    assert _redacted_url("http://user:pass@127.0.0.1:1/x?a=1&b=2") == (
        "http://127.0.0.1:1/x?a=REDACTED&b=REDACTED"
    )


@pytest.mark.asyncio
async def test_probe_url_secrets_are_not_persisted_or_printed(tmp_path):
    secret = "SUPERSECRET-TOKEN-9173"
    db_path, candidate_id, _result = await _confirm(tmp_path, name="url", secret=secret)
    memory = Memory(db_path)
    await memory.init()
    try:
        proof = (await memory.list_security_proofs(candidate_id))[0]
    finally:
        await memory.close()

    record = json.loads(proof["record_json"])
    urls = [step["url"] for step in record["steps"]]
    assert all("token=REDACTED" in url and "id=REDACTED" in url for url in urls)
    assert all(secret not in url and "#" not in url and "frag" not in url for url in urls)
    assert secret not in proof["record_json"]

    # The protected canonical artifact keeps the full URL for an authorized replay.
    artifact_path = tmp_path / "oracles-url" / f"{proof['oracle_digest']}.json"
    assert secret in artifact_path.read_text(encoding="utf-8")

    # The CLI never echoes the URL or the secret on stdout/stderr.
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused2"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    try:
        cli_dir = tmp_path / "cli"
        _cli_db, command = _cli_harness(cli_dir, _policy(before, after))
        spec_path = _write_spec(cli_dir, _poisoned_spec(before, after, secret))
        headers = _headers_file(cli_dir / "headers.json")
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "IDOR",
        )
        candidate_id_cli = json.loads(candidate.stdout)["candidate_id"]
        digest = json.loads(command("register-oracle", str(spec_path)).stdout)["digest"]
        verified = command(
            "verify-candidate", candidate_id_cli, "--oracle-digest", digest,
            "--role-headers-file", str(headers),
        )
        observed = " ".join([
            scan.stdout, scan.stderr, candidate.stdout, candidate.stderr,
            verified.stdout, verified.stderr,
        ])
        assert secret not in observed
    finally:
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))


@pytest.mark.asyncio
async def test_after_endpoint_blocking_is_not_a_patch_verdict(tmp_path):
    for name, after_mode, expected_outcome, expected_after in (
        ("blocked", "fixed", "verified", "blocked"),
        ("exposed", "vulnerable", "patch_failed", "exposed"),
    ):
        db_path, candidate_id, result = await _confirm(
            tmp_path, after_mode=after_mode, name=name,
        )
        assert result.outcome.value == expected_outcome
        assert result.after_endpoint == expected_after
        assert result.patch_status == "unverified"
        memory = Memory(db_path)
        await memory.init()
        try:
            proof = (await memory.list_security_proofs(candidate_id))[0]
        finally:
            await memory.close()
        assert proof["after_endpoint"] == expected_after
        assert proof["patch_status"] == "unverified"
