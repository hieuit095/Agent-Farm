"""Real SQLite and policy parsing checks; no simulated clients or responses."""

import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from pydantic import ValidationError

from farm_agent.core.models import ContributionType, Finding, Severity
from farm_agent.orchestrator.memory import Memory
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.evidence import evidence_hash
from farm_agent.security.scope import ProgramScope, ScanManifest, manifest_for_scan
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError
from farm_agent.security.transport import ScopedHttpClient


def program(*, public: bool = False, private: bool = False) -> ProgramScope:
    return ProgramScope(
        program_id="local-program", repo="owner/repo", target_commit="a" * 40,
        allowed_origins=["http://127.0.0.1:8088"], excluded_endpoints=["/admin/*"],
        max_requests=8, test_roles=["owner", "attacker"],
        allowed_impacts=["read_only"], allow_live_testing=True,
        allow_public_pr=public, allow_private_disclosure=private,
        policy_reference="local authorization fixture", surfaces=["/api/orders/{id}"],
        risk_classes=["idor"], trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["order_id"], attacker_stories=["cross-tenant order read"],
    )


@pytest.mark.asyncio
async def test_manifest_and_publication_are_commit_bound_in_real_sqlite(tmp_path):
    memory = Memory(tmp_path / "farm.db")
    await memory.init()
    finding = Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR", description="Cross tenant object read", file_path="src/app.py",
    )
    try:
        candidate_id = await memory.create_security_candidate(
            scan_id="scan-real", repo="owner/repo", target_commit="a" * 40,
            file_path=finding.file_path, title=finding.title,
        )
        finding.metadata.update(
            security_candidate_id=candidate_id, security_target_commit="a" * 40,
        )
        evidence_id = await memory.add_security_evidence(
            candidate_id=candidate_id, kind=EvidenceKind.POC_TRIGGERED,
            content_hash=evidence_hash(target_commit="a" * 40, observation={"marker": "seen"}),
            target_commit="a" * 40,
        )
        await memory.close_security_candidate(
            candidate_id, status=CandidateStatus.CONFIRMED,
            reason_code="POC_TRIGGERED", evidence_id=evidence_id,
        )
        with pytest.raises(SecurityGateError, match="manifest"):
            await require_confirmed_security_finding(
                memory, finding, "owner/repo", channel="public_pr",
            )
        manifest = manifest_for_scan("scan-real", "owner/repo", "a" * 40, [program(public=True)])
        assert manifest is not None
        await memory.store_scan_manifest(manifest)
        with pytest.raises(sqlite3.IntegrityError):
            await memory.store_scan_manifest(manifest)
        await memory._db.rollback()
        await require_confirmed_security_finding(memory, finding, "owner/repo", channel="public_pr")
        with pytest.raises(SecurityGateError, match="outside program scope"):
            await require_confirmed_security_finding(
                memory, finding, "owner/repo", channel="private_disclosure",
            )
        assert (await memory.get_scan_manifest("scan-real")).digest == manifest.digest
        await memory._db.execute(
            "UPDATE scan_manifests SET manifest_hash = ? WHERE scan_id = ?",
            ("0" * 64, "scan-real"),
        )
        await memory._db.commit()
        with pytest.raises(SecurityGateError, match="integrity"):
            await require_confirmed_security_finding(
                memory, finding, "owner/repo", channel="public_pr",
            )
    finally:
        await memory.close()


def test_live_scope_rejects_wrong_origin_role_impact_and_excluded_endpoint():
    manifest = ScanManifest(scan_id="scan", scope=program(), mode="live")
    manifest.require_request("http://127.0.0.1:8088/api/orders/1", "owner", "read_only")
    for url, role, impact in (
        ("http://127.0.0.1:8089/api/orders/1", "owner", "read_only"),
        ("http://127.0.0.1:8088.evil.test/api/orders/1", "owner", "read_only"),
        ("http://127.0.0.1:8088/admin/users", "owner", "read_only"),
        ("http://127.0.0.1:8088/api/orders/1", "admin", "read_only"),
        ("http://127.0.0.1:8088/api/orders/1", "owner", "destructive"),
    ):
        with pytest.raises(SecurityGateError):
            manifest.require_request(url, role, impact)
    with pytest.raises(SecurityGateError):
        ScanManifest(scan_id="offline", scope=program()).require_request(
            "http://127.0.0.1:8088/api/orders/1", "owner", "read_only",
        )


def test_policy_requires_explicit_live_limits_and_exact_commit():
    with pytest.raises(ValidationError):
        ProgramScope(
            program_id="bad", repo="owner/repo", target_commit="a" * 40,
            allow_live_testing=True, policy_reference="fixture",
        )
    assert manifest_for_scan("scan", "owner/repo", "b" * 40, [program()]) is None
    with pytest.raises(SecurityGateError, match="Ambiguous"):
        manifest_for_scan("scan", "owner/repo", "a" * 40, [program(), program()])


@pytest.mark.asyncio
async def test_real_http_uses_exact_origin_and_durable_request_budget(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        hits = 0

        def do_GET(self):
            Handler.hits += 1
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/outside")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"tenant":"alpha","id":1}')

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    memory = Memory(tmp_path / "requests.db")
    await memory.init()
    try:
        policy = program().model_copy(update={
            "allowed_origins": [origin], "max_requests": 2,
        })
        await memory.store_scan_manifest(ScanManifest(
            scan_id="live", scope=policy, mode="live",
        ))
        async with ScopedHttpClient(memory, "live") as client:
            good = await client.request(
                "GET", origin + "/api/orders/1", role="owner", impact="read_only",
            )
            assert good.status_code == 200 and b'"tenant":"alpha"' in good.body
            redirect = await client.request(
                "GET", origin + "/redirect", role="owner", impact="read_only",
            )
            assert redirect.status_code == 302
            with pytest.raises(SecurityGateError, match="budget"):
                await client.request(
                    "GET", origin + "/api/orders/2", role="owner", impact="read_only",
                )
            with pytest.raises(SecurityGateError, match="outside"):
                await client.request(
                    "GET", origin.replace("127.0.0.1", "localhost") + "/api/orders/1",
                    role="owner", impact="read_only",
                )
        assert Handler.hits == 2
        cursor = await memory._db.execute(
            "SELECT requests_used FROM scan_manifests WHERE scan_id = 'live'"
        )
        assert (await cursor.fetchone())[0] == 2
    finally:
        await memory.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
