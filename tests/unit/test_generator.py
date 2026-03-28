"""Tests for the contribution generator."""

from unittest.mock import AsyncMock

import pytest

from farm_agent.core.config import ContributionConfig
from farm_agent.core.models import (
    Contribution,
    ContributionType,
    FileChange,
    Finding,
    RepoContext,
    Severity,
)
from farm_agent.generator.engine import ContributionGenerator


@pytest.fixture
def generator(mock_llm):
    config = ContributionConfig(max_files_per_pr=5)
    return ContributionGenerator(llm=mock_llm, config=config)


@pytest.fixture
def security_finding():
    return Finding(
        id="sec001",
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="Hardcoded API key",
        description="API key is hardcoded in source",
        file_path="src/config.py",
        line_start=42,
        suggestion="Use environment variables",
    )


@pytest.fixture
def context(sample_repo):
    return RepoContext(
        repo=sample_repo,
        relevant_files={"src/config.py": "API_KEY = 'sk-1234'\n"},
    )


class TestGenerateBranchName:
    def test_security_fix_branch(self, generator, security_finding):
        name = generator._generate_branch_name(security_finding)
        assert name.startswith("farm_agent/fix/security/")
        assert "hardcoded" in name

    def test_docs_branch(self, generator):
        finding = Finding(
            type=ContributionType.README_FIX,
            severity=Severity.LOW,
            title="Missing README section",
            description="",
            file_path="README.md",
        )
        name = generator._generate_branch_name(finding)
        assert name.startswith("farm_agent/docs/")

    def test_branch_name_sanitized(self, generator):
        finding = Finding(
            type=ContributionType.FEATURE_ADD,
            severity=Severity.MEDIUM,
            title="Add feature: special chars! @#$ here",
            description="",
            file_path="x.py",
        )
        name = generator._generate_branch_name(finding)
        assert "@" not in name
        assert "!" not in name
        assert "$" not in name


class TestGeneratePRTitle:
    def test_security_title(self, generator, security_finding):
        title = generator._generate_pr_title(security_finding)
        assert "🔒" in title
        assert "Hardcoded API key" in title

    def test_docs_title(self, generator):
        finding = Finding(
            type=ContributionType.README_FIX,
            severity=Severity.LOW,
            title="Add API docs",
            description="",
            file_path="docs/api.md",
        )
        title = generator._generate_pr_title(finding)
        assert "📝" in title


class TestParseChanges:
    @pytest.fixture
    def mock_context(self, sample_repo):
        return RepoContext(
            repo=sample_repo,
            relevant_files={"src/config.py": "API_KEY = 'sk-1234'\n"},
        )

    def test_parse_json_response(self, generator, mock_context):
        response = """Here is the fix:
```json
{
  "changes": [
    {
      "path": "src/config.py",
      "content": "import os\\nAPI_KEY = os.getenv('API_KEY')",
      "is_new_file": false
    }
  ]
}
```"""
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 1
        assert changes[0].path == "src/config.py"
        assert not changes[0].is_new_file

    def test_parse_new_file(self, generator, mock_context):
        response = """```json
{"changes": [{"path": "new_file.py", "content": "print('hello')", "is_new_file": true}]}
```"""
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 1
        assert changes[0].is_new_file is True

    def test_parse_invalid_json(self, generator, mock_context):
        response = "This is not JSON at all"
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 0

    def test_enforces_max_files(self, generator, mock_context):
        many_changes = [
            {"path": f"file{i}.py", "content": "x", "is_new_file": True} for i in range(20)
        ]
        response = f'{{"changes": {many_changes}}}'.replace("'", '"')
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) <= generator._config.max_files_per_pr

    def test_parse_search_replace(self, generator, mock_context):
        """Test search/replace mode preserves original content."""
        response = """```json
{
  "changes": [
    {
      "path": "src/config.py",
      "is_new_file": false,
      "edits": [
        {
          "search": "API_KEY = 'sk-1234'",
          "replace": "API_KEY = os.getenv('API_KEY', '')"
        }
      ]
    }
  ]
}
```"""
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 1
        assert "os.getenv" in changes[0].new_content
        assert not changes[0].is_new_file


class TestSelfReview:
    @pytest.mark.asyncio
    async def test_approve(self, generator, security_finding, context):
        generator._llm.complete = AsyncMock(return_value="APPROVE - looks good")
        contribution = Contribution(
            finding=security_finding,
            contribution_type=ContributionType.SECURITY_FIX,
            title="Fix security issue",
            description="Fixed it",
            changes=[FileChange(path="x.py", new_content="safe code")],
        )
        assert await generator._self_review(contribution, context) is True

    @pytest.mark.asyncio
    async def test_reject(self, generator, security_finding, context):
        generator._llm.complete = AsyncMock(return_value="REJECT - introduces new bug")
        contribution = Contribution(
            finding=security_finding,
            contribution_type=ContributionType.SECURITY_FIX,
            title="Bad fix",
            description="Bad",
            changes=[FileChange(path="x.py", new_content="buggy code")],
        )
        assert await generator._self_review(contribution, context) is False

    @pytest.mark.asyncio
    async def test_llm_failure_approves_by_default(self, generator, security_finding, context):
        generator._llm.complete = AsyncMock(side_effect=Exception("LLM down"))
        contribution = Contribution(
            finding=security_finding,
            contribution_type=ContributionType.SECURITY_FIX,
            title="Fix",
            description="",
            changes=[FileChange(path="x.py", new_content="code")],
        )
        # Should approve by default when LLM fails
        assert await generator._self_review(contribution, context) is True

    @pytest.mark.asyncio
    async def test_unrecognized_verdict_approves_by_default(self, generator, security_finding, context):
        generator._llm.complete = AsyncMock(return_value="REVIEW - partially correct, inspect manually")
        contribution = Contribution(
            finding=security_finding,
            contribution_type=ContributionType.SECURITY_FIX,
            title="Needs review",
            description="",
            changes=[FileChange(path="x.py", new_content="code")],
        )
        assert await generator._self_review(contribution, context) is True


# ── Test Architectural Awareness ──────────────────────────────────────────


MOCK_PROJECT_MAP = """\
src/utils/date_helpers.py
  class DateParser:
    def parse_date_custom_v3(self, date_str: str, fmt: str) -> datetime
    def format_iso(self, dt: datetime) -> str

src/models/user.py
  class User(BaseModel):
    def validate_email(self, email: str) -> bool

src/db/connection.py
  async def get_db_pool(dsn: str) -> Pool
"""


class TestArchitecturalAwareness:
    """Test that the Generator's system prompt enforces architectural awareness."""

    def test_system_prompt_includes_project_map_and_rules(self, generator, context):
        """When a project map is provided, the system prompt must contain
        the map data AND all three architectural awareness rules."""
        system = generator._build_system_prompt(
            context, project_map=MOCK_PROJECT_MAP,
        )

        # Map data is present
        assert "parse_date_custom_v3" in system
        assert "DateParser" in system
        assert "get_db_pool" in system

        # All 3 rules are present
        assert "RULE 1" in system
        assert "CROSS-REFERENCE" in system
        assert "RULE 2" in system
        assert "SIGNATURE MATCHING" in system
        assert "RULE 3" in system
        assert "MISSING CONTEXT" in system

        # Header present
        assert "PROJECT SKELETON MAP" in system

    def test_system_prompt_unique_utility_is_discoverable(self, generator, context):
        """The LLM should be able to discover `parse_date_custom_v3` from the
        map. Verify the *exact* signature is in the prompt so the LLM can
        cross-reference it rather than inventing a generic `parse_date`."""
        system = generator._build_system_prompt(
            context, project_map=MOCK_PROJECT_MAP,
        )

        # The EXACT unique function name must be present
        assert "parse_date_custom_v3" in system
        # The full signature including args must be visible
        assert "date_str: str" in system
        assert "fmt: str" in system

    def test_system_prompt_without_map_has_no_map_section(self, generator, context):
        """When no project map is provided, the prompt should NOT contain
        the skeleton map section or rules (backward compatibility)."""
        system = generator._build_system_prompt(context, project_map="")

        assert "PROJECT SKELETON MAP" not in system
        assert "CROSS-REFERENCE" not in system
        assert "SIGNATURE MATCHING" not in system

        # But standard rules should still be present
        assert "RULES FOR GENERATING CHANGES" in system
        assert "MAINTAINER ACCEPTANCE CRITERIA" in system

    def test_system_prompt_truncation_notice_for_large_map(self, generator, context):
        """When the project map exceeds 60K chars, the truncation notice
        must appear in the prompt."""
        huge_map = "x" * 70_000
        system = generator._build_system_prompt(context, project_map=huge_map)

        assert "The Project Map may be truncated" in system
        assert "Rely on the provided context first" in system

    @pytest.mark.asyncio
    async def test_generate_uses_project_map_from_github(self):
        """Full integration: generate() fetches the project map and passes
        it to the system prompt. Verify the LLM receives the map content."""
        from unittest.mock import MagicMock

        from farm_agent.core.models import FileNode, Repository
        from farm_agent.llm.provider import LLMToolResponse

        mock_llm = MagicMock()
        received_system = {}
        call_count = {"n": 0}

        async def capture_complete_with_tools(messages, *, system="", temperature=0.2, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Generation call — capture the system prompt
                received_system["value"] = system
                return LLMToolResponse(
                    text='```json\n'
                    '{"changes": [{"path": "src/fix.py", "content": '
                    '"from src.utils.date_helpers import DateParser\\n'
                    'parser = DateParser()\\n'
                    'result = parser.parse_date_custom_v3(raw, \\"%Y-%m-%d\\")\\n", '
                    '"is_new_file": true}]}\n'
                    '```'
                )
            # Self-review call (though not reached via complete_with_tools anymore, but complete)
            pass

        async def capture_complete(*args, **kwargs):
            return "APPROVE - looks good"

        mock_llm.complete_with_tools = AsyncMock(side_effect=capture_complete_with_tools)
        mock_llm.complete = AsyncMock(side_effect=capture_complete)

        config = ContributionConfig(max_files_per_pr=5)
        gen = ContributionGenerator(llm=mock_llm, config=config)

        # Build a context with file tree nodes so RepoMapper has files to scan
        repo = Repository(
            owner="test", name="repo", full_name="test/repo",
            description="test", language="Python", stars=10,
        )
        ctx = RepoContext(
            repo=repo,
            file_tree=[
                FileNode(path="src/utils/date_helpers.py", type="blob"),
                FileNode(path="src/fix.py", type="blob"),
                FileNode(path="README.md", type="blob"),
            ],
        )

        # Mock github_client
        github_client = MagicMock()
        github_client.get_recent_merged_prs = AsyncMock(return_value=[])
        github_client.get_file_content = AsyncMock(
            return_value=(
                "class DateParser:\n"
                "    def parse_date_custom_v3(self, date_str: str, fmt: str):\n"
                "        pass\n"
            )
        )

        finding = Finding(
            id="date-bug",
            type=ContributionType.CODE_QUALITY,
            severity=Severity.MEDIUM,
            title="Fix date parsing bug",
            description="Date parsing fails for ISO format",
            file_path="src/fix.py",
        )

        result = await gen.generate(
            finding, ctx, github_client=github_client,
        )

        # The system prompt the LLM received must contain the map data
        system = received_system.get("value", "")
        assert "parse_date_custom_v3" in system
        assert "CROSS-REFERENCE" in system
        assert ctx.relevant_files["src/utils/date_helpers.py"].startswith("class DateParser")


class TestAgenticLoop:
    @pytest.mark.asyncio
    async def test_agentic_loop_read_file_success(self, context):
        """Verify the agentic loop calls read_file and then returns generation."""
        from unittest.mock import AsyncMock, MagicMock
        from farm_agent.llm.provider import LLMToolResponse, ToolCallRequest

        mock_llm = MagicMock()
        call_count = {"tools": 0, "complete": 0}

        async def mock_complete_with_tools(*args, **kwargs):
            call_count["tools"] += 1
            if call_count["tools"] == 1:
                return LLMToolResponse(
                    tool_calls=[ToolCallRequest(tool_name="read_file", arguments={"filepath": "src/utils.py"})]
                )
            
            return LLMToolResponse(
                text='```json\n{"changes": [{"path": "src/fix.py", "content": "def helper(): pass\\n", "is_new_file": true}]}\n```'
            )

        async def mock_complete(*args, **kwargs):
            call_count["complete"] += 1
            return "APPROVE - looks good"

        mock_llm.complete_with_tools = AsyncMock(side_effect=mock_complete_with_tools)
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        github_client = MagicMock()
        github_client.get_recent_merged_prs = AsyncMock(return_value=[])
        github_client.get_file_content = AsyncMock(return_value="def helper(): pass")

        config = ContributionConfig(max_files_per_pr=5)
        gen = ContributionGenerator(llm=mock_llm, config=config)

        finding = Finding(
            id="test-bug",
            type=ContributionType.CODE_QUALITY,
            severity=Severity.MEDIUM,
            title="Test bug",
            description="Fix the bug",
            file_path="src/fix.py"
        )

        result = await gen.generate(finding, context, github_client=github_client)

        assert call_count["tools"] == 2
        assert call_count["complete"] == 1  # Self review
        
        # Verify read_file was called on github client via the tool
        github_client.get_file_content.assert_any_call(context.repo.owner, context.repo.name, "src/utils.py")
        assert context.relevant_files["src/utils.py"] == "def helper(): pass"

        assert result is not None
        assert len(result.changes) == 1
        assert "def helper(): pass" in result.changes[0].new_content

    @pytest.mark.asyncio
    async def test_agentic_loop_max_calls_limit(self, context):
        """Verify the loop doesn't exceed MAX_TOOL_CALLS."""
        from unittest.mock import AsyncMock, MagicMock
        from farm_agent.llm.provider import LLMToolResponse, ToolCallRequest
        from farm_agent.generator.engine import MAX_TOOL_CALLS

        mock_llm = MagicMock()
        call_count = {"tools": 0, "complete": 0}

        async def mock_complete_with_tools(messages, tools=None, **kwargs):
            call_count["tools"] += 1
            # If tools are not None, return a tool call. If they are None (limit reached), return text.
            if tools is not None:
                return LLMToolResponse(
                    tool_calls=[ToolCallRequest(tool_name="read_file", arguments={"filepath": "src/utils.py"})]
                )
            return LLMToolResponse(
                text='```json\n{"changes": [{"path": "src/fix.py", "content": "print()\\n", "is_new_file": true}]}\n```'
            )

        async def mock_complete(*args, **kwargs):
            call_count["complete"] += 1
            return "APPROVE"

        mock_llm.complete_with_tools = AsyncMock(side_effect=mock_complete_with_tools)
        mock_llm.complete = AsyncMock(side_effect=mock_complete)

        github_client = MagicMock()
        github_client.get_recent_merged_prs = AsyncMock(return_value=[])
        github_client.get_file_content = AsyncMock(return_value="def helper(): pass")

        config = ContributionConfig(max_files_per_pr=5)
        gen = ContributionGenerator(llm=mock_llm, config=config)

        finding = Finding(
            id="test-bug-2",
            type=ContributionType.CODE_QUALITY,
            severity=Severity.MEDIUM,
            title="Test bug 2",
            description="Fix the bug 2",
            file_path="src/fix.py"
        )

        result = await gen.generate(finding, context, github_client=github_client)

        # tools should be called MAX_TOOL_CALLS times returning tool calls, 
        # plus 1 time with tools=None returning text
        assert call_count["tools"] == MAX_TOOL_CALLS + 1
        assert call_count["complete"] == 1  # Self review only

        assert result is not None
        assert result.changes[0].new_content == "print()\n"


class TestDiffMinimizer:
    """Test that bloated replace blocks are rejected by _parse_changes."""

    @pytest.fixture
    def mock_context(self, sample_repo):
        original = "line1\nline2\nline3\nline4\nline5\n"
        return RepoContext(
            repo=sample_repo,
            relevant_files={"src/app.py": original},
        )

    def test_rejects_bloated_replace(self, generator, mock_context):
        """A 2-line search with a 40-line replace must be rejected."""
        bloated_replace = "\\n".join(f"new_line_{i}" for i in range(40))
        response = (
            '```json\n'
            '{"changes": [{"path": "src/app.py", "is_new_file": false, '
            '"edits": [{"search": "line1\\nline2", '
            f'"replace": "{bloated_replace}"'
            '}]}]}\n```'
        )
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 0

    def test_allows_proportional_replace(self, generator, mock_context):
        """A 3-line search with a 5-line replace should pass."""
        response = (
            '```json\n'
            '{"changes": [{"path": "src/app.py", "is_new_file": false, '
            '"edits": [{"search": "line1\\nline2\\nline3", '
            '"replace": "new1\\nnew2\\nnew3\\nnew4\\nnew5"'
            '}]}]}\n```'
        )
        changes = generator._parse_changes(response, mock_context)
        assert len(changes) == 1
        assert "new1" in changes[0].new_content


