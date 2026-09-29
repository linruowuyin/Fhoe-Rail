"""utils/flows/monthly_pass.py —— 月卡检查的时间计算与节流判定。"""

from datetime import datetime, timedelta

import pytest

from utils.config.config import ConfigurationManager
from utils.flows.monthly_pass import MonthlyPass


@pytest.fixture
def monthly(make_instance, isolated_cwd):
    return make_instance(
        MonthlyPass,
        cfg=ConfigurationManager(),
        refresh_hour=4,
        refresh_minute=0,
        next_check_time=None,
        last_check_time=None,
    )


class TestStatus:
    def test_constants_are_distinct(self):
        statuses = {
            MonthlyPass.Status.CLAIMED,
            MonthlyPass.Status.NO_PASS,
            MonthlyPass.Status.NOT_FOUND,
        }
        assert len(statuses) == 3


class TestCalculateNextCheck:
    def test_before_refresh_returns_same_day(self):
        base = datetime(2026, 1, 1, 3, 0)
        assert MonthlyPass._calculate_next_check(base, 4, 0) == datetime(2026, 1, 1, 4, 0)

    def test_after_refresh_returns_next_day(self):
        base = datetime(2026, 1, 1, 5, 0)
        assert MonthlyPass._calculate_next_check(base, 4, 0) == datetime(2026, 1, 2, 4, 0)

    def test_exactly_at_refresh_rolls_to_next_day(self):
        """比较是严格的 >，所以正好等于刷新点也算“已过”。"""
        base = datetime(2026, 1, 1, 4, 0)
        assert MonthlyPass._calculate_next_check(base, 4, 0) == datetime(2026, 1, 2, 4, 0)

    def test_respects_non_zero_minute(self):
        base = datetime(2026, 1, 1, 4, 0)
        assert MonthlyPass._calculate_next_check(base, 4, 30) == datetime(2026, 1, 1, 4, 30)

    def test_microseconds_are_dropped(self):
        base = datetime(2026, 1, 1, 3, 59, 59, 999999)
        assert MonthlyPass._calculate_next_check(base, 4, 0).microsecond == 0


class TestNeedWaitBeforeCheck:
    def test_waits_when_refresh_is_imminent(self, monthly):
        assert monthly._need_wait_before_check(datetime(2026, 1, 1, 3, 58)) is True

    def test_does_not_wait_when_refresh_is_far(self, monthly):
        assert monthly._need_wait_before_check(datetime(2026, 1, 1, 3, 0)) is False

    def test_does_not_wait_once_refresh_has_passed(self, monthly):
        assert monthly._need_wait_before_check(datetime(2026, 1, 1, 5, 0)) is False

    def test_boundary_at_wait_interval_is_not_imminent(self, monthly):
        """剩余正好等于等待间隔时不算“临近”（比较是严格的 <）。"""
        assert monthly._need_wait_before_check(datetime(2026, 1, 1, 3, 55)) is False

    def test_just_inside_the_interval_waits(self, monthly):
        assert monthly._need_wait_before_check(datetime(2026, 1, 1, 3, 55, 1)) is True


class TestShouldPerformCheck:
    def test_first_run_always_checks(self, monthly):
        monthly.monthly_update_check_time()
        assert monthly._should_perform_check(datetime(2026, 1, 1, 12, 0)) is True

    def test_waits_until_next_check_time(self, monthly):
        monthly.last_check_time = datetime(2026, 1, 1, 4, 0)
        monthly.next_check_time = datetime(2026, 1, 2, 4, 0)
        assert monthly._should_perform_check(datetime(2026, 1, 1, 12, 0)) is False

    def test_checks_once_next_check_time_reached(self, monthly):
        monthly.last_check_time = datetime(2026, 1, 1, 4, 0)
        monthly.next_check_time = datetime(2026, 1, 2, 4, 0)
        assert monthly._should_perform_check(datetime(2026, 1, 2, 4, 1)) is True

    def test_initialises_next_check_time_when_missing(self, monthly):
        monthly._should_perform_check(datetime(2026, 1, 1, 12, 0))
        assert monthly.next_check_time is not None


class TestUpdateCheckTimestamps:
    def test_records_last_check(self, monthly):
        now = datetime(2026, 1, 1, 4, 0, 30)
        monthly._update_check_timestamps(now)
        assert monthly.last_check_time == now

    def test_advances_next_check_to_the_configured_refresh_point(self, monthly):
        monthly._update_check_timestamps(datetime(2026, 1, 1, 4, 0, 30))
        assert (monthly.next_check_time.hour, monthly.next_check_time.minute) == (4, 0)
        assert monthly.next_check_time > datetime.now()


class TestRefreshConfig:
    def test_update_check_time_uses_instance_refresh_point(self, monthly):
        """monthly_update_check_time 读的是实例属性，不查配置。"""
        monthly.refresh_hour = 6
        monthly.refresh_minute = 15

        monthly.monthly_update_check_time()

        assert (monthly.next_check_time.hour, monthly.next_check_time.minute) == (6, 15)

    def test_check_reloads_refresh_values_from_config(self, monthly, set_config):
        """配置里的刷新时间只有走 monthly_pass_check 才会同步到实例上。"""
        set_config(monthly.cfg, refresh_hour=9, refresh_minute=45)
        monthly._execute_check_flow = lambda current: None
        monthly.next_check_time = datetime.now() + timedelta(days=1)

        monthly.monthly_pass_check()

        assert (monthly.refresh_hour, monthly.refresh_minute) == (9, 45)
