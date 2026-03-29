"""Tests for Friendly Repos sync logic."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.config import FarmAgentConfig, GitHubConfig, LLMConfig, AnalysisConfig, ContributionConfig, StorageConfig, DiscoveryConfig
from farm_agent.orchestrator.human import SuperHumanLoop


class FakeRepoDetails:
    """Fake Repository object returned by mocked get_repo_details."""
    def __init__(self, full_name: str, stars: int):
        self.full_name = full_name
        self.stars = stars


class TestSyncHistoricalFriendlyRepos:
    """Rigorous tests for _sync_historical_friendly_repos()."""

    @pytest.fixture
    def config(self):
        return FarmAgentConfig(
            github=GitHubConfig(token="ghp_test", max_prs_per_day=5),
            llm=LLMConfig(provider="minimax", model="MiniMax-M2.7", api_key="test_key"),
            analysis=AnalysisConfig(enabled_analyzers=["security", "quality"]),
            generator=ContributionConfig(max_files_per_pr=3),
            discovery=DiscoveryConfig(languages=["python"], stars_range=[1000, 50000]),
            storage=StorageConfig(db_path=":memory:"),
        )

    @pytest.fixture
    def mock_github(self):
        gh = MagicMock()
        gh.get_authenticated_user = AsyncMock(return_value={"login": "test-bot"})
        gh.fetch_user_merged_prs = AsyncMock()
        gh.get_repo_details = AsyncMock()
        return gh

    @pytest.fixture
    async def loop(self, config, mock_github):
        """Build a SuperHumanLoop with mocked GitHub and in-memory DB."""
        from farm_agent.orchestrator.memory import Memory

        mem = Memory(":memory:")
        await mem.init()
        await mem._db.execute("CREATE TABLE IF NOT EXISTS submitted_prs (repo TEXT, pr_number INTEGER, pr_url TEXT, title TEXT, type TEXT, status TEXT, created_at TEXT, updated_at TEXT)")
        await mem._db.commit()

        loop = SuperHumanLoop.__new__(SuperHumanLoop)
        loop._github = mock_github
        loop._memory = mem
        loop.config = config
        loop._last_sync_time = 0.0
        return loop

    @pytest.mark.asyncio
    async def test_sync_inserts_merged_prs_within_star_range(self, loop, mock_github):
        """Repos with stars within config range must be inserted."""
        # Four merged PRs: 2 within range, 2 outside
        mock_github.fetch_user_merged_prs = AsyncMock(return_value=[
            {"repo": "friendly/repo-a", "pr_number": 1, "html_url": "https://github.com/friendly/repo-a/pull/1", "title": "Fix A", "merged_at": "2026-03-27T10:00:00Z"},
            {"repo": "friendly/repo-b", "pr_number": 2, "html_url": "https://github.com/friendly/repo-b/pull/2", "title": "Fix B", "merged_at": "2026-03-27T11:00:00Z"},
            {"repo": "tiny/repo-c",  "pr_number": 3, "html_url": "https://github.com/tiny/repo-c/pull/3",  "title": "Fix C", "merged_at": "2026-03-27T12:00:00Z"},
            {"repo": "enterprise/repo-d","pr_number":4,"html_url":"https://github.com/enterprise/repo-d/pull/4","title":"Fix D","merged_at":"2026-03-27T13:00:00Z"},
        ])
        # repo-a → 5000 stars (within 1k-50k), repo-b → 25000 (within), repo-c → 50 (outside), repo-d → 100000 (outside)
        async def fake_details(owner, repo):
            repo_map = {"repo-a": 5000, "repo-b": 25000, "repo-c": 50, "repo-d": 100000}
            return FakeRepoDetails(f"{owner}/{repo}", repo_map[repo])

        mock_github.get_repo_details = AsyncMock(side_effect=fake_details)

        count = await loop._sync_historical_friendly_repos()

        # Only 2 should be inserted (repo-a and repo-b)
        assert count == 2, f"Expected 2 inserts, got {count}"

        # Verify both friendly repos are in the DB
        cur = await loop._memory._db.execute(
            "SELECT repo, pr_number, status FROM submitted_prs WHERE status='merged' ORDER BY repo"
        )
        rows = await cur.fetchall()
        repos_inserted = {r[0] for r in rows}
        assert repos_inserted == {"friendly/repo-a", "friendly/repo-b"}
        # tiny and enterprise must NOT be in the DB
        assert "tiny/repo-c" not in repos_inserted
        assert "enterprise/repo-d" not in repos_inserted

    @pytest.mark.asyncio
    async def test_sync_idempotent_no_duplicates_on_second_run(self, loop, mock_github):
        """Running sync twice must NOT insert duplicate repo entries."""
        mock_github.fetch_user_merged_prs = AsyncMock(return_value=[
            {"repo": "friendly/repo-x", "pr_number": 10, "html_url": "https://github.com/friendly/repo-x/pull/10", "title": "Fix X", "merged_at": "2026-03-27T10:00:00Z"},
        ])
        mock_github.get_repo_details = AsyncMock(return_value=FakeRepoDetails("friendly/repo-x", 8000))

        # First run
        count1 = await loop._sync_historical_friendly_repos()
        assert count1 == 1

        # Second run — same data
        count2 = await loop._sync_historical_friendly_repos()
        assert count2 == 0, f"Second run should return 0 (idempotent), got {count2}"

        # Total rows in DB should still be exactly 1
        cur = await loop._memory._db.execute("SELECT COUNT(*) FROM submitted_prs")
        total = (await cur.fetchone())[0]
        assert total == 1, f"Expected 1 row (idempotent), got {total}"

    @pytest.mark.asyncio
    async def test_sync_skips_repos_outside_star_range(self, loop, mock_github):
        """Repos with stars < min or > max must be skipped entirely."""
        mock_github.fetch_user_merged_prs = AsyncMock(return_value=[
            {"repo": "too-few/repo",  "pr_number": 1, "html_url": "https://github.com/too-few/repo/pull/1",  "title": "Fix", "merged_at": "2026-03-27T10:00:00Z"},
            {"repo": "too-many/repo2", "pr_number": 2, "html_url": "https://github.com/too-many/repo2/pull/2","title": "Fix2","merged_at":"2026-03-27T11:00:00Z"},
        ])
        # min_stars=1000, max_stars=50000 (from config fixture)
        async def fake_details(owner, repo):
            return FakeRepoDetails(f"{owner}/{repo}", 50 if "too-few" in repo else 99999)

        mock_github.get_repo_details = AsyncMock(side_effect=fake_details)

        count = await loop._sync_historical_friendly_repos()

        assert count == 0
        cur = await loop._memory._db.execute("SELECT COUNT(*) FROM submitted_prs")
        total = (await cur.fetchone())[0]
        assert total == 0

    @pytest.mark.asyncio
    async def test_sync_gracefully_handles_missing_auth_user(self, loop, mock_github):
        """If get_authenticated_user fails, return 0 without raising."""
        mock_github.get_authenticated_user = AsyncMock(side_effect=Exception("auth failed"))

        count = await loop._sync_historical_friendly_repos()
        assert count == 0

    @pytest.mark.asyncio
    async def test_sync_handles_get_repo_details_failure(self, loop, mock_github):
        """If get_repo_details fails for a repo, skip that repo without crashing."""
        mock_github.fetch_user_merged_prs = AsyncMock(return_value=[
            {"repo": "good/repo", "pr_number": 5, "html_url": "https://github.com/good/repo/pull/5", "title": "Fix", "merged_at": "2026-03-27T10:00:00Z"},
            {"repo": "bad/repo",  "pr_number": 6, "html_url": "https://github.com/bad/repo/pull/6",  "title": "Fix", "merged_at": "2026-03-27T11:00:00Z"},
        ])
        # good/repo returns valid stars; bad/repo raises
        # get_repo_details is called as get_repo_details(owner, "repo-name") — check owner
        async def fake_details(owner, repo_name):
            if "bad" in owner:  # owner is "bad" for bad/repo
                raise Exception("API error")
            return FakeRepoDetails(f"{owner}/{repo_name}", 5000)

        mock_github.get_repo_details = AsyncMock(side_effect=fake_details)

        await loop._sync_historical_friendly_repos()

        # Verify DB contents directly — only good/repo should be inserted
        cur = await loop._memory._db.execute(
            "SELECT repo, pr_number FROM submitted_prs WHERE status='merged' ORDER BY pr_number"
        )
        rows = await cur.fetchall()
        assert rows == [("good/repo", 5)], f"Expected only good/repo, got {rows}"

    @pytest.mark.asyncio
    async def test_sync_inserts_correct_pr_fields(self, loop, mock_github):
        """Verify all fields of the inserted PR record are correct."""
        mock_github.fetch_user_merged_prs = AsyncMock(return_value=[
            {
                "repo": "owner/myrepo",
                "pr_number": 42,
                "html_url": "https://github.com/owner/myrepo/pull/42",
                "title": "Fix critical bug in auth",
                "merged_at": "2026-03-28T15:00:00+00:00",
            },
        ])
        mock_github.get_repo_details = AsyncMock(return_value=FakeRepoDetails("owner/myrepo", 15000))

        await loop._sync_historical_friendly_repos()

        cur = await loop._memory._db.execute(
            "SELECT repo, pr_number, pr_url, title, type, status FROM submitted_prs WHERE status='merged'"
        )
        row = await cur.fetchone()
        assert row is not None
        repo, pr_num, pr_url, title, ptype, status = row
        assert repo == "owner/myrepo"
        assert pr_num == 42
        assert pr_url == "https://github.com/owner/myrepo/pull/42"
        assert title == "Fix critical bug in auth"
        assert ptype == "code_quality"  # default type for historical merges
        assert status == "merged"
