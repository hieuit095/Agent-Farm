"""Proof-record retrievability, contradiction invalidation and evidence ownership.

Real collaborators: loopback vulnerable/fixed/empty services, a real SQLite
database and the canonical artifact store. No mock stands in for a security
decision. The loopback helpers are reused from the M2 oracle integration module.
"""

import hashlib
import json

import pytest

from farm_agent.core.models import ContributionType, Finding, Severity
from farm_agent.orchestrator.memory import Memory
from farm_agent.security.artifacts import ArtifactStore
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.evidence import evidence_hash
from farm_agent.security.oracles import OracleKind, ProofOutcome
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.verifier import SemanticVerifier
from tests.integration.test_m2_oracles_real import _spec, _start_service, _start_witness

ROLES = {"owner": {"X-Actor": "owner"}, "attacker": {"X-Actor": "attacker"}}
COMMIT = "a" * 40


def _program(origins, *, max_requests=8, public=True):
    return ProgramScope(
        program_id="proof-integrity", repo="owner/repo", target_commit=COMMIT,
        allowed_origins=origins, max_requests=max_requests,
        test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
        allow_live_testing=True, allow_public_pr=public,
        policy_reference="local fixture authorization",
        surfaces=["/idor"], risk_classes=["idor"],
        trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["id"], attacker_stories=["cross tenant read"],
    )


async def _scan(memory, program, scan_id="proof-scan"):
    manifest = ScanManifest(scan_id=scan_id, scope=program, mode="live")
    await memory.store_scan_manifest(manifest)
    await memory.store_threat_model(ThreatModel.from_manifest(manifest))
    await memory.initialize_coverage(manifest)
    return manifest


async def _candidate(memory, *, file_path="src/app.py", title="IDOR"):
    return await memory.create_security_candidate(
        scan_id="proof-scan", repo="owner/repo", target_commit=COMMIT,
        file_path=file_path, title=title,
    )


def _finding(candidate_id, *, file_path="src/app.py", title="IDOR"):
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title=title, description="fixture", file_path=file_path,
        metadata={"security_candidate_id": candidate_id, "security_target_commit": COMMIT},
    )


def _shutdown(*servers):
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.asyncio
async def test_semantic_proof_is_retrievable_redacted_and_bound(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "proof.db")
    await memory.init()
    try:
        await _scan(memory, _program([before, after]))
        candidate_id = await _candidate(memory)
        store = ArtifactStore(tmp_path / "oracles")
        artifact = store.save(_spec(OracleKind.IDOR, before, after))
        result = await SemanticVerifier(memory).verify_candidate(
            candidate_id, artifact, store, role_headers=ROLES,
        )
        assert result.outcome == ProofOutcome.VERIFIED
        proofs = await memory.list_security_proofs(candidate_id)
        assert len(proofs) == 1
        proof = proofs[0]
        assert proof["valid"] == 1
        assert proof["vulnerability_confirmed"] == 1
        assert proof["patch_status"] == "unverified"
        assert proof["after_endpoint"] == "blocked"
        assert proof["oracle_digest"] == artifact.digest
        assert proof["surface"] == "/idor" and proof["risk_class"] == "idor"

        record = json.loads(proof["record_json"])
        assert [step["phase"] for step in record["steps"]] == [
            "benign_before", "malicious_before", "malicious_after", "benign_after",
        ]
        assert record["oracle_digest"] == artifact.digest
        assert record["target_commit"] == COMMIT
        assert record["owner_tenant"] == "alpha" and record["attacker_tenant"] == "beta"
        assert record["object_id"] == "order-7"
        for step in record["steps"]:
            assert set(step) == {
                "phase", "method", "url", "role", "impact", "status",
                "transport_error", "body_sha256", "body_len", "witness_hits",
            }
            assert "body" not in step and "headers" not in step
            assert len(step["body_sha256"]) == 64

        recomputed = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            .encode("utf-8")
        ).hexdigest()
        assert proof["record_hash"] == recomputed
        assert result.evidence_hash == evidence_hash(target_commit=COMMIT, observation=record)
        await require_confirmed_security_finding(
            memory, _finding(candidate_id), "owner/repo", channel="public_pr",
        )
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))


@pytest.mark.asyncio
async def test_contradictory_run_invalidates_stale_proof(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    vuln_server, vuln_thread, vuln = _start_service("vulnerable", witness_url, side_effect)
    empty_server, empty_thread, empty = _start_service("empty", witness_url, side_effect)
    fixed_server, fixed_thread, fixed = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "contradiction.db")
    await memory.init()
    try:
        await _scan(memory, _program([vuln, empty, fixed], max_requests=16))
        candidate_id = await _candidate(memory)
        store = ArtifactStore(tmp_path / "oracles")
        verifier = SemanticVerifier(memory)

        result = await verifier.verify_candidate(
            candidate_id, store.save(_spec(OracleKind.IDOR, vuln, fixed)), store,
            role_headers=ROLES,
        )
        assert result.outcome == ProofOutcome.VERIFIED
        status = (await memory.get_security_candidate(candidate_id))["status"]
        assert status == CandidateStatus.CONFIRMED
        await require_confirmed_security_finding(
            memory, _finding(candidate_id), "owner/repo", channel="public_pr",
        )

        contradictory = await verifier.verify_candidate(
            candidate_id, store.save(_spec(OracleKind.IDOR, empty, fixed)), store,
            role_headers=ROLES,
        )
        assert contradictory.outcome == ProofOutcome.NOT_TRIGGERED
        proofs = await memory.list_security_proofs(candidate_id)
        assert [proof["valid"] for proof in proofs] == [0, 1]
        assert not await memory.security_candidate_has_semantic_proof(candidate_id)
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, _finding(candidate_id), "owner/repo", channel="public_pr",
            )
    finally:
        await memory.close()
        _shutdown((vuln_server, vuln_thread), (empty_server, empty_thread),
                  (fixed_server, fixed_thread), (witness_server, witness_thread))


@pytest.mark.asyncio
async def test_one_candidate_cannot_borrow_another_candidates_evidence(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "ownership.db")
    await memory.init()
    try:
        await _scan(memory, _program([before, after], max_requests=16))
        proven = await _candidate(memory, file_path="src/app.py")
        other = await _candidate(memory, file_path="src/other.py")
        store = ArtifactStore(tmp_path / "oracles")
        artifact = store.save(_spec(OracleKind.IDOR, before, after))
        await SemanticVerifier(memory).verify_candidate(
            proven, artifact, store, role_headers=ROLES,
        )
        assert await memory.security_candidate_has_semantic_proof(proven)
        assert not await memory.security_candidate_has_semantic_proof(other)
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, _finding(other, file_path="src/other.py"), "owner/repo",
                channel="public_pr",
            )
        cursor = await memory._db.execute(
            "SELECT closing_evidence_id FROM security_candidates WHERE id = ?", (proven,)
        )
        recorded = (await cursor.fetchone())[0]
        with pytest.raises(SecurityGateError):
            await memory.close_security_candidate(
                other, status=CandidateStatus.CONFIRMED,
                reason_code="BORROWED", evidence_id=recorded,
            )
        assert (await memory.get_security_candidate(other))["status"] == CandidateStatus.DISCOVERED
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))


@pytest.mark.asyncio
async def test_pending_candidate_is_blocked_then_promoted_by_operator(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "handoff.db")
    await memory.init()
    try:
        await _scan(memory, _program([before, after]))
        candidate_id = await _candidate(memory)
        evidence_id = await memory.add_security_evidence(
            candidate_id=candidate_id, kind=EvidenceKind.POC_TRIGGERED,
            content_hash="d" * 64, target_commit=COMMIT,
        )
        await memory.close_security_candidate(
            candidate_id, status=CandidateStatus.NEEDS_MANUAL_REVIEW,
            reason_code="SEMANTIC_PROOF_PENDING", evidence_id=evidence_id,
        )
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, _finding(candidate_id), "owner/repo", channel="public_pr",
            )

        store = ArtifactStore(tmp_path / "oracles")
        artifact = store.save(_spec(OracleKind.IDOR, before, after))
        result = await SemanticVerifier(memory).verify_candidate(
            candidate_id, artifact, store, role_headers=ROLES,
        )
        assert result.outcome == ProofOutcome.VERIFIED
        status = (await memory.get_security_candidate(candidate_id))["status"]
        assert status == CandidateStatus.CONFIRMED
        await require_confirmed_security_finding(
            memory, _finding(candidate_id), "owner/repo", channel="public_pr",
        )
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))
