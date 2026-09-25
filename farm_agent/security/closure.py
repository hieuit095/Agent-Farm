"""Single entry point for closing security candidates."""

from farm_agent.security.state import CandidateStatus


class ClosureService:
    def __init__(self, memory):
        self._memory = memory

    async def close(
        self, candidate_id: str, status: CandidateStatus, *, reason_code: str,
        evidence_id: str | None = None,
    ) -> None:
        await self._memory.close_security_candidate(
            candidate_id, status=status, reason_code=reason_code,
            evidence_id=evidence_id,
        )
