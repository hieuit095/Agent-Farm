"""Tests for v2.0.0 pipeline issue-driven mode."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from contribai.core.models import (
    AnalysisResult,
    Contribution,
    ContributionType,
    FileChange,
    FileNode,
    Finding,
    PRResult,
    Repository,
    Severity,
)


@pytest.fixture
def sample_pipeline(sample_config):
    """Create a pipeline instance for testing."""
    from contribai.orchestrator.pipeline import ContribPipeline

    return ContribPipeline(sample_config)


class TestIdentifyKeyFiles:
    def test_finds_readme_and_config(self, sample_pipeline, sample_repo):
        file_tree = [
            FileNode(path="README.md", type="blob", size=100, sha="a"),
            FileNode(path="setup.py", type="blob", size=100, sha="b"),
            FileNode(path="src/main.py", type="blob", size=100, sha="c"),
            FileNode(path="tests/test_main.py", type="blob", size=100, sha="d"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, sample_repo)
        assert "README.md" in keys
        assert "setup.py" in keys

    def test_finds_python_entry_points(self, sample_pipeline):
        repo = Repository(
            owner="a",
            name="b",
            full_name="a/b",
            language="python",
            default_branch="main",
        )
        file_tree = [
            FileNode(path="myapp/__init__.py", type="blob", size=100, sha="a"),
            FileNode(path="myapp/main.py", type="blob", size=200, sha="b"),
            FileNode(path="myapp/cli.py", type="blob", size=150, sha="c"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, repo)
        assert any("__init__.py" in k for k in keys)

    def test_finds_javascript_entry_points(self, sample_pipeline):
        repo = Repository(
            owner="a",
            name="b",
            full_name="a/b",
            language="JavaScript",
            default_branch="main",
        )
        file_tree = [
            FileNode(path="package.json", type="blob", size=100, sha="a"),
            FileNode(path="src/index.js", type="blob", size=200, sha="b"),
            FileNode(path="src/app.js", type="blob", size=150, sha="c"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, repo)
        assert "package.json" in keys

    def test_finds_src_dir_files(self, sample_pipeline, sample_repo):
        file_tree = [
            FileNode(path="src/module_a.py", type="blob", size=100, sha="a"),
            FileNode(path="src/module_b.py", type="blob", size=100, sha="b"),
            FileNode(path="lib/helper.py", type="blob", size=100, sha="c"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, sample_repo)
        assert "src/module_a.py" in keys or "src/module_b.py" in keys

    def test_max_15_files(self, sample_pipeline, sample_repo):
        file_tree = [
            FileNode(path=f"src/file_{i}.py", type="blob", size=100, sha=str(i)) for i in range(30)
        ]
        keys = sample_pipeline._identify_key_files(file_tree, sample_repo)
        assert len(keys) <= 15

    def test_skips_tree_nodes(self, sample_pipeline, sample_repo):
        file_tree = [
            FileNode(path="src", type="tree", size=0, sha="a"),
            FileNode(path="src/main.py", type="blob", size=100, sha="b"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, sample_repo)
        assert "src" not in keys

    def test_contributing_md(self, sample_pipeline, sample_repo):
        file_tree = [
            FileNode(path="CONTRIBUTING.md", type="blob", size=100, sha="a"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, sample_repo)
        assert "CONTRIBUTING.md" in keys

    def test_finds_go_files(self, sample_pipeline):
        repo = Repository(
            owner="a",
            name="b",
            full_name="a/b",
            language="Go",
            default_branch="main",
        )
        file_tree = [
            FileNode(path="go.mod", type="blob", size=100, sha="a"),
            FileNode(path="cmd/main.go", type="blob", size=200, sha="b"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, repo)
        assert "go.mod" in keys

    def test_finds_rust_files(self, sample_pipeline):
        repo = Repository(
            owner="a",
            name="b",
            full_name="a/b",
            language="Rust",
            default_branch="main",
        )
        file_tree = [
            FileNode(path="Cargo.toml", type="blob", size=100, sha="a"),
            FileNode(path="src/main.rs", type="blob", size=200, sha="b"),
            FileNode(path="src/lib.rs", type="blob", size=150, sha="c"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, repo)
        assert "Cargo.toml" in keys

    def test_unknown_language(self, sample_pipeline):
        repo = Repository(
            owner="a",
            name="b",
            full_name="a/b",
            language="Brainfuck",
            default_branch="main",
        )
        file_tree = [
            FileNode(path="README.md", type="blob", size=100, sha="a"),
        ]
        keys = sample_pipeline._identify_key_files(file_tree, repo)
        assert "README.md" in keys


class TestPipelineHuntMode:
    def test_hunt_has_mode_param(self, sample_pipeline):
        import inspect

        sig = inspect.signature(sample_pipeline.hunt)
        assert "mode" in sig.parameters
        assert sig.parameters["mode"].default == "both"


class TestPipelineResult:
    def test_pipeline_result_defaults(self):
        from contribai.orchestrator.pipeline import PipelineResult

        result = PipelineResult()
        assert result.repos_analyzed == 0
        assert result.findings_total == 0
        assert result.contributions_generated == 0
        assert result.prs_created == 0
        assert result.prs == []
        assert result.errors == []


class TestCiFailureHandling:
    @pytest.mark.asyncio
    async def test_failed_ci_is_left_open_for_patrol(
        self,
        sample_pipeline,
        sample_repo,
        sample_finding,
    ):
        sample_pipeline._github = AsyncMock()
        sample_pipeline._memory = AsyncMock()
        sample_pipeline._github._get = AsyncMock(return_value={"object": {"sha": "abc123"}})
        sample_pipeline._github.get_combined_status = AsyncMock(
            return_value={"state": "failure", "failed": ["typecheck"], "total": 1}
        )
        sample_pipeline._github.close_pull_request = AsyncMock()
        sample_pipeline._memory.update_pr_status = AsyncMock()

        contribution = Contribution(
            title="Fix a CI issue",
            description="",
            contribution_type=ContributionType.CODE_QUALITY,
            finding=sample_finding,
            changes=[],
        )
        pr_result = PRResult(
            repo=sample_repo,
            contribution=contribution,
            pr_number=7,
            pr_url="https://github.com/testowner/testrepo/pull/7",
            branch_name="fix/test",
            fork_full_name="forkowner/testrepo",
        )

        await sample_pipeline._check_ci_and_close_if_failed(
            pr_result,
            sample_repo,
            max_wait_sec=1,
            poll_interval=1,
        )

        sample_pipeline._github.close_pull_request.assert_not_awaited()
        sample_pipeline._memory.update_pr_status.assert_not_awaited()
        sample_pipeline._github.get_combined_status.assert_awaited_once_with(
            sample_repo.owner,
            sample_repo.name,
            "abc123",
        )

    @pytest.mark.asyncio
    async def test_missing_check_runs_returns_without_waiting_full_timeout(
        self,
        sample_pipeline,
        sample_repo,
        sample_finding,
    ):
        sample_pipeline._github = AsyncMock()
        sample_pipeline._memory = AsyncMock()
        sample_pipeline._github._get = AsyncMock(return_value={"object": {"sha": "abc123"}})
        sample_pipeline._github.get_combined_status = AsyncMock(
            return_value={"state": "pending", "failed": [], "passed": [], "total": 0}
        )
        sample_pipeline._github.close_pull_request = AsyncMock()
        sample_pipeline._memory.update_pr_status = AsyncMock()

        contribution = Contribution(
            title="Fix a CI issue",
            description="",
            contribution_type=ContributionType.CODE_QUALITY,
            finding=sample_finding,
            changes=[],
        )
        pr_result = PRResult(
            repo=sample_repo,
            contribution=contribution,
            pr_number=8,
            pr_url="https://github.com/testowner/testrepo/pull/8",
            branch_name="fix/test",
            fork_full_name="forkowner/testrepo",
        )

        await sample_pipeline._check_ci_and_close_if_failed(
            pr_result,
            sample_repo,
            max_wait_sec=1,
            poll_interval=1,
        )

        sample_pipeline._github.close_pull_request.assert_not_awaited()
        sample_pipeline._memory.update_pr_status.assert_not_awaited()
        sample_pipeline._github.get_combined_status.assert_awaited_once()


class TestGenerationContext:
    @pytest.mark.asyncio
    async def test_process_repo_passes_github_client_to_generator(
        self,
        sample_pipeline,
        sample_repo,
        sample_finding,
        monkeypatch,
    ):
        sample_pipeline._github = AsyncMock()
        sample_pipeline._memory = AsyncMock()
        sample_pipeline._analyzer = AsyncMock()
        sample_pipeline._generator = AsyncMock()

        monkeypatch.setattr(
            "contribai.orchestrator.pipeline.fetch_repo_guidelines",
            AsyncMock(return_value=SimpleNamespace(has_guidelines=False)),
        )
        sample_pipeline._check_ai_policy = AsyncMock(return_value=False)
        sample_pipeline._memory.record_analysis = AsyncMock()
        sample_pipeline._memory.get_repo_prs = AsyncMock(return_value=[])
        sample_pipeline._github.get_file_tree = AsyncMock(return_value=[])
        sample_pipeline._github.get_file_content = AsyncMock(return_value="const token = localStorage.getItem('gh');")
        sample_pipeline._github.list_pull_requests = AsyncMock(return_value=[])
        sample_pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
        sample_pipeline._validate_findings = AsyncMock(return_value=[sample_finding])
        sample_pipeline._analyzer.analyze = AsyncMock(
            return_value=AnalysisResult(
                repo=sample_repo,
                findings=[sample_finding],
                analyzed_files=1,
                analysis_duration_sec=0.1,
            )
        )
        sample_pipeline._generator.generate = AsyncMock(
            return_value=Contribution(
                title="Fix local token storage",
                description="",
                contribution_type=ContributionType.SECURITY_FIX,
                finding=sample_finding,
                changes=[
                    FileChange(
                        path=sample_finding.file_path,
                        original_content="before",
                        new_content="after",
                    )
                ],
                commit_message="fix: stop storing token in local storage",
            )
        )

        result = await sample_pipeline._process_repo(sample_repo, dry_run=True, max_prs=1)

        assert result.contributions_generated == 1
        assert sample_pipeline._generator.generate.await_count == 1
        assert (
            sample_pipeline._generator.generate.await_args.kwargs["github_client"]
            is sample_pipeline._github
        )

    @pytest.mark.asyncio
    async def test_controlled_duplicate_mode_prefers_code_finding_over_untitled_docs(
        self,
        sample_pipeline,
        sample_repo,
        monkeypatch,
    ):
        docs_finding = Finding(
            id="docs-1",
            type=ContributionType.DOCS_IMPROVE,
            severity=Severity.MEDIUM,
            title="Untitled finding",
            description="Improve docs",
            file_path="",
            confidence=0.95,
        )
        ui_finding = Finding(
            id="ui-1",
            type=ContributionType.UI_UX_FIX,
            severity=Severity.MEDIUM,
            title="Clickable FolderNode/GroupNode",
            description="Improve node affordance",
            file_path="src/components/nodes/FolderNode.tsx",
            confidence=0.8,
        )

        sample_pipeline._github = AsyncMock()
        sample_pipeline._memory = AsyncMock()
        sample_pipeline._analyzer = AsyncMock()
        sample_pipeline._generator = AsyncMock()

        monkeypatch.setattr(
            "contribai.orchestrator.pipeline.fetch_repo_guidelines",
            AsyncMock(return_value=SimpleNamespace(has_guidelines=False)),
        )
        sample_pipeline._check_ai_policy = AsyncMock(return_value=False)
        sample_pipeline._memory.record_analysis = AsyncMock()
        sample_pipeline._memory.get_repo_prs = AsyncMock(return_value=[])
        sample_pipeline._github.get_file_tree = AsyncMock(return_value=[])
        sample_pipeline._github.get_file_content = AsyncMock(return_value="<div />")
        sample_pipeline._github.list_pull_requests = AsyncMock(return_value=[])
        sample_pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
        sample_pipeline._validate_findings = AsyncMock(return_value=[ui_finding])
        sample_pipeline._analyzer.analyze = AsyncMock(
            return_value=AnalysisResult(
                repo=sample_repo,
                findings=[docs_finding, ui_finding],
                analyzed_files=2,
                analysis_duration_sec=0.1,
            )
        )
        sample_pipeline._generator.generate = AsyncMock(return_value=None)

        await sample_pipeline._process_repo(
            sample_repo,
            dry_run=True,
            max_prs=1,
            allow_duplicate_prs=True,
        )

        validated_input = sample_pipeline._validate_findings.await_args.args[0]
        assert validated_input == [ui_finding]


class TestTitlesSimilar:
    def test_similar_titles(self):
        from contribai.orchestrator.pipeline import _titles_similar

        assert _titles_similar(
            "Fix null pointer in login handler",
            "Fix null pointer exception in login handler",
        )

    def test_different_titles(self):
        from contribai.orchestrator.pipeline import _titles_similar

        assert not _titles_similar(
            "Update README documentation",
            "Fix performance bottleneck in database",
        )

    def test_empty_titles(self):
        from contribai.orchestrator.pipeline import _titles_similar

        assert not _titles_similar("", "")

    def test_short_words_ignored(self):
        from contribai.orchestrator.pipeline import _titles_similar

        assert not _titles_similar("a the in", "b or on")
