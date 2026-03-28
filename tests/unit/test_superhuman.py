"""Tests for SuperHumanLoop — the stochastic daily routine orchestrator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.exceptions import GitHubAPIError
from farm_agent.orchestrator.human import (
    ABSOLUTE_MAX_PRS_PER_DAY,
    DRY_HUNT_DELAY_MAX,
    DRY_HUNT_DELAY_MIN,
    HUNT_DELAY_MAX,
    HUNT_DELAY_MIN,
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
    pipeline.config.github.max_prs_per_day = 10
    pipeline.config.github.min_daily_prs = 3
    pipeline.config.github.max_daily_prs = 10
    pipeline.config.llm = MagicMock()
    pipeline.config.notifications.telegram_token = "fake-token"
    pipeline.config.notifications.telegram_chat_id = "fake-chat"
    pipeline.hunt = AsyncMock(
        return_value=MagicMock(repos_analyzed=1, prs_created=0, pr_urls=[])
    )
    pipeline.run_single = AsyncMock(
        return_value=MagicMock(repos_analyzed=1, prs_created=0, pr_urls=[])
    )
    # DEBT-03 fix: _do_patrol now reuses persistent pipeline clients
    pipeline._github = MagicMock()
    pipeline._llm = MagicMock()
    return pipeline


@pytest.fixture
def loop(mock_pipeline, mock_memory, mock_notifier):
    """Create a SuperHumanLoop instance for testing with a mocked notifier."""
    # Patch TelegramNotifier at the definition site so SuperHumanLoop.__init__
    # never creates a real httpx.AsyncClient or makes HTTP calls.
    with patch(
        "farm_agent.orchestrator.human.TelegramNotifier",
        return_value=mock_notifier,
    ):
        instance = SuperHumanLoop(mock_pipeline, mock_memory, dry_run=True)
    # Ensure the injected mock notifier is used (covers any late binding)
    instance._notifier = mock_notifier
    return instance


class TestDailyTarget:
    """Tests for daily PR target generation."""

    def test_daily_target_within_bounds(self, loop):
        """Daily target must always be between 3 and 10 (inclusive)."""
        seen = set()
        for _ in range(200):
            loop._current_day = None  # force new-day check
            loop._new_day_check()
            seen.add(loop._daily_pr_target)
            assert 3 <= loop._daily_pr_target <= 10
            assert loop._daily_pr_target <= ABSOLUTE_MAX_PRS_PER_DAY

        # With 200 rounds, we should see at least 2 distinct values
        assert len(seen) >= 2, f"Only saw targets: {seen}"

    def test_safety_cap_respected(self, loop):
        """Daily target must never exceed ABSOLUTE_MAX_PRS_PER_DAY (12)."""
        for _ in range(500):
            loop._current_day = None
            loop._new_day_check()
            assert loop._daily_pr_target <= ABSOLUTE_MAX_PRS_PER_DAY

    def test_prs_created_today_resets_on_new_day(self, loop):
        """The local PR counter should reset to 0 when a new day starts."""
        loop._prs_created_today = 3
        loop._current_day = None  # force new-day check
        loop._new_day_check()
        assert loop._prs_created_today == 0


class TestActionSelection:
    """Tests for hunt/patrol interleaving logic."""

    @pytest.mark.asyncio
    async def test_patrol_only_when_target_reached(self, loop, mock_memory):
        """When _prs_created_today >= _daily_pr_target, only Patrol should run."""
        # Initialize the day first so _new_day_check() won't reset counter
        loop._new_day_check()
        loop._daily_pr_target = 3
        loop._prs_created_today = 5  # already exceeded target

        # CRIT-01 FIX: The DB sync at startup reads get_today_pr_count.
        # Return 5 so the RAM counter stays at 5 (matching the scenario).
        mock_memory.get_today_pr_count = AsyncMock(return_value=5)

        hunt_called = False
        patrol_called = False

        async def fake_hunt(*a, **kw):
            nonlocal hunt_called
            hunt_called = True
            return 0, 0

        async def fake_patrol(*a, **kw):
            nonlocal patrol_called
            patrol_called = True

        with patch.object(loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(loop, "_do_patrol", side_effect=fake_patrol):
            await loop.run_daily_routine(time_warp=True)

        assert patrol_called, "Patrol should have been called"
        assert not hunt_called, "Hunt should NOT be called when target is reached"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_only_hunts_when_under_target(self, mock_random, loop, mock_memory):
        """When under target, ONLY Hunt should run (no stochastic patrol)."""
        loop._daily_pr_target = 99  # will never be reached in 10 iterations

        hunt_count = 0
        patrol_count = 0

        async def fake_hunt(*a, **kw):
            nonlocal hunt_count
            hunt_count += 1
            return 0, 1  # 0 PRs, 1 repo scanned

        async def fake_patrol(*a, **kw):
            nonlocal patrol_count
            patrol_count += 1

        with patch.object(loop, "_do_hunt", side_effect=fake_hunt), \
             patch.object(loop, "_do_patrol", side_effect=fake_patrol):
            await loop.run_daily_routine(time_warp=True)

        assert hunt_count == WARP_MAX_ITERATIONS, \
            f"All {WARP_MAX_ITERATIONS} iterations should be Hunt, got {hunt_count}"
        assert patrol_count == 0, \
            "Patrol should NOT be called when under target"

    @pytest.mark.asyncio
    async def test_controlled_target_uses_single_repo_path(self, mock_pipeline, mock_memory, mock_notifier):
        """Targeted hunts should use run_single instead of discovery hunt."""
        with patch("farm_agent.orchestrator.human.TelegramNotifier", return_value=mock_notifier):
            controlled_loop = SuperHumanLoop(
                mock_pipeline,
                mock_memory,
                dry_run=True,
                target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
            )
        # CRIT-01 FIX: DB guard checks target. Set a non-zero target
        # so the guard doesn't abort before reaching run_single.
        controlled_loop._daily_pr_target = 99

        await controlled_loop._do_hunt()

        mock_pipeline.run_single.assert_awaited_once_with(
            "https://github.com/hieuit095/gitvisualizer-ai",
            dry_run=True,
            max_prs=1,
        )
        mock_pipeline.hunt.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_controlled_hunt_calls_run_single_once(self, mock_pipeline, mock_memory, mock_notifier):
        """Targeted hunts call run_single exactly once (no retry logic)."""
        mock_pipeline.run_single = AsyncMock(
            return_value=MagicMock(repos_analyzed=1, prs_created=0, pr_urls=[])
        )
        with patch("farm_agent.orchestrator.human.TelegramNotifier", return_value=mock_notifier):
            controlled_loop = SuperHumanLoop(
                mock_pipeline,
                mock_memory,
                dry_run=True,
                target_repo_url="https://github.com/hieuit095/gitvisualizer-ai",
            )
        # CRIT-01 FIX: DB guard checks target. Set a non-zero target
        # so the guard doesn't abort before reaching run_single.
        controlled_loop._daily_pr_target = 99

        await controlled_loop._do_hunt()

        assert mock_pipeline.run_single.await_count == 1


class TestPRCounter:
    """Tests for the strict PR counter logic."""

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_counter_increments_only_on_success(self, mock_random, loop, mock_pipeline):
        """_prs_created_today should ONLY increment when _do_hunt returns > 0."""
        # Initialize the day first so _new_day_check() won't reset counter
        loop._new_day_check()
        loop._daily_pr_target = 99  # will never be reached
        call_count = 0

        async def fake_hunt_alternating(*a, **kw):
            nonlocal call_count
            call_count += 1
            # Return 1 PR on odd calls, 0 on even
            return (1, 1) if call_count % 2 == 1 else (0, 1)

        with patch.object(loop, "_do_hunt", side_effect=fake_hunt_alternating):
            await loop.run_daily_routine(time_warp=True)

        # With 10 iterations: calls 1,3,5,7,9 return 1 = 5 PRs
        expected_prs = 5
        assert loop._prs_created_today == expected_prs, \
            f"Expected {expected_prs} PRs, got {loop._prs_created_today}"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_counter_does_not_increment_on_error(self, mock_random, loop, mock_pipeline):
        """Errors in _do_hunt should NOT increment _prs_created_today."""
        loop._daily_pr_target = 99

        async def always_fail(*a, **kw):
            raise GitHubAPIError("rate limit", status_code=429)

        with patch.object(loop, "_do_hunt", side_effect=always_fail):
            await loop.run_daily_routine(time_warp=True)

        assert loop._prs_created_today == 0, \
            "Counter should be 0 after all errors"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_counter_does_not_increment_on_zero_prs(self, mock_random, loop, mock_pipeline):
        """Scanning 50 repos without a PR means counter stays at 0."""
        loop._daily_pr_target = 99

        async def no_pr_hunt(*a, **kw):
            return 0, 1  # 0 PRs, 1 repo scanned

        with patch.object(loop, "_do_hunt", side_effect=no_pr_hunt):
            await loop.run_daily_routine(time_warp=True)

        assert loop._prs_created_today == 0, \
            "Counter should be 0 when no PRs are created"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_switches_to_patrol_after_target_met(self, mock_random, loop, mock_pipeline):
        """After reaching target, loop should switch to patrol-only."""
        # Initialize the day first so _new_day_check() won't reset counter
        loop._new_day_check()
        loop._daily_pr_target = 2
        hunt_count = 0
        patrol_count = 0

        async def hunt_returns_one(*a, **kw):
            nonlocal hunt_count
            hunt_count += 1
            return 1, 1  # 1 PR, 1 repo

        async def count_patrol(*a, **kw):
            nonlocal patrol_count
            patrol_count += 1

        with patch.object(loop, "_do_hunt", side_effect=hunt_returns_one), \
             patch.object(loop, "_do_patrol", side_effect=count_patrol):
            await loop.run_daily_routine(time_warp=True)

        # First 2 iterations: hunt → get 1 PR each → target=2 met
        # Remaining 8 iterations: patrol only
        assert hunt_count == 2, f"Expected 2 hunts, got {hunt_count}"
        assert patrol_count == WARP_MAX_ITERATIONS - 2, \
            f"Expected {WARP_MAX_ITERATIONS - 2} patrols, got {patrol_count}"
        assert loop._prs_created_today == 2


class TestErrorResilience:
    """Tests for error handling and stress breaks."""

    @pytest.mark.asyncio
    async def test_github_api_error_does_not_crash(self, loop, mock_memory):
        """GitHubAPIError during Hunt should not crash the loop."""
        loop._daily_pr_target = 99
        call_count = 0

        async def failing_hunt(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise GitHubAPIError("API rate limit exceeded", status_code=429)
            # After 3 failures, succeed silently
            return 0, 1

        with patch.object(loop, "_do_hunt", side_effect=failing_hunt):
            # Should complete without raising
            await loop.run_daily_routine(time_warp=True)

        # Loop should have run all 10 iterations despite errors
        assert loop._iteration > WARP_MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_generic_exception_does_not_crash(self, loop, mock_memory):
        """Any unexpected exception during Patrol should not crash the loop."""
        # Initialize the day first so _new_day_check() won't reset counter
        loop._new_day_check()
        loop._daily_pr_target = 3
        loop._prs_created_today = 5  # quota reached → patrol mode

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
        loop._daily_pr_target = 99

        async def noop(*a, **kw):
            return 0, 1

        with patch.object(loop, "_do_hunt", side_effect=noop):
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


class TestDynamicSleep:
    """Tests for dynamic sleep based on hunt outcome."""

    def test_pick_delay_hunt_dry_range(self, loop):
        """hunt_dry delay should be 120-300 seconds (2-5 min)."""
        for _ in range(200):
            delay = loop._pick_delay("hunt_dry", time_warp=False)
            assert DRY_HUNT_DELAY_MIN <= delay <= DRY_HUNT_DELAY_MAX, \
                f"hunt_dry delay {delay} outside [{DRY_HUNT_DELAY_MIN}, {DRY_HUNT_DELAY_MAX}]"

    def test_pick_delay_hunt_normal_range(self, loop):
        """Normal hunt delay should be 1800-5400 seconds (30-90 min)."""
        for _ in range(200):
            delay = loop._pick_delay("hunt", time_warp=False)
            assert HUNT_DELAY_MIN <= delay <= HUNT_DELAY_MAX, \
                f"hunt delay {delay} outside [{HUNT_DELAY_MIN}, {HUNT_DELAY_MAX}]"

    def test_pick_delay_hunt_dry_time_warp(self, loop):
        """hunt_dry in time-warp mode should still use 1-3s."""
        for _ in range(100):
            delay = loop._pick_delay("hunt_dry", time_warp=True)
            assert 1 <= delay <= 3, f"Time-warp hunt_dry delay was {delay}"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_dry_hunt_uses_short_delay(self, mock_random, loop, mock_pipeline):
        """When _do_hunt returns (0, 0), delay should use hunt_dry."""
        loop._new_day_check()
        loop._daily_pr_target = 99
        delays_used = []

        async def dry_hunt(*a, **kw):
            return 0, 0  # 0 PRs, 0 repos scanned (dry run)

        original_pick = loop._pick_delay

        def tracking_pick(action, tw):
            delays_used.append(action)
            return original_pick(action, tw)

        with patch.object(loop, "_do_hunt", side_effect=dry_hunt), \
             patch.object(loop, "_pick_delay", side_effect=tracking_pick):
            await loop.run_daily_routine(time_warp=True)

        # All iterations should have used "hunt_dry" since no repos were scanned
        assert all(d == "hunt_dry" for d in delays_used), \
            f"Expected all hunt_dry delays, got {delays_used}"

    @pytest.mark.asyncio
    @patch("random.random", return_value=0.1)
    async def test_productive_hunt_uses_normal_delay(self, mock_random, loop, mock_pipeline):
        """When _do_hunt returns repos scanned, delay should use normal hunt."""
        loop._new_day_check()
        loop._daily_pr_target = 99
        delays_used = []

        async def productive_hunt(*a, **kw):
            return 0, 3  # 0 PRs but 3 repos scanned

        original_pick = loop._pick_delay

        def tracking_pick(action, tw):
            delays_used.append(action)
            return original_pick(action, tw)

        with patch.object(loop, "_do_hunt", side_effect=productive_hunt), \
             patch.object(loop, "_pick_delay", side_effect=tracking_pick):
            await loop.run_daily_routine(time_warp=True)

        # All iterations should have used "hunt" since repos were scanned
        assert all(d == "hunt" for d in delays_used), \
            f"Expected all hunt delays, got {delays_used}"
