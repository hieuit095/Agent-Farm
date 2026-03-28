"""Tests for the Style Mimicry feature.

Covers:
- GitHubClient.get_recent_merged_prs  (respx-mocked API)
- extract_style_guide  (pattern detection)
- build_repo_context_prompt  (style_guide injection)
"""

from __future__ import annotations

import httpx
import pytest
import respx

from farm_agent.core.models import RepoContext
from farm_agent.github.client import GITHUB_API, GitHubClient
from farm_agent.llm.context import build_repo_context_prompt, extract_style_guide


# ── Helpers ────────────────────────────────────────────────────────────────────


def _pr(title: str, body: str, merged: bool, user_type: str = "User") -> dict:
    """Build a minimal PR dict matching the GitHub API shape."""
    return {
        "title": title,
        "body": body,
        "merged_at": "2025-03-01T12:00:00Z" if merged else None,
        "user": {"login": "alice", "type": user_type},
    }


# ── extract_style_guide tests ─────────────────────────────────────────────────


class TestExtractStyleGuide:
    def test_empty_prs_returns_empty_string(self):
        assert extract_style_guide([]) == ""

    def test_emoji_titles_detected(self):
        prs = [
            {"title": "🐛 Fix login crash", "body": ""},
            {"title": "✨ Add dark mode", "body": ""},
            {"title": "🔧 Update config", "body": ""},
        ]
        guide = extract_style_guide(prs)
        assert "emoji" in guide.lower()

    def test_no_emoji_titles_detected(self):
        prs = [
            {"title": "Fix login crash", "body": ""},
            {"title": "Add dark mode", "body": ""},
            {"title": "Update config", "body": ""},
        ]
        guide = extract_style_guide(prs)
        assert "NOT use emojis" in guide

    def test_conventional_commits_detected(self):
        prs = [
            {"title": "feat: add dark mode", "body": ""},
            {"title": "fix: login crash", "body": ""},
            {"title": "docs: update readme", "body": ""},
        ]
        guide = extract_style_guide(prs)
        assert "Conventional Commits" in guide

    def test_bullet_points_and_issue_refs_detected(self):
        prs = [
            {"title": "Fix bug", "body": "- Fixed the thing\n- Also this\nCloses #42"},
            {"title": "Add feat", "body": "- New feature\nRef #10"},
            {"title": "Cleanup", "body": "- Removed dead code"},
        ]
        guide = extract_style_guide(prs)
        assert "bullet" in guide.lower()
        assert "#NNN" in guide

    def test_example_titles_included(self):
        prs = [
            {"title": "🐛 Fix login crash", "body": ""},
            {"title": "✨ Add dark mode", "body": ""},
        ]
        guide = extract_style_guide(prs)
        assert "Fix login crash" in guide
        assert "Add dark mode" in guide


# ── build_repo_context_prompt with style_guide ────────────────────────────────


class TestBuildRepoContextWithStyleGuide:
    def test_style_guide_injected(self, sample_repo):
        ctx = RepoContext(repo=sample_repo)
        guide = "OBSERVED REPO STYLE: - PR titles use emoji prefixes"
        prompt = build_repo_context_prompt(ctx, style_guide=guide)
        assert "emoji" in prompt
        assert "Observed PR Style" in prompt

    def test_no_style_guide_no_section(self, sample_repo):
        ctx = RepoContext(repo=sample_repo)
        prompt = build_repo_context_prompt(ctx)
        assert "Observed PR Style" not in prompt


# ── get_recent_merged_prs tests ───────────────────────────────────────────────


_PULLS_URL = f"{GITHUB_API}/repos/owner/repo/pulls"


class TestGetRecentMergedPRs:
    @respx.mock
    @pytest.mark.asyncio
    async def test_filters_bot_prs(self):
        """Bot PRs (user.type != 'User') are excluded."""
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    _pr("🤖 Bump deps", "", merged=True, user_type="Bot"),
                    _pr("Fix login", "", merged=True, user_type="User"),
                    _pr("Add tests", "", merged=True, user_type="User"),
                ],
            )
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo")
        await client.close()

        assert len(result) == 2
        assert all("Bot" not in pr.get("title", "") for pr in result)

    @respx.mock
    @pytest.mark.asyncio
    async def test_filters_unmerged_prs(self):
        """Closed-but-not-merged PRs are excluded."""
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    _pr("Merged PR", "", merged=True),
                    _pr("Closed PR", "", merged=False),
                ],
            )
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo")
        await client.close()

        assert len(result) == 1
        assert result[0]["title"] == "Merged PR"

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_repo_returns_empty(self):
        """Repo with no PRs returns an empty list."""
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(200, json=[])
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo")
        await client.close()

        assert result == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self):
        """API failures are caught gracefully."""
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo")
        await client.close()

        assert result == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_respects_limit(self):
        """Only returns up to `limit` PRs."""
        many_prs = [_pr(f"PR #{i}", "", merged=True) for i in range(20)]
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(200, json=many_prs)
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo", limit=3)
        await client.close()

        assert len(result) == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_body_truncated(self):
        """PR body is capped at 500 characters."""
        long_body = "x" * 2000
        respx.get(_PULLS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[_pr("Big PR", long_body, merged=True)],
            )
        )
        client = GitHubClient(token="test")
        result = await client.get_recent_merged_prs("owner", "repo")
        await client.close()

        assert len(result[0]["body"]) == 500
