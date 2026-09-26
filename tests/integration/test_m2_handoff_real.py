"""Both automatic entry points hand off to the operator; neither publishes alone.

External GitHub and paid LLM calls are replaced (labeled below); the manifest,
threat model, coverage, candidate, closure and publication gate are real.

Replaced collaborators: the GitHub client, LLM provider / analyzer / generator,
sandbox (returns a fixed triggered verdict), repo guidelines, dependency mapper,
file reader, validation and appraisal gates, and (for the circular entry point)
the target-discovery and Bloodhound scanner.
"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import (
    AnalysisResult,
    ContributionType,
    Finding,
    Repository,
    Severity,
)
from farm_agent.generator.poc import PoCGenerator
from farm_agent.orchestrator.memory import Memory
from farm_agent.orchestrator.pipeline import FarmAgentPipeline
from farm_agent.security.artifacts import ArtifactStore
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.oracles import OracleKind
from farm_agent.security.scope import ProgramScope
from farm_agent.security.state import SecurityGateError
from farm_agent.security.verifier import SemanticVerifier
from tests.integration.test_m2_oracles_real import _spec, _start_service, _start_witness

ROLES = {"owner": {"X-Actor": "owner"}, "attacker": {"X-Actor": "attacker"}}
COMMIT = "a" * 40
FINDING = Finding(
    type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
    title="IDOR", description="cross tenant read", file_path="src/app.py",
)


def _repo():
    return Repository(
        owner="owner", name="repo", full_name="owner/repo",
        clone_url="https://example.invalid/owner/repo.git",
    )


def _config(origins):
    config = FarmAgentConfig()
    config.bounty.live_testing_enabled = True
    config.bounty.program_scopes = [ProgramScope(
        program_id="handoff", repo="owner/repo", target_commit=COMMIT,
        allowed_origins=origins, max_requests=16,
        test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
        allow_live_testing=True, allow_public_pr=True,
        policy_reference="fixture authorization",
        surfaces=["/idor"], risk_classes=["idor"],
        trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["id"], attacker_stories=["cross tenant read"],
    )]
    return config


def _poc_llm():
    llm = MagicMock()
    llm.complete = AsyncMock(return_value='{"is_triggered": true, "reason": "confirmed"}')
    llm.close = AsyncMock()
    return llm


def _wire(pipeline, memory, tmp_path):
    pipeline._memory = memory
    pipeline._github = MagicMock()
    pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
    pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])
    pipeline._github.get_file_tree = AsyncMock(return_value=[])
    pipeline._github.get_file_content = AsyncMock(return_value="source")
    pipeline._github.get_repo_details = AsyncMock(return_value=_repo())
    pipeline._github.list_pull_requests = AsyncMock(return_value=[])
    pipeline._github.close = AsyncMock()
    pipeline._analyzer = MagicMock()
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(repo=_repo(), findings=[FINDING])
    )
    pipeline._llm = MagicMock()
    pipeline._llm.close = AsyncMock()
    pipeline._sandbox = MagicMock()
    pipeline._sandbox.run_native_test_suite = AsyncMock(
        return_value={"status": "tests_missing", "exit_code": 0}
    )
    pipeline._sandbox.verify_vulnerability_with_poc = AsyncMock(
        return_value={"exit_code": 1, "timed_out": False, "stdout": "", "stderr": "boom"}
    )
    pipeline._generator = MagicMock()
    pipeline._generator.generate = AsyncMock(return_value=MagicMock(title="Fix IDOR"))
    pipeline._check_ai_policy = AsyncMock(return_value=False)
    pipeline._clone_and_patch_repo = AsyncMock(return_value=str(tmp_path))
    pipeline._validate_findings = AsyncMock(return_value=[FINDING])
    pipeline._layer1_expert_appraisal = AsyncMock(return_value=(True, "valid"))


def _common_patches():
    guidelines = MagicMock(subsystem_docs={}, has_guidelines=False)
    guidelines.discover_subsystem_docs = AsyncMock(return_value={})
    return (
        patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines",
              new=AsyncMock(return_value=guidelines)),
        patch("farm_agent.orchestrator.pipeline._read_all_repo_files_sync", return_value={}),
        patch("farm_agent.analysis.mapper.RepoMapper"),
        patch.object(FarmAgentPipeline, "_repo_head_sha", return_value=COMMIT),
        patch("farm_agent.llm.provider.create_llm_provider", return_value=_poc_llm()),
        patch.object(PoCGenerator, "generate_poc",
                     new=AsyncMock(return_value=("poc.py", "assert False", "python poc.py"))),
    )


def _shutdown(*servers):
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


async def _only_candidate(memory):
    cursor = await memory._db.execute(
        "SELECT id, status, reason_code FROM security_candidates"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    return {"id": rows[0][0], "status": rows[0][1], "reason_code": rows[0][2]}


def _finding(candidate_id):
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR", description="fixture", file_path="src/app.py",
        metadata={"security_candidate_id": candidate_id, "security_target_commit": COMMIT},
    )


async def _assert_handoff(memory, tmp_path, before, after):
    candidate = await _only_candidate(memory)
    assert candidate["status"] == "NEEDS_MANUAL_REVIEW"
    assert candidate["reason_code"] == "SEMANTIC_PROOF_PENDING"
    with pytest.raises(SecurityGateError):
        await require_confirmed_security_finding(
            memory, _finding(candidate["id"]), "owner/repo", channel="public_pr",
        )
    store = ArtifactStore(tmp_path / "oracles")
    artifact = store.save(_spec(OracleKind.IDOR, before, after))
    result = await SemanticVerifier(memory).verify_candidate(
        candidate["id"], artifact, store, role_headers=ROLES,
    )
    assert result.outcome.value == "verified"
    promoted = await memory.get_security_candidate(candidate["id"])
    assert promoted["status"] == "CONFIRMED"
    await require_confirmed_security_finding(
        memory, _finding(candidate["id"]), "owner/repo", channel="public_pr",
    )


@pytest.mark.asyncio
async def test_standard_process_repo_hands_off_to_operator(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "standard.db")
    await memory.init()
    try:
        pipeline = FarmAgentPipeline(_config([before, after]))
        _wire(pipeline, memory, tmp_path)
        with ExitStack() as stack:
            for context in _common_patches():
                stack.enter_context(context)
            await pipeline._process_repo(_repo(), dry_run=True, max_prs=1)
        await _assert_handoff(memory, tmp_path, before, after)
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))


@pytest.mark.asyncio
async def test_run_circular_hands_off_to_operator(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "circular.db")
    await memory.init()
    try:
        pipeline = FarmAgentPipeline(_config([before, after]))
        _wire(pipeline, memory, tmp_path)
        vulnerability = SimpleNamespace(
            context_type="PRODUCTION", file="src/app.py", line=10, impact="HIGH",
            evidence_chain="chain", snippet="snip", fix="fix",
        )
        dossier = SimpleNamespace(
            vulnerabilities=[vulnerability], target_commit=COMMIT, has_bugs=lambda: True,
        )
        target = SimpleNamespace(repo_url="https://github.com/owner/repo", scanned_at=None)
        discovery = MagicMock()
        discovery.initialize = AsyncMock()
        discovery.get_next_target = AsyncMock(return_value=target)
        discovery.mark_status = AsyncMock()
        bloodhound = MagicMock()
        bloodhound.run_bloodhound = AsyncMock(return_value=dossier)
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(FarmAgentPipeline, "_init_components", new=AsyncMock())
            )
            stack.enter_context(
                patch.object(FarmAgentPipeline, "_cleanup", new=AsyncMock())
            )
            stack.enter_context(patch(
                "farm_agent.orchestrator.pipeline.DatabaseTargetDiscovery",
                return_value=discovery,
            ))
            stack.enter_context(patch(
                "farm_agent.orchestrator.pipeline.BloodhoundAnalyzer",
                return_value=bloodhound,
            ))
            for context in _common_patches():
                stack.enter_context(context)
            await pipeline.run_circular(json_path=str(tmp_path / "targets.json"), dry_run=True)
        await _assert_handoff(memory, tmp_path, before, after)
    finally:
        await memory.close()
        _shutdown((before_server, before_thread), (after_server, after_thread),
                  (witness_server, witness_thread))
