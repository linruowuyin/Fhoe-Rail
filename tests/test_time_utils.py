"""utils/core/time_utils.py —— 时间格式化、星期判定、刷新点跨越判定。"""

import datetime

import pytest

import utils.core.time_utils as time_utils_module
from utils.config.config import ConfigurationManager
from utils.core.time_utils import TimeUtils


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


class TestHasCrossed4am:
    """refresh_hour / refresh_minute 来自 config，默认 4:00。"""

    def test_crossing_within_same_day(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 3, 0)
        end = datetime.datetime(2026, 1, 1, 5, 0)
        assert time_mgr.has_crossed_4am(start, end) is True

    def test_no_crossing_when_both_after_refresh(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 1, 6, 0)
        assert time_mgr.has_crossed_4am(start, end) is False

    def test_no_crossing_when_both_before_refresh(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 1, 0)
        end = datetime.datetime(2026, 1, 1, 3, 0)
        assert time_mgr.has_crossed_4am(start, end) is False

    def test_crossing_into_next_day(self, time_mgr):
        """跨日连锄：今天 5 点跑到明天 4:30，期间跨过明天 4:00 的刷新点。"""
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 2, 4, 30)
        assert time_mgr.has_crossed_4am(start, end) is True

    def test_refresh_point_is_exclusive_of_start(self, time_mgr):
        """恰好从刷新点开始不算“跨过”。"""
        start = datetime.datetime(2026, 1, 1, 4, 0)
        end = datetime.datetime(2026, 1, 1, 6, 0)
        assert time_mgr.has_crossed_4am(start, end) is False

    def test_refresh_point_is_inclusive_of_end(self, time_mgr):
        start = datetime.datetime(2026, 1, 1, 3, 0)
        end = datetime.datetime(2026, 1, 1, 4, 0)
        assert time_mgr.has_crossed_4am(start, end) is True

    def test_uses_refresh_hour_from_config(self, time_mgr, set_config):
        set_config(time_mgr.cfg, refresh_hour=6, refresh_minute=0)
        start = datetime.datetime(2026, 1, 1, 5, 0)
        end = datetime.datetime(2026, 1, 1, 7, 0)
        assert time_mgr.has_crossed_4am(start, end) is True

    def test_non_zero_refresh_minute_with_start_minute_above_it(self, time_mgr, set_config):
        """refresh_minute=30，开始时间 5:40 —— 这一支恰好是对的。"""
        set_config(time_mgr.cfg, refresh_hour=4, refresh_minute=30)
        start = datetime.datetime(2026, 1, 1, 5, 40)
        end = datetime.datetime(2026, 1, 2, 4, 35)
        assert time_mgr.has_crossed_4am(start, end) is True

    @pytest.mark.xfail(
        strict=True,
        reason="refresh_minute 非 0 且 start.minute < refresh_minute 时，"
        "第 96 行的 `and` 应为 `or`，导致漏判跨刷新点",
    )
    def test_non_zero_refresh_minute_with_start_minute_below_it(self, time_mgr, set_config):
        """refresh_minute=30，开始时间 5:10，跑到次日 4:35 应判定为跨过 4:30。"""
        set_config(time_mgr.cfg, refresh_hour=4, refresh_minute=30)
        start = datetime.datetime(2026, 1, 1, 5, 10)
        end = datetime.datetime(2026, 1, 2, 4, 35)
        assert time_mgr.has_crossed_4am(start, end) is True


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
