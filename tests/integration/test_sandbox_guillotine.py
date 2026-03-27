"""Integration test: Sandbox Guillotine."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from contribai.core.config import ContribAIConfig, GitHubConfig, LLMConfig, AnalysisConfig, ContributionConfig, StorageConfig
from contribai.core.models import (
    Repository, Finding, Contribution, ContributionType, Severity, FileChange
)
from contribai.orchestrator.pipeline import ContribPipeline

@pytest.fixture
def pipeline_config(tmp_path):
    return ContribAIConfig(
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
        severity=Severity.MEDIUM,
        title="Syntax error injected",
        description="Bad code",
        file_path="main.py",
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
        branch_name="contribai/fix/syntax-error",
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
    
    pipeline._llm = AsyncMock()
    pipeline._llm.close = AsyncMock()
    
    pipeline._analyzer = AsyncMock()
    # Generator returning bad code
    pipeline._generator = AsyncMock()
    pipeline._generator.generate = AsyncMock(return_value=bad_contribution)
    pipeline._generator.fix_contribution_from_error = AsyncMock(return_value=bad_contribution)
    
    # Sandbox always failing
    pipeline._sandbox = AsyncMock()
    
    class MockSandboxResult:
        def __init__(self):
            self.is_success = False
            self.logs = "SyntaxError: invalid syntax"
            
    pipeline._sandbox.run_in_sandbox = AsyncMock(return_value=MockSandboxResult())
    
    # PR Manager
    pipeline._pr_manager = AsyncMock()
    pipeline._pr_manager.create_pr = AsyncMock()
    
    # Needs guidelines
    from unittest.mock import MagicMock
    guidelines = MagicMock()
    guidelines.has_guidelines = False
    
    with patch("contribai.orchestrator.pipeline.fetch_repo_guidelines", new=AsyncMock(return_value=guidelines)):
        with patch.object(pipeline, "_init_components", new=AsyncMock()):
            with patch("asyncio.sleep", new=AsyncMock()):
                # Mock analyzer to return our finding directly
                from contribai.core.models import AnalysisResult
                pipeline._analyzer.analyze = AsyncMock(return_value=AnalysisResult(
                    repo=mock_repo,
                    findings=[mock_finding],
                ))
                
                # Call the internal method that processes repos
                await pipeline._process_repo(mock_repo, dry_run=dry_run, max_prs=1)
            
    # Assertions
    # 2. sandbox should be called max_patch_retries times
    assert pipeline._sandbox.run_in_sandbox.call_count >= 1, "Sandbox Guillotine was bypassed!"

    # 1. create_pr MUST NOT BE CALLED
    pipeline._pr_manager.create_pr.assert_not_called()
