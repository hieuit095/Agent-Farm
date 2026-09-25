"""Security candidate closure and publication checks."""

import re

from farm_agent.core.models import ContributionType
from farm_agent.security.state import CandidateStatus, SecurityGateError


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


async def require_confirmed_security_finding(
    memory, finding, repo: str, *, target_commit: str = "", channel: str | None = None,
) -> None:
    """Reject publication unless this exact finding has commit-bound PoC evidence."""
    metadata = finding.metadata if isinstance(finding.metadata, dict) else {}
    candidate_id = metadata.get("security_candidate_id")
    commit = target_commit or metadata.get("security_target_commit")
    if (finding.type != ContributionType.SECURITY_FIX or not memory
            or not isinstance(candidate_id, str) or not candidate_id
            or not isinstance(commit, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit)):
        raise SecurityGateError(
            "Security publication requires a confirmed candidate and target SHA"
        )
    candidate = await memory.get_security_candidate(candidate_id)
    if (candidate is None or candidate["repo"] != repo
            or candidate["file_path"] != finding.file_path
            or candidate["title"] != finding.title
            or candidate["target_commit"] != commit
            or not await memory.security_candidate_is_confirmed(candidate_id, repo)):
        raise SecurityGateError("Security finding does not match confirmed PoC evidence")
    if not candidate.get("scan_id"):
        raise SecurityGateError("Confirmed finding has no scan identity")
    manifest = await memory.get_scan_manifest(candidate["scan_id"])
    if (manifest is None or manifest.scope.repo != repo
            or manifest.scope.target_commit != commit):
        raise SecurityGateError("Confirmed finding has no matching authorized scan manifest")
    if channel:
        manifest.require_publication(channel)
