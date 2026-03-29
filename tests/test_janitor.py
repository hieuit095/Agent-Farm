"""Tests for the PR Janitor."""

import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from farm_agent.pr.janitor import PRJanitor


class TestPRJanitor:
    """Tests for PRJanitor._classify_pr() and sweep_and_destroy()."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.complete = AsyncMock()
        return llm

    @pytest.fixture
    def mock_llm_config(self):
        from farm_agent.core.config import LLMConfig
        return LLMConfig(provider="minimax", model="some-model", api_key="test-key")

    @pytest.fixture
    def mock_github(self):
        gh = MagicMock()
        gh.fetch_user_open_prs = AsyncMock(return_value=[])
        gh.close_pull_request = AsyncMock()
        gh.delete_branch = AsyncMock()
        return gh

    @pytest.fixture
    def janitor(self, mock_github, mock_llm, mock_llm_config):
        return PRJanitor(mock_github, username="test-bot", llm_config=mock_llm_config, llm=mock_llm)

    @pytest.mark.asyncio
    async def test_classify_pr_returns_garbage_for_exploratory_title(self, janitor, mock_llm):
        """Title 'understand current config' must be classified as GARBAGE."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "GARBAGE", "reason": "Exploratory PR — wants to understand code."}'
        )
        verdict = await janitor._classify_pr(
            "feat: understand current config structure",
            "Let me look at the current implementation first.",
        )
        assert verdict["classification"] == "GARBAGE"

    @pytest.mark.asyncio
    async def test_classify_pr_returns_garbage_for_docs_pr(self, janitor, mock_llm):
        """Documentation PR must be classified as GARBAGE."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "GARBAGE", "reason": "Documentation-only change."}'
        )
        verdict = await janitor._classify_pr(
            "docs: update README installation steps",
            "Fixed typos and improved readability.",
        )
        assert verdict["classification"] == "GARBAGE"

    @pytest.mark.asyncio
    async def test_classify_pr_returns_garbage_for_typo_fix(self, janitor, mock_llm):
        """Typo-fix PR must be classified as GARBAGE."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "GARBAGE", "reason": "Typo fix is low-impact."}'
        )
        verdict = await janitor._classify_pr(
            "fix: typo in auth.py",
            "Changed 'enviroment' to 'environment'.",
        )
        assert verdict["classification"] == "GARBAGE"

    @pytest.mark.asyncio
    async def test_classify_pr_returns_critical_for_real_security_fix(self, janitor, mock_llm):
        """Real SQL injection fix must be classified as CRITICAL."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "CRITICAL", "reason": "Real SQL injection with concrete attack vector."}'
        )
        verdict = await janitor._classify_pr(
            "fix: SQL injection in auth login",
            "Sanitized user input before passing to raw SQL query.",
        )
        assert verdict["classification"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_classify_pr_returns_critical_for_logic_bug(self, janitor, mock_llm):
        """Real null pointer fix must be classified as CRITICAL."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "CRITICAL", "reason": "Null dereference will crash if user is None."}'
        )
        verdict = await janitor._classify_pr(
            "fix: null pointer in user profile handler",
            "Added null check before accessing user.email.",
        )
        assert verdict["classification"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_classify_pr_parses_json_with_markdown_fence(self, janitor, mock_llm):
        """LLM response wrapped in ```json fences must be parsed correctly."""
        mock_llm.complete = AsyncMock(
            return_value='```json\n{"classification": "GARBAGE", "reason": "Formatting change."}\n```'
        )
        verdict = await janitor._classify_pr("style: fix indentation", "")
        assert verdict["classification"] == "GARBAGE"

    @pytest.mark.asyncio
    async def test_classify_pr_falls_back_to_garbage_on_parse_error(self, janitor, mock_llm):
        """If LLM returns unparseable response, treat as GARBAGE."""
        mock_llm.complete = AsyncMock(return_value="APPROVE")
        verdict = await janitor._classify_pr("fix: some bug", "")
        assert verdict["classification"] == "GARBAGE"
        assert "parse error" in verdict["reason"].lower()

    @pytest.mark.asyncio
    async def test_sweep_closes_garbage_pr(self, janitor, mock_github, mock_llm):
        """GARBAGE PR must be closed and branch deleted."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "GARBAGE", "reason": "Exploratory PR."}'
        )
        mock_github.fetch_user_open_prs = AsyncMock(return_value=[
            {
                "repo": "owner/repo",
                "pr_number": 42,
                "title": "feat: understand the codebase",
                "body": "Let me explore this repo.",
                "html_url": "https://github.com/owner/repo/pull/42",
                "head_branch": "feat/understand",
                "state": "open",
            },
        ])

        summary = await janitor.sweep_and_destroy()

        assert summary["total_scanned"] == 1
        assert summary["garbage_closed"] == 1
        assert summary["critical_spared"] == 0
        mock_github.close_pull_request.assert_called_once_with(
            "owner",
            "repo",
            42,
            comment=ANY,
        )
        mock_github.delete_branch.assert_called_once_with("owner", "repo", "feat/understand")

    @pytest.mark.asyncio
    async def test_sweep_spares_critical_pr(self, janitor, mock_github, mock_llm):
        """CRITICAL PR must NOT be closed."""
        mock_llm.complete = AsyncMock(
            return_value='{"classification": "CRITICAL", "reason": "Real SQL injection vulnerability."}'
        )
        mock_github.fetch_user_open_prs = AsyncMock(return_value=[
            {
                "repo": "owner/repo",
                "pr_number": 99,
                "title": "fix: SQL injection in auth",
                "body": "Sanitized the raw SQL query.",
                "html_url": "https://github.com/owner/repo/pull/99",
                "head_branch": "fix/sql-injection",
                "state": "open",
            },
        ])

        summary = await janitor.sweep_and_destroy()

        assert summary["total_scanned"] == 1
        assert summary["garbage_closed"] == 0
        assert summary["critical_spared"] == 1
        mock_github.close_pull_request.assert_not_called()
        mock_github.delete_branch.assert_not_called()

    @pytest.mark.asyncio
    async def test_sweep_handles_mixed_prs(self, janitor, mock_github, mock_llm):
        """One GARBAGE, one CRITICAL — only the garbage one is closed."""
        call_count = [0]

        async def mock_complete(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return '{"classification": "GARBAGE", "reason": "Formatting."}'
            return '{"classification": "CRITICAL", "reason": "Real bug."}'

        mock_llm.complete = AsyncMock(side_effect=mock_complete)
        mock_github.fetch_user_open_prs = AsyncMock(return_value=[
            {
                "repo": "owner/repo",
                "pr_number": 1,
                "title": "style: whitespace fix",
                "body": "",
                "html_url": "https://github.com/owner/repo/pull/1",
                "head_branch": "style/whitespace",
                "state": "open",
            },
            {
                "repo": "owner/repo",
                "pr_number": 2,
                "title": "fix: memory leak in cache",
                "body": "Fixed leak by adding cleanup.",
                "html_url": "https://github.com/owner/repo/pull/2",
                "head_branch": "fix/memory-leak",
                "state": "open",
            },
        ])

        summary = await janitor.sweep_and_destroy()

        assert summary["total_scanned"] == 2
        assert summary["garbage_closed"] == 1
        assert summary["critical_spared"] == 1
        assert mock_github.close_pull_request.call_count == 1
        mock_github.close_pull_request.assert_called_with("owner", "repo", 1, comment=ANY)
        mock_github.delete_branch.assert_called_once_with("owner", "repo", "style/whitespace")

    @pytest.mark.asyncio
    async def test_sweep_no_open_prs(self, janitor, mock_github):
        """If no open PRs exist, do nothing."""
        mock_github.fetch_user_open_prs = AsyncMock(return_value=[])

        summary = await janitor.sweep_and_destroy()

        assert summary["total_scanned"] == 0
        assert summary["garbage_closed"] == 0
        assert summary["critical_spared"] == 0
        mock_github.close_pull_request.assert_not_called()
