"""utils/core/time_utils.py —— 时间格式化、星期判定、刷新点跨越判定。"""

import datetime

import pytest

import utils.core.time_utils as time_utils_module
from utils.config.config import ConfigurationManager
from utils.core.time_utils import CROSS_DAY_GRACE, TimeUtils


@pytest.fixture
def time_mgr(make_instance):
    return make_instance(TimeUtils, cfg=ConfigurationManager())


class TestFormatTime:
    def test_seconds_only(self):
        assert TimeUtils.format_time(9.5) == "9.5秒"

    def test_zero(self):
        assert TimeUtils.format_time(0) == "0.0秒"

    def test_minutes(self):
        assert TimeUtils.format_time(61.5) == "1分1.5秒"

    def test_hours(self):
        assert TimeUtils.format_time(3661) == "1小时1分1.0秒"

    def test_exactly_one_minute(self):
        assert TimeUtils.format_time(60) == "1分0.0秒"


class TestDayInit:
    def test_today_is_in_list(self):
        today = datetime.datetime.now().weekday()
        assert TimeUtils.day_init([today]) is True

    def test_today_is_not_in_list(self):
        today = datetime.datetime.now().weekday()
        assert TimeUtils.day_init([(today + 1) % 7]) is False

    def test_none_means_no_day(self):
        assert TimeUtils.day_init() is False

    def test_empty_list_means_no_day(self):
        assert TimeUtils.day_init([]) is False


class TestGetTargetDatetime:
    def test_uses_today(self):
        target = TimeUtils.get_target_datetime(4, 30, 15)
        assert target.date() == datetime.date.today()
        assert (target.hour, target.minute, target.second) == (4, 30, 15)


class TestHasCrossedRefresh:
    """refresh_hour / refresh_minute 来自 config，默认 4:00。

    判定的是「start 之后的第一个刷新点是否落在 end 之内」。
    """

    def test_crossing_within_same_day(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 3, 0)
        end = datetime.datetime(2026, 1, 1, 5, 0)
        assert time_mgr.has_crossed_refresh(start, end) is True

    def test_no_crossing_when_both_after_refresh(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 1, 6, 0)
        assert time_mgr.has_crossed_refresh(start, end) is False

    def test_no_crossing_when_both_before_refresh(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 1, 0)
        end = datetime.datetime(2026, 1, 1, 3, 0)
        assert time_mgr.has_crossed_refresh(start, end) is False

    def test_crossing_into_next_day(self, time_mgr):
        """跨日连锄：今天 5 点跑到明天 4:30，期间跨过明天 4:00 的刷新点。"""
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 2, 4, 30)
        assert time_mgr.has_crossed_refresh(start, end) is True

    def test_refresh_point_is_exclusive_of_start(self, time_mgr):
        """恰好从刷新点开始不算“跨过”。"""
        start = datetime.datetime(2026, 1, 1, 4, 0)
        end = datetime.datetime(2026, 1, 1, 6, 0)
        assert time_mgr.has_crossed_refresh(start, end) is False

    def test_refresh_point_is_inclusive_of_end(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 3, 0)
        end = datetime.datetime(2026, 1, 1, 4, 0)
        assert time_mgr.has_crossed_refresh(start, end) is True

    def test_uses_refresh_hour_from_config(self, time_mgr, set_config):
        set_config(time_mgr.cfg, refresh_hour=6, refresh_minute=0)
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 1, 7, 0)
        assert time_mgr.has_crossed_refresh(start, end) is True

    def test_non_zero_refresh_minute_with_start_minute_above_it(self, time_mgr, set_config):
        """refresh_minute=30，开始时间 5:40。"""
        set_config(time_mgr.cfg, refresh_hour=4, refresh_minute=30)
        start = datetime.datetime(2026, 1, 1, 5, 40)
        end = datetime.datetime(2026, 1, 2, 4, 35)
        assert time_mgr.has_crossed_refresh(start, end) is True

    def test_non_zero_refresh_minute_with_start_minute_below_it(self, time_mgr, set_config):
        """refresh_minute=30，开始时间 5:10，跑到次日 4:35 应判定为跨过 4:30。

        旧写法 `start.hour >= rh and start.minute >= rm` 在这一支会漏判。
        当年那条 xfail 的 reason 写「`and` 应为 `or`」是错的：`or` 会让条件恒真。
        """
        set_config(time_mgr.cfg, refresh_hour=4, refresh_minute=30)
        start = datetime.datetime(2026, 1, 1, 5, 10)
        end = datetime.datetime(2026, 1, 2, 4, 35)
        assert time_mgr.has_crossed_refresh(start, end) is True


class TestNextRefreshAfter:
    """next_refresh_after：moment 之后的第一个刷新时刻（严格晚于 moment）。"""

    def test_returns_today_when_refresh_still_ahead(self):
        moment = datetime.datetime(2026, 1, 1, 3, 0)
        assert TimeUtils.next_refresh_after(moment, 4, 0) == datetime.datetime(2026, 1, 1, 4, 0)

    def test_rolls_to_tomorrow_when_refresh_already_passed(self):
        moment = datetime.datetime(2026, 1, 1, 5, 0)
        assert TimeUtils.next_refresh_after(moment, 4, 0) == datetime.datetime(2026, 1, 2, 4, 0)

    def test_starting_exactly_on_the_refresh_point_rolls_to_tomorrow(self):
        """严格晚于 moment，所以踩点开始取次日。"""
        moment = datetime.datetime(2026, 1, 1, 4, 0)
        assert TimeUtils.next_refresh_after(moment, 4, 0) == datetime.datetime(2026, 1, 2, 4, 0)

    def test_hour_past_but_minute_before_refresh_rolls_to_tomorrow(self):
        """h > rh 但 m < rm 时必须取次日 —— 旧的 `and` 判定会错成当天。"""
        moment = datetime.datetime(2026, 1, 1, 5, 10)
        assert TimeUtils.next_refresh_after(moment, 4, 30) == datetime.datetime(2026, 1, 2, 4, 30)

    def test_minute_past_but_hour_before_refresh_stays_today(self):
        """m >= rm 但 h < rh 时仍取当天 —— 把 `and` 改成 `or` 会错成次日。"""
        moment = datetime.datetime(2026, 1, 1, 3, 45)
        assert TimeUtils.next_refresh_after(moment, 4, 30) == datetime.datetime(2026, 1, 1, 4, 30)


class TestCrossDayWait:
    """跨日连锄的等待时长。纯计算：不读 config、不看真实时钟。"""

    def test_waits_until_the_next_refresh(self):
        now = datetime.datetime(2026, 1, 1, 3, 0)
        # 刷新点 04:00，等 1 小时，另加一分钟余量
        assert TimeUtils.cross_day_wait(now, 4, 0) == 3600 + CROSS_DAY_GRACE

    def test_gives_up_when_the_wait_exceeds_the_cap(self):
        now = datetime.datetime(2026, 1, 1, 5, 0)
        # 当天 04:00 已过，下一个是次日 04:00 —— 23 小时，远超 4 小时上限
        assert TimeUtils.cross_day_wait(now, 4, 0) is None

    def test_exactly_at_the_cap_still_waits(self):
        now = datetime.datetime(2026, 1, 1, 0, 0)
        # 00:00 起算，下一个刷新点是次日 00:00，正好 24 小时
        exact = 24 * 3600 + CROSS_DAY_GRACE
        assert TimeUtils.cross_day_wait(now, 0, 0, max_wait=exact) == exact
        assert TimeUtils.cross_day_wait(now, 0, 0, max_wait=exact - 1) is None


class TestGetValidHour:
    """get_valid_hour 直接读 stdin。"""

    def test_valid_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a, **k: "7")
        assert TimeUtils.get_valid_hour() == 7

    def test_empty_input_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")
        assert TimeUtils.get_valid_hour() == 4

    def test_non_numeric_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a, **k: "abc")
        assert TimeUtils.get_valid_hour() == 4

    def test_out_of_range_asks_again(self, monkeypatch):
        answers = iter(["99", "-1", "5"])
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
        assert TimeUtils.get_valid_hour() == 5

    @pytest.mark.xfail(
        strict=True,
        reason="WebUI 以 stdin=subprocess.DEVNULL 启动子进程，input() 会抛 EOFError，"
        "应回退默认值而不是把异常抛给调用方（见 window.py 里同类问题的修复）",
    )
    def test_eof_falls_back_to_default(self, monkeypatch):
        def raise_eof(*args, **kwargs):
            raise EOFError("stdin 已关闭")

        monkeypatch.setattr("builtins.input", raise_eof)
        assert TimeUtils.get_valid_hour() == 4


class TestWaitAndRun:
    def test_sleeps_once_for_computed_delta(self, monkeypatch):
        slept = []
        monkeypatch.setattr(TimeUtils, "get_valid_hour", staticmethod(lambda: 4))
        monkeypatch.setattr(
            time_utils_module.time, "sleep", lambda seconds: slept.append(seconds)
        )

        TimeUtils.wait_and_run(minute=1, second=0)

        assert len(slept) == 1
        assert slept[0] >= 0

    def test_rolls_over_to_next_day_when_target_passed(self, monkeypatch):
        """目标时间已过时应顺延到明天：等 23 小时而不是立刻返回。"""
        slept = []
        monkeypatch.setattr(TimeUtils, "get_valid_hour", staticmethod(lambda: 4))
        past = datetime.datetime.now() - datetime.timedelta(hours=1)
        monkeypatch.setattr(
            TimeUtils, "get_target_datetime", staticmethod(lambda h, m, s: past)
        )
        monkeypatch.setattr(
            time_utils_module.time, "sleep", lambda seconds: slept.append(seconds)
        )

        TimeUtils.wait_and_run(minute=0, second=0)

        assert len(slept) == 1
        assert slept[0] == pytest.approx(23 * 3600, abs=5)
