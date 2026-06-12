import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure chromadb is mocked out
mock_chromadb = MagicMock()
sys.modules["chromadb"] = mock_chromadb

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import (
    AnalysisResult,
    ContributionType,
    Finding,
    ImpactLevel,
    Repository,
    Severity,
)
from farm_agent.orchestrator.pipeline import FarmAgentPipeline


@pytest.mark.asyncio
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch("farm_agent.core.rag.RepoIndexer")
@patch("farm_agent.analysis.mapper.RepoMapper")
async def test_process_repo_integration(mock_mapper_cls, mock_indexer_cls, mock_fetch_guidelines):
    # Setup mocks
    mock_guidelines = MagicMock()
    mock_guidelines.has_guidelines = True
    mock_guidelines.subsystem_docs = {"README.md": "content"}
    mock_guidelines.discover_subsystem_docs = AsyncMock(return_value={"README.md": "content"})
    mock_fetch_guidelines.return_value = mock_guidelines

    mock_indexer = MagicMock()
    mock_indexer_cls.return_value = mock_indexer

    mock_mapper = MagicMock()
    mock_mapper.get_module_dependencies.return_value = {
        "imports": ["src/auth.py"],
        "calls": ["src/utils.py"],
        "dependents": [],
    }
    mock_mapper_cls.return_value = mock_mapper

    # Mock the pipeline configurations
    config = FarmAgentConfig()
    config.github.token = "fake-token"
    config.storage.db_path = ":memory:"
    config.pipeline.sandbox_validation_enabled = True

    pipeline = FarmAgentPipeline(config)
    pipeline._github = MagicMock()
    pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
    pipeline._github.get_file_tree = AsyncMock(return_value=[])
    pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])

    pipeline._memory = MagicMock()
    pipeline._memory.has_analyzed = AsyncMock(return_value=False)
    pipeline._memory.get_today_pr_count = AsyncMock(return_value=0)
    pipeline._memory.get_style_guide = AsyncMock(return_value=None)
    pipeline._memory.record_analysis = AsyncMock()
    pipeline._memory.get_repo_prs = AsyncMock(return_value=[])

    # Mock analyzer.analyze to return a finding
    pipeline._analyzer = MagicMock()
    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="Vulnerability description",
        file_path="src/main.py",
        impact_level=ImpactLevel.HIGH,
    )
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(
            repo=Repository(owner="owner", name="repo", full_name="owner/repo"), findings=[finding]
        )
    )

    # Mock LLM provider for PoC Generator and Evaluator
    poc_gen_json = '{"filename": "poc.py", "content": "print()", "command": "python poc.py"}'
    evaluate_poc_json = '{"is_triggered": true, "reason": "Verified"}'
    pipeline._llm = MagicMock()
    pipeline._llm.complete = AsyncMock(side_effect=[poc_gen_json, evaluate_poc_json])

    # Mock DockerSandbox and verify_vulnerability_with_poc method
    pipeline._sandbox = MagicMock()
    pipeline._sandbox.verify_vulnerability_with_poc = AsyncMock(
        return_value={"exit_code": 1, "stdout": "", "stderr": "", "timed_out": False}
    )
    pipeline._sandbox.run_native_test_suite = AsyncMock(
        return_value={
            "exit_code": 0,
            "status": "tests_missing",
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        }
    )
    pipeline._sandbox.run_in_sandbox = AsyncMock(
        return_value={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}
    )

    # Mock generator to return a dummy contribution
    mock_contribution = MagicMock()
    mock_contribution.title = "Fix SQL Injection"
    pipeline._generator = MagicMock()
    pipeline._generator.generate = AsyncMock(return_value=mock_contribution)

    # Mock github client methods that are called during processing
    pipeline._github.get_file_content = AsyncMock(return_value="file content")
    pipeline._github.list_pull_requests = AsyncMock(return_value=[])

    # Mock _check_ai_policy
    pipeline._check_ai_policy = AsyncMock(return_value=False)

    # Mock _clone_and_patch_repo to return a fake repo path
    pipeline._clone_and_patch_repo = AsyncMock(return_value="/tmp/fake-repo")

    # Mock _layer1_expert_appraisal and _validate_findings to avoid LLM calls
    pipeline._layer1_expert_appraisal = AsyncMock(return_value=(True, "Genuine"))
    pipeline._validate_findings = AsyncMock(return_value=[finding])

    # Run _process_repo under test
    repo = Repository(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        clone_url="https://github.com/owner/repo.git",
    )

    with patch("asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        # We need mock_to_thread to return index_repo count or perform action
        mock_to_thread.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)

        # Patch the file reading to return empty dict
        with patch(
            "farm_agent.orchestrator.pipeline._read_all_repo_files_sync",
            return_value={"src/main.py": "content"},
        ) as mock_read_files:
            await pipeline._process_repo(repo, dry_run=True, max_prs=1)

            # Assert early clone occurred
            pipeline._clone_and_patch_repo.assert_called_with(repo.clone_url, [], [])

            # Assert discover_subsystem_docs called with the repo path
            mock_guidelines.discover_subsystem_docs.assert_called_with("/tmp/fake-repo")

            # Assert RAG indexing triggered
            mock_indexer.index_repo.assert_called_with("owner/repo", {"README.md": "content"})

            # Assert dependency injection populated Finding.metadata
            assert finding.metadata["module_dependencies"]["imports"] == ["src/auth.py"]
            assert finding.metadata["module_dependencies"]["calls"] == ["src/utils.py"]


@pytest.mark.asyncio
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch("farm_agent.core.rag.RepoIndexer")
@patch("farm_agent.analysis.mapper.RepoMapper")
async def test_process_repo_drops_medium_severity(
    mock_mapper_cls, mock_indexer_cls, mock_fetch_guidelines
):
    # Setup mocks
    mock_guidelines = MagicMock()
    mock_guidelines.has_guidelines = True
    mock_guidelines.subsystem_docs = {"README.md": "content"}
    mock_guidelines.discover_subsystem_docs = AsyncMock(return_value={"README.md": "content"})
    mock_fetch_guidelines.return_value = mock_guidelines

    mock_indexer = MagicMock()
    mock_indexer_cls.return_value = mock_indexer

    mock_mapper = MagicMock()
    mock_mapper_cls.return_value = mock_mapper

    # Mock the pipeline configurations
    config = FarmAgentConfig()
    config.github.token = "fake-token"
    config.storage.db_path = ":memory:"
    config.pipeline.sandbox_validation_enabled = True

    pipeline = FarmAgentPipeline(config)
    pipeline._github = MagicMock()
    pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
    pipeline._github.get_file_tree = AsyncMock(return_value=[])
    pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])

    pipeline._memory = MagicMock()
    pipeline._memory.has_analyzed = AsyncMock(return_value=False)
    pipeline._memory.get_today_pr_count = AsyncMock(return_value=0)
    pipeline._memory.get_style_guide = AsyncMock(return_value=None)
    pipeline._memory.record_analysis = AsyncMock()
    pipeline._memory.get_repo_prs = AsyncMock(return_value=[])

    # Mock analyzer.analyze to return a Severity.MEDIUM finding
    pipeline._analyzer = MagicMock()
    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.MEDIUM,
        title="SQL Injection",
        description="Vulnerability description",
        file_path="src/main.py",
        impact_level=ImpactLevel.MEDIUM,
    )
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(
            repo=Repository(owner="owner", name="repo", full_name="owner/repo"), findings=[finding]
        )
    )

    # Mock other methods to avoid calls since it should drop
    pipeline._check_ai_policy = AsyncMock(return_value=False)
    pipeline._clone_and_patch_repo = AsyncMock(return_value="/tmp/fake-repo")

    # Run _process_repo under test
    repo = Repository(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        clone_url="https://github.com/owner/repo.git",
    )

    with patch("asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        mock_to_thread.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
        with patch(
            "farm_agent.orchestrator.pipeline._read_all_repo_files_sync",
            return_value={"src/main.py": "content"},
        ):
            result = await pipeline._process_repo(repo, dry_run=True, max_prs=1)

            # Since the finding was dropped, prs_created is 0 and contributions_generated is 0
            assert result.prs_created == 0
            assert result.contributions_generated == 0
