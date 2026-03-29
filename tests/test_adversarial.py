"""Tests for the Adversarial Reviewer Agent and feedback loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.models import (
    Contribution,
    ContributionType,
    FileChange,
    Finding,
    RepoContext,
    Repository,
    Severity,
)
from farm_agent.generator.reviewer import ReviewerAgent
from farm_agent.generator.engine import ContributionGenerator


# ---------------------------------------------------------------------------
# FakeContribution – minimal Contribution used in reviewer unit tests
# ---------------------------------------------------------------------------


def _make_finding():
    return Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="User input not sanitized",
        file_path="auth.py",
    )


def _FakeContribution(
    decision="APPROVE",
    critique="",
):
    """Factory that returns a Contribution + pre-configured mock LLM."""
    fc = FileChange(
        path="auth.py",
        original_content="def login(u, p): return u + p",
        new_content="def login(u, p): return sanitize(u) + sanitize(p)",
    )
    finding = _make_finding()
    return Contribution(
        finding=finding,
        contribution_type=ContributionType.SECURITY_FIX,
        title="Fix SQL Injection",
        description="User input not sanitized",
        changes=[fc],
        commit_message="fix: sanitize",
        branch_name="fix/sql",
    )


# ---------------------------------------------------------------------------
# TestReviewerAgent – ReviewerAgent tested in isolation
# ---------------------------------------------------------------------------


class TestReviewerAgent:
    """Tests for ReviewerAgent.review() in complete isolation."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.complete = AsyncMock()
        return llm

    @pytest.fixture
    def reviewer(self, mock_llm):
        return ReviewerAgent(mock_llm)

    @pytest.fixture
    def fake_context(self):
        repo = Repository(
            owner="test",
            name="repo",
            full_name="test/repo",
            language="Python",
            stars=1000,
            description="A test repo",
            html_url="https://github.com/test/repo",
            clone_url="https://github.com/test/repo.git",
        )
        return RepoContext(
            repo=repo,
            relevant_files={"auth.py": "def login(u, p): return u + p"},
            file_tree=[],
        )

    @pytest.mark.asyncio
    async def test_reviewer_returns_approve_when_patch_is_clean(
        self, reviewer, mock_llm, fake_context
    ):
        """If the reviewer LLM returns APPROVE, the verdict should be APPROVE."""
        mock_llm.complete.return_value = '{"decision": "APPROVE", "critique": ""}'

        contrib = _FakeContribution()
        verdict = await reviewer.review(contrib, fake_context)

        assert verdict["decision"] == "APPROVE"
        assert verdict["critique"] == ""

    @pytest.mark.asyncio
    async def test_reviewer_returns_reject_with_critique(
        self, reviewer, mock_llm, fake_context
    ):
        """If the reviewer LLM returns REJECT, the verdict should contain the critique."""
        critique_text = (
            "Line 42: variable 'token' is referenced but never defined in scope. "
            "This will cause NameError at runtime."
        )
        mock_llm.complete.return_value = (
            f'{{"decision": "REJECT", "critique": "{critique_text}"}}'
        )

        contrib = _FakeContribution()
        verdict = await reviewer.review(contrib, fake_context)

        assert verdict["decision"] == "REJECT"
        assert critique_text in verdict["critique"]

    @pytest.mark.asyncio
    async def test_reviewer_parses_raw_json_with_markdown(
        self, reviewer, mock_llm, fake_context
    ):
        """The reviewer must handle ```json fences around the response."""
        mock_llm.complete = AsyncMock(
            return_value='```json\n{"decision": "APPROVE", "critique": ""}\n```'
        )

        contrib = Contribution(
            finding=_make_finding(),
            contribution_type=ContributionType.SECURITY_FIX,
            title="Fix SQL Injection",
            description="User input not sanitized",
            changes=[],
            commit_message="fix: sanitize",
            branch_name="fix/sql",
        )
        verdict = await reviewer.review(contrib, fake_context)

        assert verdict["decision"] == "APPROVE"

    @pytest.mark.asyncio
    async def test_reviewer_handles_trailing_comma_in_json(
        self, reviewer, mock_llm, fake_context
    ):
        """JSON with trailing commas must be parsed successfully."""
        mock_llm.complete = AsyncMock(
            return_value='{"decision": "REJECT", "critique": "Hallucinated variable",}'
        )

        contrib = Contribution(
            finding=_make_finding(),
            contribution_type=ContributionType.SECURITY_FIX,
            title="Fix SQL Injection",
            description="User input not sanitized",
            changes=[],
            commit_message="fix: sanitize",
            branch_name="fix/sql",
        )
        verdict = await reviewer.review(contrib, fake_context)

        assert verdict["decision"] == "REJECT"

    @pytest.mark.asyncio
    async def test_reviewer_falls_back_to_approve_on_parse_error(
        self, reviewer, mock_llm, fake_context
    ):
        """If JSON parsing fails, default to APPROVE (fail open)."""
        mock_llm.complete = AsyncMock(side_effect=Exception("API error"))

        contrib = _FakeContribution()
        verdict = await reviewer.review(contrib, fake_context)

        assert verdict["decision"] == "APPROVE"
        assert verdict["critique"] == ""

    @pytest.mark.asyncio
    async def test_reviewer_builds_prompt_with_finding_details(
        self, reviewer, mock_llm, fake_context
    ):
        """The review prompt must include the finding description and changed files."""
        mock_llm.complete.return_value = '{"decision": "APPROVE", "critique": ""}'

        contrib = _FakeContribution()
        await reviewer.review(contrib, fake_context)

        assert mock_llm.complete.called
        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0]

        assert "SQL Injection" in prompt or "SQL" in prompt
        assert "auth.py" in prompt

    @pytest.mark.asyncio
    async def test_reviewer_system_prompt_is_adversarial(
        self, reviewer, mock_llm, fake_context
    ):
        """The reviewer must use a SEPARATE adversarial (paranoid) system prompt."""
        mock_llm.complete.return_value = '{"decision": "APPROVE", "critique": ""}'

        contrib = _FakeContribution()
        await reviewer.review(contrib, fake_context)

        assert mock_llm.complete.called
        call_args = mock_llm.complete.call_args
        system = call_args.kwargs.get("system") or (call_args[0][1] if len(call_args[0]) > 1 else "")

        assert "ADVERSARIAL" in system.upper() or "security" in system.lower()


# ---------------------------------------------------------------------------
# TestAdversarialLoopIntegration – full generate() + review loop
# ---------------------------------------------------------------------------


class TestAdversarialLoopIntegration:
    """Tests for the complete generate() → adversarial review loop."""

    @pytest.fixture
    def real_contribution_with_changes(self):
        fc = FileChange(
            path="auth.py",
            original_content="def login(u, p): return u + p",
            new_content="def login(u, p): return sanitize(u) + sanitize(p)",
        )
        finding = Finding(
            type=ContributionType.SECURITY_FIX,
            severity=Severity.HIGH,
            title="SQL Injection",
            description="User input not sanitized",
            file_path="auth.py",
        )
        return Contribution(
            finding=finding,
            contribution_type=ContributionType.SECURITY_FIX,
            title="Fix SQL Injection",
            description="User input not sanitized",
            changes=[fc],
            commit_message="fix: sanitize login inputs",
            branch_name="fix/sql-injection",
        )

    @pytest.fixture
    def populated_context(self):
        repo = Repository(
            owner="test",
            name="repo",
            full_name="test/repo",
            language="Python",
            stars=1000,
            description="Test repo",
            html_url="https://github.com/test/repo",
            clone_url="https://github.com/test/repo.git",
        )
        ctx = RepoContext(repo=repo, relevant_files={}, file_tree=[])
        ctx.relevant_files["auth.py"] = "def login(u, p): return u + p"
        ctx._tree = [(["src"], ["auth.py"])]
        return ctx

    @pytest.fixture
    def mock_gh_populated(self):
        gh = MagicMock()
        gh.get_dir_content = AsyncMock(return_value=(["src"], ["auth.py"]))
        gh.get_file_content = AsyncMock(
            return_value="def login(u, p): return u + p"
        )
        return gh

    def _make_mock_response(self, text):
        """Return an awaitable MagicMock with the tool-call interface."""
        m = MagicMock()
        m.has_tool_calls = False
        m.text = text
        m.tool_calls = []
        return m

    @pytest.mark.asyncio
    async def test_generator_retries_on_reject_then_approve(
        self,
        real_contribution_with_changes,
        populated_context,
        mock_gh_populated,
    ):
        """Generator must call LLM TWICE when reviewer REJECTs first then APPROVEs second."""
        from farm_agent.core.config import ContributionConfig

        mock_llm = MagicMock()
        call_count = [0]

        async def complete_with_tools_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: patch identical to original (will be REJECTed)
                text = (
                    '{"changes":[{"path":"auth.py","is_new_file":false,'
                    '"edits":[{"search":"def login(u, p): return u + p",'
                    '"replace":"def login(u, p): return u + p"}]}]}'
                )
            else:
                # Second call (after critique): fixed patch
                text = (
                    '{"changes":[{"path":"auth.py","is_new_file":false,'
                    '"edits":[{"search":"def login(u, p): return u + p",'
                    '"replace":"def login(u, p): return sanitize(u) + sanitize(p)"}]}]}'
                )
            return self._make_mock_response(text)

        mock_llm.complete_with_tools = AsyncMock(side_effect=complete_with_tools_side_effect)

        config = ContributionConfig(max_review_retries=2)
        gen = ContributionGenerator(mock_llm, config)

        review_count = [0]

        async def mock_review(contribution, context):
            review_count[0] += 1
            if review_count[0] == 1:
                return {
                    "decision": "REJECT",
                    "critique": "Patch is identical to original — no fix applied!",
                }
            return {"decision": "APPROVE", "critique": ""}

        gen._reviewer.review = AsyncMock(side_effect=mock_review)

        finding = real_contribution_with_changes.finding
        result = await gen.generate(
            finding=finding,
            context=populated_context,
            github_client=mock_gh_populated,
        )

        # Reviewer called TWICE (REJECT + APPROVE)
        assert review_count[0] == 2, f"Expected 2 review calls, got {review_count[0]}"

        # LLM called TWICE (original + rewrite with critique)
        assert call_count[0] == 2, f"Expected 2 LLM calls, got {call_count[0]}"

        # Second call prompt must include critique
        second_call_args = mock_llm.complete_with_tools.call_args_list[1]
        messages = second_call_args[0][0]
        # messages is a list of dicts; join all content to search
        all_content = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
        assert (
            "ADVERSARIAL REVIEWER CRITIQUE" in all_content
            or "Patch is identical" in all_content
        ), f"Second LLM call must include the reviewer's critique. Got: {all_content[:200]}"

        assert result is not None

    @pytest.mark.asyncio
    async def test_generator_discards_finding_after_max_retries(
        self,
        real_contribution_with_changes,
        populated_context,
        mock_gh_populated,
    ):
        """If all review retries fail, Generator must return None (discard finding)."""
        from farm_agent.core.config import ContributionConfig

        mock_llm = MagicMock()
        mock_llm.complete_with_tools = AsyncMock(
            return_value=self._make_mock_response(
                '{"changes":[{"path":"auth.py","is_new_file":false,'
                '"edits":[{"search":"def login(u, p): return u + p",'
                '"replace":"def login(u, p): return sanitize(u) + sanitize(p)"}]}]}'
            )
        )

        config = ContributionConfig(max_review_retries=2)
        gen = ContributionGenerator(mock_llm, config)

        # Mock reviewer: always REJECT
        gen._reviewer.review = AsyncMock(
            return_value={"decision": "REJECT", "critique": "Patch is still wrong"}
        )

        finding = real_contribution_with_changes.finding
        result = await gen.generate(
            finding=finding,
            context=populated_context,
            github_client=mock_gh_populated,
        )

        # 1 original + 2 retries = 3 review calls
        assert gen._reviewer.review.call_count == 3, (
            f"Expected 3 review calls (1 original + 2 retries), "
            f"got {gen._reviewer.review.call_count}"
        )

        assert result is None  # Finding was discarded

    @pytest.mark.asyncio
    async def test_approved_on_first_review_no_extra_llm_calls(
        self,
        real_contribution_with_changes,
        populated_context,
        mock_gh_populated,
    ):
        """If reviewer APPROVEs on first try, LLM is called exactly once."""
        from farm_agent.core.config import ContributionConfig

        mock_llm = MagicMock()
        call_count = [0]

        async def complete_with_tools_side_effect(*args, **kwargs):
            call_count[0] += 1
            text = (
                '{"changes":[{"path":"auth.py","is_new_file":false,'
                '"edits":[{"search":"def login(u, p): return u + p",'
                '"replace":"def login(u, p): return sanitize(u) + sanitize(p)"}]}]}'
            )
            return self._make_mock_response(text)

        mock_llm.complete_with_tools = AsyncMock(side_effect=complete_with_tools_side_effect)

        config = ContributionConfig(max_review_retries=2)
        gen = ContributionGenerator(mock_llm, config)

        # Mock reviewer: APPROVE immediately
        gen._reviewer.review = AsyncMock(
            return_value={"decision": "APPROVE", "critique": ""}
        )

        finding = real_contribution_with_changes.finding
        result = await gen.generate(
            finding=finding,
            context=populated_context,
            github_client=mock_gh_populated,
        )

        # LLM called exactly once (no rewrite needed)
        assert call_count[0] == 1, f"Expected 1 LLM call, got {call_count[0]}"

        # Reviewer called exactly once
        assert (
            gen._reviewer.review.call_count == 1
        ), f"Expected 1 review call, got {gen._reviewer.review.call_count}"

        assert result is not None
