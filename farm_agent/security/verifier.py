"""Persist machine proof and coverage only after scoped live verification."""

from collections.abc import Callable

from farm_agent.security.closure import ClosureService
from farm_agent.security.coverage import CoverageOutcome
from farm_agent.security.oracles import OracleSpec, ProofOutcome, ProofResult, run_four_phase
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError
from farm_agent.security.transport import ScopedHttpClient


class SemanticVerifier:
    def __init__(self, memory):
        self._memory = memory

    async def verify_candidate(
        self, candidate_id: str, spec: OracleSpec, *,
        role_headers: dict[str, dict[str, str]],
        witness_counter: Callable[[], int] | None = None,
    ) -> ProofResult:
        candidate = await self._memory.get_security_candidate(candidate_id)
        if candidate is None or candidate["status"] not in {
            CandidateStatus.DISCOVERED, CandidateStatus.INVESTIGATING,
            CandidateStatus.CONFIRMED,
        }:
            raise SecurityGateError("Candidate is missing or cannot be verified")
        scan_id = candidate["scan_id"]
        manifest = await self._memory.get_scan_manifest(scan_id)
        threat_model = await self._memory.get_threat_model(scan_id)
        if (manifest is None or manifest.mode != "live" or threat_model is None
                or manifest.scope.repo != candidate["repo"]
                or manifest.scope.target_commit != candidate["target_commit"]
                or threat_model.target_commit != candidate["target_commit"]
                or spec.surface not in manifest.scope.surfaces
                or spec.risk_class not in manifest.scope.risk_classes
                or spec.risk_class != spec.kind.value):
            raise SecurityGateError("Oracle or candidate is outside the authorized scan")
        async with ScopedHttpClient(self._memory, scan_id) as client:
            result = await run_four_phase(
                spec, client, target_commit=candidate["target_commit"],
                role_headers=role_headers, witness_counter=witness_counter,
            )
        if result.outcome in {
            ProofOutcome.VERIFIED, ProofOutcome.PATCH_FAILED, ProofOutcome.REGRESSION,
        }:
            evidence_id = await self._memory.add_security_evidence(
                candidate_id=candidate_id, kind=EvidenceKind.SEMANTIC_PROOF,
                content_hash=result.evidence_hash,
                target_commit=candidate["target_commit"],
            )
            if candidate["status"] != CandidateStatus.CONFIRMED:
                await ClosureService(self._memory).close(
                    candidate_id, CandidateStatus.CONFIRMED,
                    reason_code="SEMANTIC_IMPACT_PROVEN", evidence_id=evidence_id,
                )
            await self._memory.record_coverage(
                scan_id, spec.surface, spec.risk_class, CoverageOutcome.TESTED,
                evidence_hash=result.evidence_hash,
            )
        else:
            if candidate["status"] != CandidateStatus.CONFIRMED:
                await ClosureService(self._memory).close(
                    candidate_id, CandidateStatus.OPEN_PROOF_GAP,
                    reason_code=f"ORACLE_{result.outcome.value.upper()}",
                )
            await self._memory.record_coverage(
                scan_id, spec.surface, spec.risk_class, CoverageOutcome.INCONCLUSIVE,
                reason_code=f"ORACLE_{result.outcome.value.upper()}",
            )
        return result
