"""The standard security path cannot generate a fix without an executable proof."""

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_status", "generator_called"),
    [
        ("missing_poc", "OPEN_PROOF_GAP", False),
        ("timeout", "OPEN_PROOF_GAP", False),
        ("invalid_evaluator", "OPEN_PROOF_GAP", False),
        ("unknown_sha", "OPEN_PROOF_GAP", False),
        ("baseline_skipped", "OPEN_PROOF_GAP", False),
        ("source_missing", "OPEN_PROOF_GAP", False),
        ("triggered", "NEEDS_MANUAL_REVIEW", True),
    ],
)
async def test_standard_proof_gate(tmp_path, case, expected_status, generator_called):
    memory = Memory(tmp_path / "memory.db")
    await memory.init()
    try:
        repo = Repository(
            owner="owner", name="repo", full_name="owner/repo",
            clone_url="https://github.com/owner/repo.git",
        )
        finding = Finding(
            type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
            title="IDOR", description="cross tenant read", file_path="src/app.py",
        )
        pipeline = FarmAgentPipeline(FarmAgentConfig())
        pipeline._memory = memory
        pipeline._github = MagicMock()
        pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
        pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])
        pipeline._github.get_file_tree = AsyncMock(return_value=[])
        pipeline._github.get_file_content = AsyncMock(
            return_value="" if case == "source_missing" else "source"
        )
        pipeline._github.list_pull_requests = AsyncMock(return_value=[])
        pipeline._analyzer = MagicMock()
        pipeline._analyzer.analyze = AsyncMock(
            return_value=AnalysisResult(repo=repo, findings=[finding])
        )
        pipeline._generator = MagicMock()
        contribution = MagicMock(title="Fix IDOR")
        pipeline._generator.generate = AsyncMock(return_value=contribution)
        pipeline._sandbox = MagicMock()
        baseline_status = "skipped" if case == "baseline_skipped" else "tests_missing"
        pipeline._sandbox.run_native_test_suite = AsyncMock(
            return_value={"status": baseline_status, "exit_code": 0}
        )
        pipeline._sandbox.verify_vulnerability_with_poc = AsyncMock(
            return_value={
                "exit_code": 1, "timed_out": case == "timeout",
                "stdout": "", "stderr": "AssertionError: cross tenant",
            }
        )
        pipeline._llm = MagicMock()
        pipeline._check_ai_policy = AsyncMock(return_value=False)
        pipeline._clone_and_patch_repo = AsyncMock(return_value=str(tmp_path))
        pipeline._validate_findings = AsyncMock(return_value=[finding])
        pipeline._layer1_expert_appraisal = AsyncMock(return_value=(True, "valid"))

        guidelines = MagicMock(subsystem_docs={}, has_guidelines=False)
        guidelines.discover_subsystem_docs = AsyncMock(return_value={})
        poc_llm = MagicMock()
        poc_llm.complete = AsyncMock(
            return_value='{"is_triggered": true, "reason": "confirmed"}'
            if case != "invalid_evaluator" else "invalid"
        )
        poc_llm.close = AsyncMock()
        poc = (None, None, None) if case == "missing_poc" else (
            "test_poc.py", "assert False", "python test_poc.py"
        )
        sha = None if case == "unknown_sha" else "a" * 40

        with (
            patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines",
                  new=AsyncMock(return_value=guidelines)),
            patch("farm_agent.orchestrator.pipeline._read_all_repo_files_sync",
                  return_value={}),
            patch("farm_agent.analysis.mapper.RepoMapper"),
            patch.object(FarmAgentPipeline, "_repo_head_sha", return_value=sha),
            patch("farm_agent.llm.provider.create_llm_provider", return_value=poc_llm),
            patch.object(PoCGenerator, "generate_poc", new=AsyncMock(return_value=poc)),
        ):
            await pipeline._process_repo(repo, dry_run=True, max_prs=1)

        if generator_called:
            pipeline._generator.generate.assert_awaited()
        else:
            pipeline._generator.generate.assert_not_awaited()
        cursor = await memory._db.execute("SELECT status FROM security_candidates")
        assert (await cursor.fetchone())[0] == expected_status
        if case != "unknown_sha":
            pipeline._github.get_file_content.assert_awaited_with(
                "owner", "repo", "src/app.py", ref="a" * 40,
            )
    finally:
        await memory.close()
