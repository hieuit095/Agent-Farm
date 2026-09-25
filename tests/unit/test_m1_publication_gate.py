"""External security publication and patrol updates require explicit proof."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from farm_agent.core.models import Contribution, ContributionType, Finding, Repository, Severity
from farm_agent.github.security_gate import handle_responsible_disclosure, run_security_gate
from farm_agent.orchestrator.memory import Memory
from farm_agent.pr.manager import PRManager
from farm_agent.pr.patrol import PRPatrol
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.evidence import evidence_hash
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError


def _finding() -> Finding:
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="Traversal", description="Untrusted filename", file_path="src/files.py",
    )


def _repo() -> Repository:
    return Repository(owner="owner", name="repo", full_name="owner/repo")


@pytest.mark.asyncio
async def test_exact_finding_and_commit_required_for_publication(tmp_path):
    memory = Memory(tmp_path / "proof.db")
    await memory.init()
    try:
        finding = _finding()
        candidate = await memory.create_security_candidate(
            scan_id="scan", repo="owner/repo", target_commit="a" * 40,
            file_path=finding.file_path, title=finding.title,
        )
        finding.metadata.update(security_candidate_id=candidate, security_target_commit="a" * 40)
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(memory, finding, "owner/repo")
        evidence = await memory.add_security_evidence(
            candidate_id=candidate, kind=EvidenceKind.POC_TRIGGERED,
            content_hash=evidence_hash(target_commit="a" * 40, observation={"exit_code": 1}),
            target_commit="a" * 40,
        )
        await memory.close_security_candidate(
            candidate, status=CandidateStatus.CONFIRMED,
            reason_code="POC_TRIGGERED", evidence_id=evidence,
        )
        await memory.store_scan_manifest(ScanManifest(
            scan_id="scan", scope=ProgramScope(
                program_id="test-program", repo="owner/repo", target_commit="a" * 40,
                policy_reference="local test authorization", allow_public_pr=True,
            ),
        ))
        await require_confirmed_security_finding(memory, finding, "owner/repo")
        for changed in (
            finding.model_copy(update={"title": "Other"}),
            finding.model_copy(update={"file_path": "src/other.py"}),
        ):
            with pytest.raises(SecurityGateError):
                await require_confirmed_security_finding(memory, changed, "owner/repo")
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, finding, "owner/repo", target_commit="b" * 40,
            )
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(memory, finding, "other/repo")
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_security_pr_and_public_issue_block_before_github_calls():
    github = MagicMock()
    github.get_authenticated_user = AsyncMock()
    github.create_issue = AsyncMock()
    manager = PRManager(github)
    contribution = Contribution(
        finding=_finding(), contribution_type=ContributionType.SECURITY_FIX,
        title="Fix", description="", changes=[],
    )
    with pytest.raises(SecurityGateError):
        await manager.create_pr(contribution, _repo())
    with pytest.raises(SecurityGateError):
        await manager._create_issue_for_finding(contribution, _repo())
    github.get_authenticated_user.assert_not_awaited()
    github.create_issue.assert_not_awaited()


@pytest.mark.asyncio
async def test_advisory_blocked_without_proof_or_side_effects(tmp_path):
    github = MagicMock()
    github.check_private_vulnerability_reporting = AsyncMock()
    github.submit_security_advisory_report = AsyncMock()
    notifier = MagicMock()
    notifier.send_message = AsyncMock()
    config = MagicMock()
    config.bounty.bounty_reports_dir = str(tmp_path)
    with pytest.raises(SecurityGateError):
        await handle_responsible_disclosure(
            github, "owner", "repo", _finding(),
            target_commit="a" * 40, config=config, notifier=notifier,
        )
    github.check_private_vulnerability_reporting.assert_not_awaited()
    github.submit_security_advisory_report.assert_not_awaited()
    notifier.send_message.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_private_disclosure_gate_rejects_unproven_finding_before_policy_lookup():
    github = MagicMock()
    github.get_file_content = AsyncMock()
    with pytest.raises(SecurityGateError):
        await run_security_gate(
            github, "owner", "repo",
            dossier=SimpleNamespace(vulnerabilities=[_finding()]),
        )
    github.get_file_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_patrol_does_not_mutate_security_or_untyped_pr():
    patrol = PRPatrol(MagicMock(), MagicMock())
    patrol._github.create_or_update_file = AsyncMock()
    for pr_type in (ContributionType.SECURITY_FIX.value, None):
        record = {"repo": "owner/repo", "type": pr_type}
        assert await patrol._handle_code_fix(
            "owner", "repo", record, {"number": 1}, MagicMock(),
        ) is False
        assert await patrol._handle_ci_failure(
            "owner", "repo", record, {"number": 1}, "trace", "test", 0,
        ) == "blocked"
    patrol._github.create_or_update_file.assert_not_awaited()
