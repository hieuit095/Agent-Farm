"""Real negative cases: forged digest, role collision, concurrent budget,
restart persistence and a candidate/manifest commit mismatch.

Loopback HTTP services and real SQLite only; the oracle helpers are reused from
the M2 oracle integration module.
"""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from farm_agent.orchestrator.memory import Memory
from farm_agent.security.artifacts import ArtifactRef, ArtifactStore
from farm_agent.security.oracles import (
    OracleKind,
    OracleSpec,
    ProbeRequest,
    run_four_phase,
)
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import SecurityGateError
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.transport import ScopedHttpClient
from farm_agent.security.verifier import SemanticVerifier
from tests.integration.test_m2_oracles_real import _spec, _start_service, _start_witness

ROLES = {"owner": {"X-Actor": "owner"}, "attacker": {"X-Actor": "attacker"}}


def _ok_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _program(origin, *, max_requests=1, roles=("owner", "attacker"), surfaces=("/idor",)):
    return ProgramScope(
        program_id="negatives", repo="owner/repo", target_commit="a" * 40,
        allowed_origins=[origin], max_requests=max_requests,
        test_roles=list(roles), allowed_impacts=["read_only"],
        allow_live_testing=True, policy_reference="fixture authorization",
        surfaces=list(surfaces), risk_classes=["idor"],
        trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["id"], attacker_stories=["cross tenant read"],
    )


def _shutdown(*servers):
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_forged_oracle_digest_is_rejected(tmp_path):
    store = ArtifactStore(tmp_path / "oracles")
    forged = ArtifactRef(store.root / f"{'0' * 64}.json", "0" * 64)
    with pytest.raises(SecurityGateError, match="missing"):
        store.load(forged)


@pytest.mark.asyncio
async def test_identical_idor_roles_are_rejected_before_probing(tmp_path):
    server, thread, origin = _ok_server()
    memory = Memory(tmp_path / "roles.db")
    await memory.init()
    try:
        await memory.store_scan_manifest(
            ScanManifest(scan_id="roles", scope=_program(origin, roles=("owner",)), mode="live")
        )
        probe = ProbeRequest(method="GET", url=f"{origin}/idor", role="owner", impact="read_only")
        spec = OracleSpec(
            kind=OracleKind.IDOR, surface="/idor", risk_class="idor",
            benign_before=probe, malicious_before=probe,
            malicious_after=probe, benign_after=probe,
            benign_marker="b", exploit_marker="e",
            owner_tenant="alpha", attacker_tenant="beta", object_id="order-7",
        )
        async with ScopedHttpClient(memory, "roles") as client:
            with pytest.raises(SecurityGateError, match="differ"):
                await run_four_phase(
                    spec, client, target_commit="a" * 40, role_headers=ROLES,
                )
        cursor = await memory._db.execute(
            "SELECT requests_used FROM scan_manifests WHERE scan_id = 'roles'"
        )
        assert (await cursor.fetchone())[0] == 0
    finally:
        await memory.close()
        _shutdown((server, thread))


@pytest.mark.asyncio
async def test_concurrent_budget_consumption_is_atomic(tmp_path):
    server, thread, origin = _ok_server()
    memory = Memory(tmp_path / "concurrent.db")
    await memory.init()
    try:
        await memory.store_scan_manifest(
            ScanManifest(scan_id="conc", scope=_program(origin, max_requests=1), mode="live")
        )
        async with ScopedHttpClient(memory, "conc") as client:
            results = await asyncio.gather(
                client.request("GET", f"{origin}/idor", role="owner", impact="read_only"),
                client.request("GET", f"{origin}/idor", role="owner", impact="read_only"),
                return_exceptions=True,
            )
        accepted = [item for item in results if not isinstance(item, Exception)]
        rejected = [item for item in results if isinstance(item, Exception)]
        assert len(accepted) == 1 and len(rejected) == 1
        assert isinstance(rejected[0], SecurityGateError)
        cursor = await memory._db.execute(
            "SELECT requests_used FROM scan_manifests WHERE scan_id = 'conc'"
        )
        assert (await cursor.fetchone())[0] == 1
    finally:
        await memory.close()
        _shutdown((server, thread))


@pytest.mark.asyncio
async def test_spent_budget_survives_restart(tmp_path):
    server, thread, origin = _ok_server()
    db_path = tmp_path / "restart.db"
    memory = Memory(db_path)
    await memory.init()
    try:
        await memory.store_scan_manifest(
            ScanManifest(scan_id="restart", scope=_program(origin, max_requests=1), mode="live")
        )
        async with ScopedHttpClient(memory, "restart") as client:
            observation = await client.request(
                "GET", f"{origin}/idor", role="owner", impact="read_only",
            )
            assert observation.status_code == 200
    finally:
        await memory.close()
    reopened = Memory(db_path)
    await reopened.init()
    try:
        async with ScopedHttpClient(reopened, "restart") as client:
            with pytest.raises(SecurityGateError, match="budget"):
                await client.request(
                    "GET", f"{origin}/idor", role="owner", impact="read_only",
                )
    finally:
        await reopened.close()
        _shutdown((server, thread))


@pytest.mark.asyncio
async def test_verification_rejects_candidate_manifest_commit_mismatch(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "mismatch.db")
    await memory.init()
    try:
        manifest = ScanManifest(
            scan_id="mismatch", scope=_program(before, max_requests=4), mode="live",
        )
        await memory.store_scan_manifest(manifest)
        await memory.store_threat_model(ThreatModel.from_manifest(manifest))
        await memory.initialize_coverage(manifest)
        candidate_id = await memory.create_security_candidate(
            scan_id="mismatch", repo="owner/repo", target_commit="b" * 40,
            file_path="src/app.py", title="IDOR",
        )
        store = ArtifactStore(tmp_path / "oracles")
        artifact = store.save(_spec(OracleKind.IDOR, before, after))
        with pytest.raises(SecurityGateError):
            await SemanticVerifier(memory).verify_candidate(
                candidate_id, artifact, store, role_headers=ROLES,
            )
        candidate = await memory.get_security_candidate(candidate_id)
        assert candidate["status"] == "DISCOVERED"
        assert await memory.list_security_proofs(candidate_id) == []
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))
