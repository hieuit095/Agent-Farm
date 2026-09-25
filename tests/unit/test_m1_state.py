"""Candidate closure needs evidence bound to the same target commit."""

import asyncio

import pytest

from farm_agent.orchestrator.memory import Memory
from farm_agent.security.closure import ClosureService
from farm_agent.security.evidence import evidence_hash
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError


@pytest.mark.asyncio
async def test_candidate_closure_is_evidence_bound_and_single_use(tmp_path):
    memory = Memory(tmp_path / "state.db")
    await memory.init()
    try:
        candidate = await memory.create_security_candidate(
            scan_id="scan-1", repo="owner/repo", target_commit="a" * 40,
            file_path="src/app.py", title="IDOR",
        )
        closure = ClosureService(memory)
        with pytest.raises(SecurityGateError, match="requires evidence"):
            await closure.close(candidate, CandidateStatus.CONFIRMED, reason_code="POC_TRIGGERED")
        with pytest.raises(SecurityGateError, match="does not match"):
            await memory.add_security_evidence(
                candidate_id=candidate, kind=EvidenceKind.POC_TRIGGERED,
                content_hash="b" * 64, target_commit="other",
            )
        digest = evidence_hash(target_commit="a" * 40, observation={"exit_code": 1})
        evidence = await memory.add_security_evidence(
            candidate_id=candidate, kind=EvidenceKind.POC_TRIGGERED,
            content_hash=digest, target_commit="a" * 40,
        )
        await closure.close(
            candidate, CandidateStatus.CONFIRMED,
            reason_code="POC_TRIGGERED", evidence_id=evidence,
        )
        assert await memory.security_candidate_is_confirmed(candidate, "owner/repo")
        assert not await memory.security_candidate_is_confirmed(candidate, "other/repo")
        with pytest.raises(SecurityGateError, match="already closed"):
            await closure.close(
                candidate, CandidateStatus.RULED_OUT,
                reason_code="COUNTEREVIDENCE", evidence_id=evidence,
            )
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_proof_gap_is_not_confirmation_and_concurrent_closure_is_single_use(tmp_path):
    memory = Memory(tmp_path / "state.db")
    await memory.init()
    try:
        candidate = await memory.create_security_candidate(
            scan_id="scan-2", repo="owner/repo", target_commit="unknown",
            file_path="src/app.py", title="scanner timeout",
        )
        closure = ClosureService(memory)
        results = await asyncio.gather(
            closure.close(candidate, CandidateStatus.OPEN_PROOF_GAP, reason_code="SCAN_TIMEOUT"),
            closure.close(candidate, CandidateStatus.OPEN_PROOF_GAP, reason_code="SCAN_TIMEOUT"),
            return_exceptions=True,
        )
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, SecurityGateError) for result in results) == 1
        assert (await memory.get_security_candidate(candidate))["status"] == "OPEN_PROOF_GAP"
        assert not await memory.security_candidate_is_confirmed(candidate, "owner/repo")
    finally:
        await memory.close()
