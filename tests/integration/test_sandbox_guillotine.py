"""Integration test: Sandbox Guillotine."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from farm_agent.core.config import FarmAgentConfig, GitHubConfig, LLMConfig, AnalysisConfig, ContributionConfig, StorageConfig
from farm_agent.core.models import (
    Repository, Finding, Contribution, ContributionType, Severity, FileChange, ImpactLevel
)
from farm_agent.orchestrator.pipeline import ContribPipeline

@pytest.fixture
def pipeline_config(tmp_path):
    return FarmAgentConfig(
        github=GitHubConfig(token="test_token", max_prs_per_day=1),
        llm=LLMConfig(provider="minimax", api_key="test_key"),
        analysis=AnalysisConfig(enabled_analyzers=["security"]),
        generator=ContributionConfig(commit_convention="conventional"),
        storage=StorageConfig(db_path=str(tmp_path / "test.db")),
    )

@pytest.fixture
def mock_repo():
    return Repository(
        owner="testorg",
        name="testrepo",
        full_name="testorg/testrepo",
        description="Test repo",
        language="python",
        stars=500,
        forks=50,
        open_issues=10,
        default_branch="main",
        has_license=True,
    )

@pytest.fixture
def mock_finding():
    return Finding(
        type=ContributionType.CODE_QUALITY,
        severity=Severity.CRITICAL,
        title="Uninjected code injection vulnerability",
        description="Bad code",
        file_path="main.py",
        impact_level=ImpactLevel.HIGH,
    )

@pytest.fixture
def bad_contribution(mock_finding):
    return Contribution(
        finding=mock_finding,
        contribution_type=ContributionType.CODE_QUALITY,
        title="Fix syntax",
        description="Did not fix syntax",
        changes=[FileChange(path="main.py", new_content="import syntax error")],
        commit_message="fix: bad syntax",
        branch_name="farm_agent/fix/syntax-error",
    )

@pytest.fixture
def mock_memory():
    # A fixture to satisfy the exact requirement of the signature
    memory = AsyncMock()
    memory.start_run = AsyncMock(return_value="run_123")
    memory.has_analyzed = AsyncMock(return_value=False)
    memory.get_today_pr_count = AsyncMock(return_value=0)
    memory.get_repo_prs = AsyncMock(return_value=[])
    return memory


class MockSandboxResult:
    """Mock SandboxResult with proper attribute access for getattr() fallback."""
    def __init__(self):
        self.is_success = False
        self.logs = "SyntaxError: invalid syntax"


@pytest.mark.asyncio
async def test_pipeline_aborts_pr_on_sandbox_failure(pipeline_config, mock_repo, mock_finding, bad_contribution, mock_memory):
    """Test that Sandbox Guillotine stops PR creation if sandbox validation fails."""
    # Ensure dry_run=False as requested by user
    dry_run = False

    pipeline = ContribPipeline(pipeline_config)

    # Needs memory
    pipeline._memory = mock_memory

    # Mock external dependencies
    pipeline._github = AsyncMock()
    pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
    pipeline._github.get_file_tree = AsyncMock(return_value=[])
    pipeline._github.get_file_content = AsyncMock(return_value="import unused\nprint('hello')")
    pipeline._github.list_pull_requests = AsyncMock(return_value=[])
    pipeline._github.close = AsyncMock()
    pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=None)  # Prevent vibe check early-exit

    # Use MagicMock for LLM so sync methods like set_task() and close() don't return coroutines
    from unittest.mock import MagicMock
    pipeline._llm = MagicMock()
    pipeline._llm.close = MagicMock()
    pipeline._llm.set_task = MagicMock()  # sync method - must NOT be AsyncMock!

    # Analyzer - check_maintainer_vibe must return non-HOSTILE to avoid early exit
    pipeline._analyzer = MagicMock()
    pipeline._analyzer.check_maintainer_vibe = AsyncMock(return_value="FRIENDLY")
    pipeline._analyzer.analyze = AsyncMock()

    # Generator returning bad code
    pipeline._generator = MagicMock()
    pipeline._generator.generate = AsyncMock(return_value=bad_contribution)
    pipeline._generator.fix_contribution_from_error = AsyncMock(return_value=bad_contribution)

    # Sandbox always failing
    pipeline._sandbox = MagicMock()
    pipeline._sandbox.run_in_sandbox = AsyncMock(return_value=MockSandboxResult())

    # PR Manager
    pipeline._pr_manager = MagicMock()
    pipeline._pr_manager.create_pr = AsyncMock()

    # Mock AI policy check to return False (no ban)
    pipeline._check_ai_policy = AsyncMock(return_value=False)

    # Needs guidelines
    guidelines = MagicMock()
    guidelines.has_guidelines = False

    with patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines", new=AsyncMock(return_value=guidelines)):
        with patch.object(pipeline, "_init_components", new=AsyncMock()):
            with patch("asyncio.sleep", new=AsyncMock()):
                # Mock analyzer to return our finding directly
                from farm_agent.core.models import AnalysisResult
                pipeline._analyzer.analyze = AsyncMock(return_value=AnalysisResult(
                    repo=mock_repo,
                    findings=[mock_finding],
                ))

                # Mock _validate_findings to return findings unchanged (avoids llm.complete issues)
                async def mock_validate(findings, relevant_files):
                    return findings
                pipeline._validate_findings = mock_validate

                # Mock memory methods used in _process_repo
                pipeline._memory.has_analyzed = AsyncMock(return_value=False)
                pipeline._memory.get_repo_prs = AsyncMock(return_value=[])
                pipeline._memory.record_analysis = AsyncMock()
                pipeline._memory.record_pr = AsyncMock()

                # Call the internal method that processes repos
                await pipeline._process_repo(mock_repo, dry_run=dry_run, max_prs=1)

    # Assertions
    # 2. sandbox should be called at least once (Sandbox Guillotine in action)
    assert pipeline._sandbox.run_in_sandbox.call_count >= 1, "Sandbox Guillotine was bypassed!"

    # 1. create_pr MUST NOT BE CALLED (sandbox blocks it)
    pipeline._pr_manager.create_pr.assert_not_called()
