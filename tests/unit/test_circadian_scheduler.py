"""Unit tests for Circadian Rhythm and Scheduler in human.py."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from farm_agent.orchestrator.human import is_within_circadian_hours


def test_circadian_working_hours_weekday():
    # Wednesday 10:00 AM UTC (17:00 in UTC+7) -> Working hour
    wednesday_10am_utc = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    config = MagicMock()
    config.bounty.circadian_enabled = True
    config.bounty.default_timezone_offset = 7
    config.bounty.work_hours_start = 8
    config.bounty.work_hours_end = 19
    config.bounty.weekend_quiet_mode = True

    assert is_within_circadian_hours(config, target_now=wednesday_10am_utc) is True


def test_circadian_night_hours_weekday():
    # Wednesday 17:00 PM UTC (24:00 in UTC+7) -> Sleeping hour
    wednesday_17pm_utc = datetime(2026, 9, 16, 17, 0, 0, tzinfo=timezone.utc)
    config = MagicMock()
    config.bounty.circadian_enabled = True
    config.bounty.default_timezone_offset = 7
    config.bounty.work_hours_start = 8
    config.bounty.work_hours_end = 19
    config.bounty.weekend_quiet_mode = True

    assert is_within_circadian_hours(config, target_now=wednesday_17pm_utc) is False


def test_circadian_weekend_quiet_mode():
    # Saturday 10:00 AM UTC+7
    saturday_utc = datetime(2026, 9, 19, 3, 0, 0, tzinfo=timezone.utc)
    config = MagicMock()
    config.bounty.circadian_enabled = True
    config.bounty.default_timezone_offset = 7
    config.bounty.work_hours_start = 8
    config.bounty.work_hours_end = 19
    config.bounty.weekend_quiet_mode = True

    # Even during daytime hours, weekend is quiet
    assert is_within_circadian_hours(config, target_now=saturday_utc) is False


def test_circadian_disabled_always_true():
    config = MagicMock()
    config.bounty.circadian_enabled = False

    saturday_midnight_utc = datetime(2026, 9, 19, 17, 0, 0, tzinfo=timezone.utc)
    assert is_within_circadian_hours(config, target_now=saturday_midnight_utc) is True
