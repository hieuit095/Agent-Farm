"""Unit tests for PR Patrol engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from contribai.core.models import FeedbackAction, FeedbackItem, PatrolResult
from contribai.pr.patrol import (
    CONTROLLED_TEST_MARKER,
    GITHUB_REPLIES,
    OUR_REPLY_MARKERS,
    REVIEW_BOT_LOGINS,
    PRPatrol,
)

# ── Test constants ─────────────────────────────────────────────────────────


class TestReviewBotLogins:
    """Test REVIEW_BOT_LOGINS constant."""

    def test_contains_coderabbitai(self):
        assert "coderabbitai" in REVIEW_BOT_LOGINS

    def test_contains_copilot(self):
        assert "copilot" in REVIEW_BOT_LOGINS

    def test_contains_dependabot(self):
        assert "dependabot" in REVIEW_BOT_LOGINS

    def test_contains_codecov(self):
        assert "codecov" in REVIEW_BOT_LOGINS


class TestOurReplyMarkers:
    """Test OUR_REPLY_MARKERS constant."""

    def test_contains_contribai(self):
        assert any("contribai" in m for m in OUR_REPLY_MARKERS)

    def test_contains_patrol_marker(self):
        assert any("contribai-patrol" in m for m in OUR_REPLY_MARKERS)


# ── Test PatrolResult ──────────────────────────────────────────────────────


class TestPatrolResult:
    """Test PatrolResult model."""

    def test_defaults(self):
        result = PatrolResult()
        assert result.prs_checked == 0
        assert result.fixes_pushed == 0
        assert result.replies_sent == 0
        assert result.cla_signed == 0
        assert result.prs_skipped == 0
        assert result.issues_found == 0
        assert result.assigned_issues == []
        assert result.errors == []

    def test_increment(self):
        result = PatrolResult()
        result.prs_checked += 1
        result.fixes_pushed += 2
        assert result.prs_checked == 1
        assert result.fixes_pushed == 2

    def test_assigned_issues(self):
        result = PatrolResult()
        result.assigned_issues.append({"repo": "test/repo", "number": 1})
        result.issues_found += 1
        assert result.issues_found == 1
        assert len(result.assigned_issues) == 1


# ── Test FeedbackItem ──────────────────────────────────────────────────────


class TestFeedbackItem:
    """Test FeedbackItem model."""

    def test_basic(self):
        item = FeedbackItem(
            comment_id=123,
            author="user1",
            body="Fix this",
            action=FeedbackAction.CODE_CHANGE,
        )
        assert item.comment_id == 123
        assert item.author == "user1"
        assert item.action == FeedbackAction.CODE_CHANGE
        assert item.is_inline is False
        assert item.bot_context is None

    def test_inline_with_bot_context(self):
        item = FeedbackItem(
            comment_id=456,
            author="maintainer",
            body="Please fix",
            action=FeedbackAction.CODE_CHANGE,
            file_path="server.py",
            line=26,
            is_inline=True,
            bot_context="[Bot review] Unused import detected",
        )
        assert item.is_inline is True
        assert item.bot_context == "[Bot review] Unused import detected"
        assert item.file_path == "server.py"
        assert item.line == 26


# ── Test FeedbackAction ────────────────────────────────────────────────────


class TestFeedbackAction:
    """Test FeedbackAction enum."""

    def test_values(self):
        assert FeedbackAction.CODE_CHANGE == "code_change"
        assert FeedbackAction.QUESTION == "question"
        assert FeedbackAction.STYLE_FIX == "style_fix"
        assert FeedbackAction.APPROVE == "approve"
        assert FeedbackAction.REJECT == "reject"
        assert FeedbackAction.ALREADY_HANDLED == "already_handled"

    def test_lookup(self):
        action_map = {a.value: a for a in FeedbackAction}
        assert action_map["code_change"] == FeedbackAction.CODE_CHANGE


# ── Test PRPatrol ──────────────────────────────────────────────────────────


class TestPRPatrolInit:
    """Test PRPatrol initialization."""

    def test_init(self):
        github = MagicMock()
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        assert patrol._github is github
        assert patrol._llm is llm
        assert patrol._user is None

    @pytest.mark.asyncio
    async def test_get_user(self):
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "tang-vu"})
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        user = await patrol._get_user()
        assert user["login"] == "tang-vu"
        # Second call should use cache
        user2 = await patrol._get_user()
        assert user2["login"] == "tang-vu"
        github.get_authenticated_user.assert_called_once()


class TestCollectFeedback:
    """Test _collect_feedback method."""

    @pytest.mark.asyncio
    async def test_filters_own_comments(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(
            return_value=[
                {"id": 1, "user": {"login": "tang-vu", "type": "User"}, "body": "test"},
            ]
        )
        github.get_pr_review_comments = AsyncMock(return_value=[])
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_filters_bot_comments(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(
            return_value=[
                {"id": 1, "user": {"login": "netlify[bot]", "type": "Bot"}, "body": "deploy"},
            ]
        )
        github.get_pr_review_comments = AsyncMock(return_value=[])
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_filters_review_bot_logins(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(
            return_value=[
                {"id": 1, "user": {"login": "coderabbitai[bot]", "type": "Bot"}, "body": "review"},
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_keeps_human_comments(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(
            return_value=[
                {"id": 1, "user": {"login": "maintainer", "type": "User"}, "body": "LGTM"},
            ]
        )
        github.get_pr_review_comments = AsyncMock(return_value=[])
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 1
        assert result[0]["author"] == "maintainer"

    @pytest.mark.asyncio
    async def test_keeps_controlled_test_comment_from_our_own_login(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "user": {"login": "tang-vu", "type": "User"},
                    "body": f"{CONTROLLED_TEST_MARKER} Please rename this variable.",
                    "path": "server.py",
                    "line": 12,
                    "original_line": 12,
                    "diff_hunk": "@@ -10,3 +10,4 @@",
                    "created_at": "2026-03-26T10:00:00Z",
                },
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 1
        assert result[0]["author"] == "tang-vu"
        assert result[0]["file_path"] == "server.py"

    @pytest.mark.asyncio
    async def test_skips_review_comment_thread_after_our_reply(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(
            return_value=[
                {
                    "id": 10,
                    "user": {"login": "tang-vu", "type": "User"},
                    "body": f"{CONTROLLED_TEST_MARKER} Please rename this variable.",
                    "path": "server.py",
                    "line": 12,
                    "original_line": 12,
                    "diff_hunk": "@@ -10,3 +10,4 @@",
                    "created_at": "2026-03-26T10:00:00Z",
                },
                {
                    "id": 11,
                    "user": {"login": "tang-vu", "type": "User"},
                    "body": "Updated in the latest commit. Thanks for pointing it out!\n\n<!-- contribai-patrol -->",
                    "path": "server.py",
                    "line": 12,
                    "original_line": 12,
                    "diff_hunk": "@@ -10,3 +10,4 @@",
                    "in_reply_to_id": 10,
                    "created_at": "2026-03-26T10:01:00Z",
                },
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert result == []

    @pytest.mark.asyncio
    async def test_bot_context_linked(self):
        """When human replies to bot review, bot_context is attached."""
        github = MagicMock()
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(
            return_value=[
                {
                    "id": 100,
                    "user": {"login": "coderabbitai[bot]", "type": "Bot"},
                    "body": "Unused import detected: start_http_server",
                    "path": "server.py",
                    "line": 26,
                    "original_line": 26,
                    "diff_hunk": "@@ -23,6 +23,7 @@",
                    "in_reply_to_id": None,
                    "created_at": "2026-03-20",
                },
                {
                    "id": 200,
                    "user": {"login": "moshemorad", "type": "User"},
                    "body": "Hi can you please take a look?",
                    "path": "server.py",
                    "line": 26,
                    "original_line": 26,
                    "diff_hunk": "@@ -23,6 +23,7 @@",
                    "in_reply_to_id": 100,
                    "created_at": "2026-03-23",
                },
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1816, "tang-vu")
        assert len(result) == 1
        assert result[0]["author"] == "moshemorad"
        assert result[0]["bot_context"] is not None
        assert "Unused import" in result[0]["bot_context"]
        assert "coderabbitai" in result[0]["bot_context"]

    @pytest.mark.asyncio
    async def test_no_bot_context_when_no_reply(self):
        github = MagicMock()
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(
            return_value=[
                {
                    "id": 300,
                    "user": {"login": "reviewer", "type": "User"},
                    "body": "This needs fixing",
                    "path": "main.py",
                    "line": 10,
                    "original_line": 10,
                    "diff_hunk": "@@ some diff",
                    "in_reply_to_id": None,
                    "created_at": "2026-03-23",
                },
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol._collect_feedback("owner", "repo", 1, "tang-vu")
        assert len(result) == 1
        assert result[0]["bot_context"] is None


class TestBuildFixPrompt:
    """Test _build_fix_prompt method."""

    def test_basic_prompt(self):
        github = MagicMock()
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        item = FeedbackItem(
            comment_id=1,
            author="reviewer",
            body="Fix the typo",
            action=FeedbackAction.CODE_CHANGE,
        )
        prompt = patrol._build_fix_prompt(item, "file content", "main.py", "")
        assert "Fix the typo" in prompt
        assert "main.py" in prompt

    def test_prompt_includes_bot_context(self):
        github = MagicMock()
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        item = FeedbackItem(
            comment_id=1,
            author="maintainer",
            body="Please fix",
            action=FeedbackAction.CODE_CHANGE,
            bot_context="[Bot review by @coderabbitai] Unused import: start_http_server",
        )
        prompt = patrol._build_fix_prompt(item, "file content", "server.py", "")
        assert "bot code review" in prompt
        assert "Unused import" in prompt
        assert "coderabbitai" in prompt

    def test_prompt_includes_diff_hunk(self):
        github = MagicMock()
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        item = FeedbackItem(
            comment_id=1,
            author="reviewer",
            body="Fix it",
            action=FeedbackAction.CODE_CHANGE,
            diff_hunk="@@ -1,3 +1,4 @@",
        )
        prompt = patrol._build_fix_prompt(item, "", None, "diff content")
        assert "@@ -1,3 +1,4 @@" in prompt


class TestExtractFixedContent:
    """Test _extract_fixed_content method."""

    def test_plain_content(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._extract_fixed_content("import os\nprint('hello')")
        assert "import os" in result

    def test_strips_code_fences(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._extract_fixed_content("```python\nimport os\nprint('hello')\n```")
        assert result.strip() == "import os\nprint('hello')"
        assert "```" not in result


class TestParseClassifications:
    """Test _parse_classifications method."""

    def test_parses_yaml(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        response = """```yaml
classifications:
  - comment_number: 1
    action: code_change
```"""
        feedback = [
            {
                "id": 1,
                "author": "user",
                "body": "fix this",
                "is_inline": True,
                "file_path": "main.py",
                "line": 10,
                "diff_hunk": None,
                "bot_context": None,
            }
        ]
        items = patrol._parse_classifications(response, feedback)
        assert len(items) == 1
        assert items[0].action == FeedbackAction.CODE_CHANGE

    def test_invalid_yaml(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._parse_classifications("not yaml {{[", [])
        assert result == []

    def test_out_of_range_index(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        response = """```yaml
classifications:
  - comment_number: 5
    action: code_change
```"""
        feedback = [{"id": 1, "author": "user", "body": "x", "is_inline": False}]
        items = patrol._parse_classifications(response, feedback)
        assert len(items) == 0


class TestCheckAssignedIssues:
    """Test _check_assigned_issues method."""

    @pytest.mark.asyncio
    async def test_finds_assigned_issues(self):
        github = MagicMock()
        github.get_assigned_issues = AsyncMock(
            return_value=[
                {"number": 42, "title": "Fix bug", "html_url": "https://example.com/42"},
            ]
        )
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = PatrolResult()
        repos = {"owner/repo"}
        await patrol._check_assigned_issues(repos, "tang-vu", result, dry_run=True)
        assert result.issues_found == 1
        assert result.assigned_issues[0]["number"] == 42

    @pytest.mark.asyncio
    async def test_empty_repos(self):
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = PatrolResult()
        await patrol._check_assigned_issues(set(), "tang-vu", result)
        assert result.issues_found == 0

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        github = MagicMock()
        github.get_assigned_issues = AsyncMock(side_effect=Exception("API error"))
        patrol = PRPatrol(github=github, llm=MagicMock())
        result = PatrolResult()
        await patrol._check_assigned_issues({"owner/repo"}, "tang-vu", result)
        assert result.issues_found == 0


class TestPatrolSkips:
    """Test patrol method skip logic."""

    @pytest.mark.asyncio
    async def test_skips_non_open_prs(self):
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "tang-vu"})
        github.get_assigned_issues = AsyncMock(return_value=[])
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol.patrol(
            [{"repo": "o/r", "pr_number": 1, "status": "closed"}],
            dry_run=True,
        )
        assert result.prs_skipped == 1
        assert result.prs_checked == 0

    @pytest.mark.asyncio
    async def test_filters_by_pr_number(self):
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "tang-vu"})
        github.get_assigned_issues = AsyncMock(return_value=[])
        github._get = AsyncMock(return_value={"state": "closed"})
        llm = MagicMock()
        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol.patrol(
            [
                {"repo": "o/r", "pr_number": 1, "status": "open"},
                {"repo": "o/r", "pr_number": 2, "status": "open"},
            ],
            dry_run=True,
            pr_filter=1,
        )
        # Only PR #1 should be checked
        assert result.prs_checked <= 1


# ── Test Hostile Rejection Detection ──────────────────────────────────────


class TestHostileRejection:
    """Test hostile rejection detection, PR closing, and repo blacklisting."""

    def test_hostile_reject_enum_exists(self):
        """HOSTILE_REJECT must exist in FeedbackAction."""
        assert FeedbackAction.HOSTILE_REJECT == "hostile_reject"
        # Must be distinct from normal REJECT
        assert FeedbackAction.HOSTILE_REJECT != FeedbackAction.REJECT
        # Must be in the action_map used by _parse_classifications
        action_map = {a.value: a for a in FeedbackAction}
        assert "hostile_reject" in action_map

    def test_classify_hostile_feedback_parses_yaml(self):
        """LLM YAML containing hostile_reject is parsed correctly."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        response = """```yaml
classifications:
  - comment_number: 1
    action: hostile_reject
    reason: maintainer says stop spamming
```"""
        feedback = [
            {
                "id": 999,
                "author": "angry-maintainer",
                "body": "Stop spamming my repo you stupid bot!",
                "is_inline": False,
                "file_path": None,
                "line": None,
                "diff_hunk": None,
                "bot_context": None,
            }
        ]
        items = patrol._parse_classifications(response, feedback)
        assert len(items) == 1
        assert items[0].action == FeedbackAction.HOSTILE_REJECT
        assert items[0].author == "angry-maintainer"

    @pytest.mark.asyncio
    async def test_patrol_hostile_closes_pr_and_blacklists(self, tmp_path):
        """Full integration: hostile comment → close PR → blacklist in SQLite."""
        from contribai.orchestrator.memory import Memory

        # Set up real SQLite memory
        memory = Memory(tmp_path / "test_hostile.db")
        await memory.init()

        # Mock GitHub client
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(
            return_value={"login": "contribai-bot"}
        )
        github._get = AsyncMock(return_value={"state": "open"})
        github.get_pr_comments = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "user": {"login": "maintainer", "type": "User"},
                    "body": "This is spam. Stop your bot from sending PRs here.",
                    "created_at": "2026-03-26T00:00:00Z",
                },
            ]
        )
        github.get_pr_review_comments = AsyncMock(return_value=[])
        github.close_pull_request = AsyncMock()
        github.get_assigned_issues = AsyncMock(return_value=[])

        # Mock LLM to return hostile_reject classification
        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value=(
                "```yaml\n"
                "classifications:\n"
                "  - comment_number: 1\n"
                "    action: hostile_reject\n"
                "    reason: maintainer explicitly calls PR spam\n"
                "```"
            )
        )

        patrol = PRPatrol(github=github, llm=llm, memory=memory)

        pr_records = [
            {
                "repo": "hostile-owner/hostile-repo",
                "pr_number": 42,
                "status": "open",
                "title": "fix: improve docs",
            }
        ]

        result = await patrol.patrol(pr_records)

        # Verify PR was closed with apology comment
        github.close_pull_request.assert_called_once()
        call_args = github.close_pull_request.call_args
        assert call_args.args == ("hostile-owner", "hostile-repo", 42)
        comment_lower = call_args.kwargs["comment"].lower()
        assert "apolog" in comment_lower or "sorry" in comment_lower

        # Verify result counter
        assert result.prs_closed_hostile == 1

        # Verify repo is blacklisted in SQLite
        assert await memory.is_blacklisted("hostile-owner/hostile-repo") is True

        # Verify blacklist data
        bl = await memory.get_blacklisted_repos()
        assert len(bl) == 1
        assert bl[0]["repo"] == "hostile-owner/hostile-repo"
        assert "spam" in bl[0]["reason"].lower()
        assert bl[0]["pr_number"] == 42

        await memory.close()

    @pytest.mark.asyncio
    async def test_patrol_hostile_handles_deleted_repo(self):
        """If repo is already deleted, close_pull_request raises 404 — patrol must not crash."""
        from contribai.core.exceptions import GitHubAPIError

        github = MagicMock()
        github.get_authenticated_user = AsyncMock(
            return_value={"login": "contribai-bot"}
        )
        github._get = AsyncMock(return_value={"state": "open"})
        github.get_pr_comments = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "user": {"login": "maintainer", "type": "User"},
                    "body": "GO AWAY BOT",
                    "created_at": "2026-03-26T00:00:00Z",
                },
            ]
        )
        github.get_pr_review_comments = AsyncMock(return_value=[])
        # Simulate repo deleted → 404
        github.close_pull_request = AsyncMock(
            side_effect=GitHubAPIError("Not found", status_code=404)
        )
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        llm.complete = AsyncMock(
            return_value=(
                "```yaml\n"
                "classifications:\n"
                "  - comment_number: 1\n"
                "    action: hostile_reject\n"
                "    reason: hostile\n"
                "```"
            )
        )

        patrol = PRPatrol(github=github, llm=llm)

        result = await patrol.patrol(
            [{"repo": "gone/deleted", "pr_number": 99, "status": "open"}]
        )

        # Should still count as hostile even if close failed
        assert result.prs_closed_hostile == 1
        # Should NOT appear in errors (gracefully handled)
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_blacklist_filtering_in_discovery(self, tmp_path):
        """Discovery engine filters out blacklisted repos."""
        from contribai.core.config import DiscoveryConfig
        from contribai.core.models import Repository
        from contribai.github.discovery import RepoDiscovery
        from contribai.orchestrator.memory import Memory

        # Set up memory with a blacklisted repo
        memory = Memory(tmp_path / "test_discovery.db")
        await memory.init()
        await memory.blacklist_repo("evil-owner", "evil-repo", "hostile maintainer", 1)

        # Mock client with search returning 2 repos (one blacklisted)
        client = MagicMock()
        client.search_repositories = AsyncMock(
            return_value=[
                Repository(
                    owner="evil-owner",
                    name="evil-repo",
                    full_name="evil-owner/evil-repo",
                    stars=500,
                    forks=10,
                    open_issues=5,
                    has_license=True,
                ),
                Repository(
                    owner="good-owner",
                    name="good-repo",
                    full_name="good-owner/good-repo",
                    stars=300,
                    forks=20,
                    open_issues=8,
                    has_license=True,
                ),
            ]
        )
        client.get_contributing_guide = AsyncMock(return_value=None)

        config = DiscoveryConfig(
            languages=["python"],
            require_contributing_guide=False,
        )
        discovery = RepoDiscovery(client, config, memory=memory)

        results = await discovery.discover()

        # Only good-repo should survive
        repo_names = [r.full_name for r in results]
        assert "evil-owner/evil-repo" not in repo_names
        assert "good-owner/good-repo" in repo_names

        await memory.close()


# ── Test CI Auto-Healing ──────────────────────────────────────────────────


SAMPLE_CI_LOG_WITH_TRACEBACK = """\
2026-03-26T10:00:00.000Z Running tests...
2026-03-26T10:00:01.000Z ==================== test session starts ====================
2026-03-26T10:00:02.000Z collected 12 items
2026-03-26T10:00:02.100Z tests/test_main.py .....F......
2026-03-26T10:00:03.000Z FAILURES
2026-03-26T10:00:03.100Z ______________________________ test_parse ______________________________
2026-03-26T10:00:03.200Z
Traceback (most recent call last):
  File "/home/runner/work/myrepo/myrepo/src/parser.py", line 42, in parse_data
    result = json.loads(data)
  File "/home/runner/work/myrepo/myrepo/tests/test_main.py", line 18, in test_parse
    assert parse_data("invalid") == {}
AssertionError: assert None == {}
2026-03-26T10:00:04.000Z ==================== 1 failed, 11 passed ====================
"""

SAMPLE_CI_LOG_NO_TRACEBACK = """\
2026-03-26T10:00:00.000Z Installing dependencies...
2026-03-26T10:00:01.000Z pip install -r requirements.txt
2026-03-26T10:00:02.000Z Successfully installed all packages
2026-03-26T10:00:03.000Z Running linter...
2026-03-26T10:00:04.000Z All checks passed.
"""


class TestCIAutoHealing:
    """Test CI auto-healing feature."""

    def test_extract_ci_traceback_python(self):
        """Extracts Python traceback from a CI log."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._extract_ci_traceback(SAMPLE_CI_LOG_WITH_TRACEBACK)
        assert "Traceback (most recent call last)" in result
        assert "AssertionError" in result
        assert "parser.py" in result
        # Must NOT be the full log — it's a slice
        assert len(result) <= 3000

    def test_extract_ci_traceback_no_error_returns_tail(self):
        """Fallback: returns tail of log when no error patterns found."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._extract_ci_traceback(SAMPLE_CI_LOG_NO_TRACEBACK)
        assert result  # not empty
        assert "All checks passed" in result

    def test_extract_ci_traceback_empty_log(self):
        """Returns empty string for empty log."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        assert patrol._extract_ci_traceback("") == ""

    @pytest.mark.asyncio
    async def test_ci_auto_heal_triggers_fix(self, tmp_path):
        """Full flow: failed check → log download → LLM fix → commit pushed."""
        from contribai.orchestrator.memory import Memory

        memory = Memory(tmp_path / "test_ci_heal.db")
        await memory.init()
        await memory.record_pr(
            "owner/repo", 10, "https://github.com/owner/repo/pull/10",
            "fix: something", "code_quality",
        )

        github = MagicMock()
        github.get_authenticated_user = AsyncMock(
            return_value={"login": "bot", "name": "Bot", "email": "bot@test.com"}
        )
        github._get = AsyncMock(
            side_effect=[
                # PR live status
                {
                    "state": "open",
                    "number": 10,
                    "head": {
                        "sha": "abc123",
                        "ref": "fix-branch",
                        "repo": {
                            "owner": {"login": "bot"},
                            "name": "repo",
                        },
                    },
                },
                # File SHA lookup
                {"sha": "file_sha_123"},
            ]
        )
        github.get_pr_check_runs = AsyncMock(
            return_value=[
                {"id": 555, "name": "pytest", "status": "completed", "conclusion": "failure"},
            ]
        )
        github.download_check_run_log = AsyncMock(
            return_value=SAMPLE_CI_LOG_WITH_TRACEBACK,
        )
        github.get_pr_diff = AsyncMock(return_value="--- a/src/parser.py\n+++ b/src/parser.py\n@@ -1 +1 @@\n-old\n+new")
        github.create_or_update_file = AsyncMock()
        github.create_pr_comment = AsyncMock()
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="```python\nimport json\ndef parse_data(data):\n    try:\n        return json.loads(data)\n    except Exception:\n        return {}\n```")

        patrol = PRPatrol(github=github, llm=llm, memory=memory)
        result = await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 10, "status": "open", "title": "fix: something"}],
        )

        assert result.ci_fixes_pushed == 1
        github.create_or_update_file.assert_called_once()
        github.create_pr_comment.assert_called_once()
        comment_body = github.create_pr_comment.call_args.args[3]
        assert "contribai-patrol" in comment_body

        # Verify attempt counter incremented
        attempts = await memory.get_ci_fix_attempts("owner/repo", 10)
        assert attempts == 1

        await memory.close()

    @pytest.mark.asyncio
    async def test_ci_auto_heal_max_attempts_closes_pr(self, tmp_path):
        """After MAX_CI_FIX_ATTEMPTS, PR is closed instead of retrying."""
        from contribai.orchestrator.memory import Memory

        memory = Memory(tmp_path / "test_ci_max.db")
        await memory.init()
        await memory.record_pr(
            "owner/repo", 20, "https://github.com/owner/repo/pull/20",
            "fix: broken", "code_quality",
        )
        # Simulate 2 previous attempts
        await memory.increment_ci_fix_attempts("owner/repo", 20)
        await memory.increment_ci_fix_attempts("owner/repo", 20)

        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "bot"})
        github._get = AsyncMock(
            return_value={
                "state": "open",
                "number": 20,
                "head": {"sha": "def456", "ref": "fix-branch", "repo": {"owner": {"login": "bot"}, "name": "repo"}},
            }
        )
        github.get_pr_check_runs = AsyncMock(
            return_value=[
                {"id": 777, "name": "tests", "status": "completed", "conclusion": "failure"},
            ]
        )
        github.close_pull_request = AsyncMock()
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        # LLM should NOT be called
        llm.complete = AsyncMock(side_effect=AssertionError("LLM should not be called"))

        patrol = PRPatrol(github=github, llm=llm, memory=memory)
        result = await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 20, "status": "open", "title": "fix: broken"}],
        )

        # PR should have been closed
        github.close_pull_request.assert_called_once()
        close_args = github.close_pull_request.call_args
        assert close_args.args == ("owner", "repo", 20)
        assert "closing" in close_args.kwargs["comment"].lower() or "CI" in close_args.kwargs["comment"]

        # No CI fix should have been pushed
        assert result.ci_fixes_pushed == 0

        await memory.close()

    def test_download_log_graceful_on_empty(self):
        """_extract_ci_traceback handles empty string gracefully."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        result = patrol._extract_ci_traceback("")
        assert result == ""

    def test_guess_file_from_traceback(self):
        """Extracts file path from Python traceback."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        tb = 'File "/home/runner/work/myrepo/myrepo/src/parser.py", line 42, in parse_data'
        result = patrol._guess_file_from_traceback(tb, "")
        assert result == "src/parser.py"

    def test_guess_file_from_diff_fallback(self):
        """Falls back to diff when traceback has no File patterns."""
        patrol = PRPatrol(github=MagicMock(), llm=MagicMock())
        diff = "--- a/old.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-x\n+y"
        result = patrol._guess_file_from_traceback("some error", diff)
        assert result == "src/main.py"

class TestGitHubReplies:
    """Validate the GITHUB_REPLIES human persona dictionary."""

    def test_all_states_present(self):
        expected = {
            "FIX_APPLIED", "COMMIT_FIX", "QUESTION_OPENER",
            "QUESTION_CLOSER", "HOSTILE_CLOSE", "CI_FIX_APPLIED",
            "CI_LIMIT_CLOSE", "COMMIT_CI_FIX",
        }
        assert set(GITHUB_REPLIES.keys()) == expected

    def test_all_variants_non_empty(self):
        for state, variants in GITHUB_REPLIES.items():
            assert len(variants) >= 2, f"{state} has fewer than 2 variants"
            for v in variants:
                assert len(v.strip()) > 0, f"Empty variant in {state}"

    def test_no_robot_emojis(self):
        """No bot-flagging emojis in any reply variant."""
        robot_emojis = {"\U0001f4dd", "\U0001f527", "\u2705", "\U0001f916", "\U0001f64f"}
        for state, variants in GITHUB_REPLIES.items():
            for v in variants:
                for emoji in robot_emojis:
                    assert emoji not in v, f"Robot emoji {emoji!r} in {state}: {v}"

    def test_format_placeholders_resolve(self):
        """All .format() placeholders must resolve without error."""
        test_data = {
            "COMMIT_FIX": {"summary": "test change"},
            "CI_FIX_APPLIED": {"check_name": "pytest", "file_path": "main.py"},
            "CI_LIMIT_CLOSE": {"attempts": 2},
            "COMMIT_CI_FIX": {"check_name": "lint"},
        }
        for state, kwargs in test_data.items():
            for v in GITHUB_REPLIES[state]:
                result = v.format(**kwargs)
                assert len(result) > 0

    def test_no_auto_fix_phrasing(self):
        """Verify no robotic phrasing survives."""
        banned = ["auto-fix", "Addressed this feedback", "AI has analyzed", "The AI"]
        for state, variants in GITHUB_REPLIES.items():
            for v in variants:
                for b in banned:
                    assert b.lower() not in v.lower(), f"Banned phrase {b!r} in {state}: {v}"

class TestAutoReaction:
    """Test the auto-like reaction feature."""

    @pytest.mark.asyncio
    async def test_reaction_called_for_code_change(self):
        """Reaction API is called before handling a code fix."""
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "bot", "name": "Bot", "email": "bot@test.com"})
        github._get = AsyncMock(side_effect=[
            {"state": "open", "number": 1, "head": {"sha": "abc", "ref": "fix", "repo": {"owner": {"login": "bot"}, "name": "r"}}},
        ])
        github.get_pr_check_runs = AsyncMock(return_value=[])
        github.get_pr_comments = AsyncMock(return_value=[
            {"id": 50, "user": {"login": "reviewer", "type": "User"}, "body": "Fix this bug", "created_at": "2026-01-01"},
        ])
        github.get_pr_review_comments = AsyncMock(return_value=[])
        github.add_comment_reaction = AsyncMock(return_value={"id": 1})
        github.get_assigned_issues = AsyncMock(return_value=[])

        # Mock LLM to classify as CODE_CHANGE
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=[
            # Classification response
            "```yaml\nclassifications:\n  - comment_number: 1\n    action: code_change\n    reason: fix needed\n```",
            # Fix response
            "```python\nprint('fixed')\n```",
        ])

        # Mock file operations — will fail because no file_path from classification
        github.get_file_content = AsyncMock(return_value="old content")
        github.get_pr_diff = AsyncMock(return_value="--- a/x\n+++ b/x\n")
        github.create_or_update_file = AsyncMock()
        github.create_pr_comment = AsyncMock()
        github.create_pr_review_comment_reply = AsyncMock()

        patrol = PRPatrol(github=github, llm=llm)
        await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 1, "status": "open", "title": "test"}],
        )

        # The reaction must have been called with is_review_comment=False
        # (because the comment came from get_pr_comments = issue comment)
        github.add_comment_reaction.assert_called_once_with(
            "owner", "repo", 50, is_review_comment=False,
        )

    @pytest.mark.asyncio
    async def test_reaction_routes_inline_to_pulls_endpoint(self):
        """Inline (review) comments route to /pulls/comments/{id}/reactions."""
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "bot"})
        github._get = AsyncMock(side_effect=[
            {"state": "open", "number": 1, "head": {"sha": "abc", "ref": "fix", "repo": {"owner": {"login": "bot"}, "name": "r"}}},
        ])
        github.get_pr_check_runs = AsyncMock(return_value=[])
        github.get_pr_comments = AsyncMock(return_value=[])
        github.get_pr_review_comments = AsyncMock(return_value=[
            {
                "id": 77, "user": {"login": "reviewer", "type": "User"},
                "body": "Style issue here", "path": "main.py",
                "line": 10, "original_line": 10,
                "diff_hunk": "@@ -1 +1 @@", "created_at": "2026-01-01",
            },
        ])
        github.add_comment_reaction = AsyncMock(return_value={"id": 1})
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=[
            "```yaml\nclassifications:\n  - comment_number: 1\n    action: style_fix\n    reason: style\n```",
            "```python\nfixed\n```",
        ])
        github.get_file_content = AsyncMock(return_value="old")
        github.get_pr_diff = AsyncMock(return_value="diff")
        github.create_or_update_file = AsyncMock()
        github.create_pr_comment = AsyncMock()
        github.create_pr_review_comment_reply = AsyncMock()

        patrol = PRPatrol(github=github, llm=llm)
        await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 1, "status": "open", "title": "test"}],
        )

        # Must route to review comment endpoint (is_review_comment=True)
        github.add_comment_reaction.assert_called_once_with(
            "owner", "repo", 77, is_review_comment=True,
        )

    @pytest.mark.asyncio
    async def test_reaction_failure_does_not_crash_patrol(self):
        """If reaction API fails, patrol continues processing normally."""
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "bot"})
        github._get = AsyncMock(side_effect=[
            {"state": "open", "number": 1, "head": {"sha": "abc", "ref": "fix", "repo": {"owner": {"login": "bot"}, "name": "r"}}},
        ])
        github.get_pr_check_runs = AsyncMock(return_value=[])
        github.get_pr_comments = AsyncMock(return_value=[
            {"id": 88, "user": {"login": "reviewer", "type": "User"}, "body": "Question?", "created_at": "2026-01-01"},
        ])
        github.get_pr_review_comments = AsyncMock(return_value=[])
        # Reaction fails with 403 — this should NOT crash
        github.add_comment_reaction = AsyncMock(side_effect=Exception("403 Forbidden"))
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=[
            "```yaml\nclassifications:\n  - comment_number: 1\n    action: question\n    reason: question\n```",
            "Here is the explanation.",
        ])
        github.create_pr_comment = AsyncMock()
        github.create_pr_review_comment_reply = AsyncMock()

        patrol = PRPatrol(github=github, llm=llm)
        result = await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 1, "status": "open", "title": "test"}],
        )

        # Despite reaction failure, the reply should still be sent
        assert result.replies_sent == 1
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_no_reaction_on_dry_run(self):
        """Reactions should NOT be sent during dry runs."""
        github = MagicMock()
        github.get_authenticated_user = AsyncMock(return_value={"login": "bot"})
        github._get = AsyncMock(return_value={
            "state": "open", "number": 1,
            "head": {"sha": "abc", "ref": "fix", "repo": {"owner": {"login": "bot"}, "name": "r"}},
        })
        github.get_pr_check_runs = AsyncMock(return_value=[])
        github.get_pr_comments = AsyncMock(return_value=[
            {"id": 99, "user": {"login": "reviewer", "type": "User"}, "body": "Fix this", "created_at": "2026-01-01"},
        ])
        github.get_pr_review_comments = AsyncMock(return_value=[])
        github.add_comment_reaction = AsyncMock()
        github.get_assigned_issues = AsyncMock(return_value=[])

        llm = MagicMock()
        llm.complete = AsyncMock(return_value=(
            "```yaml\nclassifications:\n  - comment_number: 1\n    action: code_change\n    reason: fix\n```"
        ))

        patrol = PRPatrol(github=github, llm=llm)
        await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 1, "status": "open", "title": "test"}],
            dry_run=True,
        )

        # Reaction should NOT be called in dry-run mode
        github.add_comment_reaction.assert_not_called()


class TestAddCommentReaction:
    """Test GitHubClient.add_comment_reaction endpoint routing."""

    @pytest.mark.asyncio
    async def test_review_comment_routes_to_pulls(self):
        """is_review_comment=True routes to /pulls/comments/{id}/reactions."""
        from contribai.github.client import GitHubClient

        client = GitHubClient(token="fake")
        client._post = AsyncMock(return_value={"id": 1, "content": "+1"})

        result = await client.add_comment_reaction("owner", "repo", 123, is_review_comment=True)
        assert result == {"id": 1, "content": "+1"}
        client._post.assert_called_once_with(
            "/repos/owner/repo/pulls/comments/123/reactions",
            json={"content": "+1"},
        )
        await client.close()

    @pytest.mark.asyncio
    async def test_issue_comment_routes_to_issues(self):
        """is_review_comment=False routes to /issues/comments/{id}/reactions."""
        from contribai.github.client import GitHubClient

        client = GitHubClient(token="fake")
        client._post = AsyncMock(return_value={"id": 2, "content": "+1"})

        result = await client.add_comment_reaction("owner", "repo", 456, is_review_comment=False)
        assert result == {"id": 2, "content": "+1"}
        client._post.assert_called_once_with(
            "/repos/owner/repo/issues/comments/456/reactions",
            json={"content": "+1"},
        )
        await client.close()

    @pytest.mark.asyncio
    async def test_custom_reaction(self):
        """Custom reaction types (heart, rocket, etc.) work."""
        from contribai.github.client import GitHubClient

        client = GitHubClient(token="fake")
        client._post = AsyncMock(return_value={"id": 3, "content": "heart"})

        result = await client.add_comment_reaction(
            "owner", "repo", 789, is_review_comment=True, reaction="heart",
        )
        assert result["content"] == "heart"
        client._post.assert_called_once_with(
            "/repos/owner/repo/pulls/comments/789/reactions",
            json={"content": "heart"},
        )
        await client.close()

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self):
        """If API fails, returns None instead of raising."""
        from contribai.github.client import GitHubClient

        client = GitHubClient(token="fake")
        client._post = AsyncMock(side_effect=Exception("403 Forbidden"))

        result = await client.add_comment_reaction("owner", "repo", 999, is_review_comment=True)
        assert result is None
        await client.close()

