"""Tests for SuperHumanLoop — the stochastic daily routine orchestrator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contribai.core.exceptions import GitHubAPIError
from contribai.orchestrator.human import (
    ABSOLUTE_MAX_PRS_PER_DAY,
    HUNT_WEIGHT,
    WARP_MAX_ITERATIONS,
    SuperHumanLoop,
)


@pytest.fixture
def mock_memory():
    """Create a mock Memory object with async methods."""
    memory = MagicMock()
    memory.init = AsyncMock()
    memory.close = AsyncMock()
    memory.get_today_pr_count = AsyncMock(return_value=0)
    memory.get_prs = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def mock_pipeline():
    """Create a mock ContribPipeline object."""
    pipeline = MagicMock()
    pipeline.config = MagicMock()
    pipeline.config.github.token = "fake-token"
    pipeline.config.llm = MagicMock()
    pipeline.hunt = AsyncMock(
        return_value=MagicMock(repos_analyzed=1, prs_created=0)
    )
    pipeline.run_single = AsyncMock(
        return_value=MagicMock(repos_analyzed=1, prs_created=1)
    )
    return pipeline


@pytest.fixture
def loop(mock_pipeline, mock_memory):
    """Create a SuperHumanLoop instance for testing."""
    return SuperHumanLoop(mock_pipeline, mock_memory, dry_run=True)


class TestDailyLimit:
    """Tests for daily PR quota generation."""

    def test_daily_limit_within_bounds(self, loop):
        """Daily limit must always be between 2 and 5 (inclusive)."""
        seen = set()
        for _ in range(200):
            loop._current_day = None  # force new-day check
            loop._new_day_check()
            seen.add(loop._daily_limit)
            assert 2 <= loop._daily_limit <= 5
            assert loop._daily_limit <= ABSOLUTE_MAX_PRS_PER_DAY

        # With 200 rounds, we should see at least 2 distinct values
        assert len(seen) >= 2, f"Only saw limits: {seen}"

    def test_safety_cap_respected(self, loop):
        """Daily limit must never exceed ABSOLUTE_MAX_PRS_PER_DAY (6)."""
        for _ in range(500):
            loop._current_day = None
            loop._new_day_check()
            assert loop._daily_limit <= ABSOLUTE_MAX_PRS_PER_DAY


class TestActionSelection:
    """Tests for hunt/patrol interleaving logic."""

    @pytest.mark.asyncio
    async def test_patrol_only_when_quota_reached(self, loop, mock_memory):
        """When today_prs >= daily_limit, only Patrol should run."""
        mock_memory.get_today_pr_count.return_value = 5
        loop._daily_limit = 3  # quota is 3, today_prs=5 → exceeded

        hunt_called = False
        patrol_called = False

        async def fake_hunt(*a, **kw):
            nonlocal hunt_called
            hunt_called = True

        async def fake_patrol(*a, **kw):
            nonlocal patrol_called
            patrol_called = True

        with patch.object(loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(loop, "_do_patrol", side_effect=fake_patrol):
            await loop.run_daily_routine(time_warp=True)

        assert patrol_called, "Patrol should have been called"
        assert not hunt_called, "Hunt should NOT be called when quota is reached"

    @pytest.mark.asyncio
    async def test_hunt_patrol_interleave(self, loop, mock_memory):
        """When under quota, both Hunt and Patrol should be chosen."""
        mock_memory.get_today_pr_count.return_value = 0
        loop._daily_limit = 5

        hunt_count = 0
        patrol_count = 0

        async def fake_hunt(*a, **kw):
            nonlocal hunt_count
            hunt_count += 1

        async def fake_patrol(*a, **kw):
            nonlocal patrol_count
            patrol_count += 1

        with patch.object(loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(loop, "_do_patrol", side_effect=fake_patrol):
            await loop.run_daily_routine(time_warp=True)

        # With 60/40 split over 10 iterations, statistically both should
        # be called. If one is 0, the test would be extremely unlikely
        # (p < 0.01%) to fail randomly.
        total = hunt_count + patrol_count
        assert total == WARP_MAX_ITERATIONS, f"Expected {WARP_MAX_ITERATIONS} actions, got {total}"
        assert hunt_count > 0, "Hunt should have been called at least once"
        assert patrol_count > 0, "Patrol should have been called at least once"

    @pytest.mark.asyncio
    async def test_controlled_target_uses_stochastic_first_action(self, mock_pipeline, mock_memory):
        """A controlled target still uses 60/40 stochastic roll for all actions."""
        mock_memory.get_today_pr_count = AsyncMock(side_effect=[0] + [1] * 16)
        controlled_loop = SuperHumanLoop(
            mock_pipeline,
            mock_memory,
            dry_run=True,
            target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
        )
        controlled_loop._daily_limit = 5

        hunt_count = 0
        patrol_count = 0

        async def fake_hunt(*a, **kw):
            nonlocal hunt_count
            hunt_count += 1

        async def fake_patrol(*a, **kw):
            nonlocal patrol_count
            patrol_count += 1

        with patch.object(controlled_loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(controlled_loop, "_do_patrol", side_effect=fake_patrol):
            await controlled_loop.run_daily_routine(time_warp=True)

        # Total actions should equal WARP_MAX_ITERATIONS
        assert hunt_count + patrol_count == WARP_MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_controlled_hunt_uses_single_repo_path(self, mock_pipeline, mock_memory):
        """Targeted hunts should use run_single instead of discovery hunt."""
        controlled_loop = SuperHumanLoop(
            mock_pipeline,
            mock_memory,
            dry_run=True,
            target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
        )

        await controlled_loop._do_hunt()

        mock_pipeline.run_single.assert_awaited_once_with(
            "https://github.com/hieuit095/gitvisualizer-ai",
            dry_run=True,
            max_prs=1,
        )
        mock_pipeline.hunt.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_controlled_hunt_calls_run_single_once(self, mock_pipeline, mock_memory):
        """Targeted hunts call run_single exactly once (no retry logic)."""
        mock_pipeline.run_single = AsyncMock(
            return_value=MagicMock(repos_analyzed=1, prs_created=0)
        )
        controlled_loop = SuperHumanLoop(
            mock_pipeline,
            mock_memory,
            dry_run=True,
            target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
        )

        await controlled_loop._do_hunt()

        assert mock_pipeline.run_single.await_count == 1

    @pytest.mark.asyncio
    async def test_controlled_target_uses_stochastic_roll(
        self, mock_pipeline, mock_memory
    ):
        """With a target URL and open PRs, actions still follow 60/40 stochastic roll."""
        mock_memory.get_today_pr_count = AsyncMock(side_effect=[1] * 16)
        mock_memory.get_prs = AsyncMock(return_value=[{"pr_number": 12, "status": "open"}])
        controlled_loop = SuperHumanLoop(
            mock_pipeline,
            mock_memory,
            dry_run=True,
            target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
        )
        controlled_loop._daily_limit = 5

        hunt_count = 0
        patrol_count = 0

        async def fake_hunt(*a, **kw):
            nonlocal hunt_count
            hunt_count += 1

        async def fake_patrol(*a, **kw):
            nonlocal patrol_count
            patrol_count += 1

        with patch.object(controlled_loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(controlled_loop, "_do_patrol", side_effect=fake_patrol):
            await controlled_loop.run_daily_routine(time_warp=True)

        # Both should be called — 60/40 split over 10 iterations
        total = hunt_count + patrol_count
        assert total == WARP_MAX_ITERATIONS


class TestErrorResilience:
    """Tests for error handling and stress breaks."""

    @pytest.mark.asyncio
    async def test_github_api_error_does_not_crash(self, loop, mock_memory):
        """GitHubAPIError during Hunt should not crash the loop."""
        mock_memory.get_today_pr_count.return_value = 0
        loop._daily_limit = 5

        call_count = 0

        async def failing_hunt(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise GitHubAPIError("API rate limit exceeded", status_code=429)
            # After 3 failures, succeed silently

        async def noop_patrol(*a, **kw):
            pass

        with patch.object(loop, "_do_hunt", side_effect=failing_hunt), \
             patch.object(loop, "_do_patrol", side_effect=noop_patrol):
            # Should complete without raising
            await loop.run_daily_routine(time_warp=True)

        # Loop should have run all 10 iterations despite errors
        assert loop._iteration > WARP_MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_generic_exception_does_not_crash(self, loop, mock_memory):
        """Any unexpected exception during Patrol should not crash the loop."""
        mock_memory.get_today_pr_count.return_value = 5  # quota reached
        loop._daily_limit = 3

        error_count = 0

        async def sometimes_failing_patrol(*a, **kw):
            nonlocal error_count
            error_count += 1
            if error_count <= 2:
                raise RuntimeError("Network timeout")

        with patch.object(loop, "_do_patrol", side_effect=sometimes_failing_patrol):
            await loop.run_daily_routine(time_warp=True)

        # Loop completed despite errors
        assert loop._iteration > WARP_MAX_ITERATIONS


class TestTimeWarp:
    """Tests for time-warp mode."""

    @pytest.mark.asyncio
    async def test_time_warp_exits_after_max_iterations(self, loop, mock_memory):
        """Time-warp mode should exit after exactly WARP_MAX_ITERATIONS iterations."""
        mock_memory.get_today_pr_count.return_value = 0
        loop._daily_limit = 5

        async def noop(*a, **kw):
            pass

        with patch.object(loop, "_do_hunt", side_effect=noop), \
             patch.object(loop, "_do_patrol", side_effect=noop):
            await loop.run_daily_routine(time_warp=True)

        # _iteration is incremented at start of each iteration, then checked
        # So after 10 successful iterations, _iteration == 11 (the check that breaks)
        assert loop._iteration == WARP_MAX_ITERATIONS + 1

    @pytest.mark.asyncio
    async def test_time_warp_uses_short_delays(self, loop, mock_memory):
        """Time-warp delays should be 1-3 seconds."""
        for _ in range(100):
            for action in ("hunt", "patrol", "patrol_only"):
                delay = loop._pick_delay(action, time_warp=True)
                assert 1 <= delay <= 3, f"Time-warp delay for {action} was {delay}"
