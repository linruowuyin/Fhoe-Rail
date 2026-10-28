"""utils/flows/monthly_pass.py —— 月卡检查的时间计算、节流判定与领取流程。"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from utils.config.config import ConfigurationManager
from utils.core.thresholds import MONTHLY_PASS
from utils.flows.monthly_pass import MonthlyPass


@pytest.fixture
def monthly(make_instance, isolated_cwd):
    return make_instance(
        MonthlyPass,
        cfg=ConfigurationManager(),
        pass_pictures=MonthlyPass.PASS_PICTURES,
        pass_threshold=MONTHLY_PASS,
        refresh_hour=4,
        refresh_minute=0,
        next_check_time=None,
        last_check_time=None,
        monthly_pass_status=None,
        have_monthly_pass=False,
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


class ScriptedScreen:
    """按队列回答识图的 img 替身。队列空了直接报错，免得循环静默多转。"""

    def __init__(self, scans):
        self.scans = list(scans)
        self.scan_calls = 0

    def scan_screenshot(self, target, *args, **kwargs):
        self.scan_calls += 1
        assert self.scans, "scan_screenshot 调用次数超出脚本"
        return self.scans.pop(0)

    def img_center_point(self, result, shape):
        return (10, 20)


@pytest.fixture
def screen(monthly, monkeypatch):
    """把取图与等待换成替身，返回记录器。"""
    import utils.flows.monthly_pass as monthly_module

    rec = type("Rec", (), {})()
    rec.slept, rec.clicks, rec.relative = [], [], []
    monkeypatch.setattr(
        monthly_module.Img,
        "get_img",
        staticmethod(lambda path: type("I", (), {"path": path, "shape": (4, 4, 3)})()),
    )
    # 换掉模块里的 time，不要去打 stdlib 的 time.sleep —— 那会波及整个进程
    monkeypatch.setattr(monthly_module, "time", SimpleNamespace(sleep=rec.slept.append))
    monthly.mouse_event = type(
        "Mouse",
        (),
        {
            "click": lambda self, points: rec.clicks.append(points),
            "relative_click": lambda self, offset: rec.relative.append(offset),
        },
    )()
    return rec


class TestCheckForMonthlyPass:
    def test_reports_no_pass_when_the_main_ui_shows(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.99}])

        assert monthly.check_for_monthly_pass() is False
        assert monthly.monthly_pass_status == MonthlyPass.Status.NO_PASS

    def test_passes_through_when_we_are_not_on_the_main_ui(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.5}])

        assert monthly.check_for_monthly_pass() is True
        assert monthly.monthly_pass_status is None, "这一步不下结论"


class TestConfirmRewardClaim:
    def test_clicks_as_soon_as_the_reward_icon_shows(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.99}])

        monthly._confirm_reward_claim()

        assert screen.relative == [(50, 75)]
        assert monthly.have_monthly_pass is True
        assert monthly.monthly_pass_status == MonthlyPass.Status.CLAIMED

    def test_falls_back_after_five_misses(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.0}] * 5)

        monthly._confirm_reward_claim()

        assert screen.relative == [(50, 75)], "五轮都没认出来也要点一下收尾"
        assert monthly.have_monthly_pass is True


class TestTryClickPass:
    def test_stops_when_there_is_no_monthly_pass(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.99}])

        monthly.try_click_pass()

        assert screen.clicks == []
        assert monthly.monthly_pass_status == MonthlyPass.Status.NO_PASS

    def test_clicks_the_first_matching_picture_then_confirms(self, monthly, screen):
        monthly.img = ScriptedScreen(
            [
                {"max_val": 0.5},  # 有月卡
                {"max_val": 0.99},  # 第一张月卡图命中
                {"max_val": 0.99},  # 领取确认
            ]
        )

        monthly.try_click_pass()

        assert screen.clicks == [(10, 20)]
        assert monthly.have_monthly_pass is True
        assert monthly.monthly_pass_status == MonthlyPass.Status.CLAIMED

    def test_marks_not_found_when_no_picture_matches(self, monthly, screen):
        monthly.img = ScriptedScreen(
            [{"max_val": 0.5}, {"max_val": 0.1}, {"max_val": 0.1}]
        )

        monthly.try_click_pass()

        assert screen.clicks == []
        assert monthly.monthly_pass_status == MonthlyPass.Status.NOT_FOUND


class TestTryClaimIfVisible:
    """back_to_main 的兜底路径：只回答「这一帧是不是月卡界面、点了没有」。"""

    def test_returns_false_without_clicking_when_not_the_pass_screen(
        self, monthly, screen
    ):
        monthly.img = ScriptedScreen([{"max_val": 0.1}, {"max_val": 0.2}])

        assert monthly.try_claim_if_visible() is False
        assert screen.clicks == []
        assert monthly.have_monthly_pass is False
        assert monthly.monthly_pass_status is None, "兜底路径不下结论"

    def test_claims_when_the_title_picture_matches(self, monthly, screen):
        monthly.img = ScriptedScreen([{"max_val": 0.99}, {"max_val": 0.99}])

        assert monthly.try_claim_if_visible() is True
        assert screen.clicks == [(10, 20)]
        assert screen.relative == [(50, 75)]
        assert monthly.have_monthly_pass is True
        assert monthly.monthly_pass_status == MonthlyPass.Status.CLAIMED

    def test_claims_when_only_the_card_picture_matches(self, monthly, screen):
        monthly.img = ScriptedScreen(
            [{"max_val": 0.5}, {"max_val": 0.99}, {"max_val": 0.99}]
        )

        assert monthly.try_claim_if_visible() is True
        assert screen.clicks == [(10, 20)]

    def test_injected_picture_and_threshold_are_used(self, monthly, screen):
        """手动流程测试入口用 setting_icon 这类好触发的图替换月卡图。"""
        monthly.pass_pictures = (("setting_icon", "流程测试图"),)
        monthly.pass_threshold = 0.80
        monthly.img = ScriptedScreen([{"max_val": 0.85}, {"max_val": 0.99}])

        assert monthly.try_claim_if_visible() is True, "0.85 在 0.80 阈值下应命中"
        assert screen.clicks == [(10, 20)]


class TestFrameMatching:
    """`pre_esc` 修复表用的一帧式识别：不自己截图、结果按帧内坐标返回。"""

    def test_match_frame_uses_the_same_frame_for_every_picture(
        self, monthly, screen, monkeypatch
    ):
        import utils.flows.monthly_pass as monthly_module

        frames = []

        def fake_match(frame, prepared, left, top, strategy=None):
            frames.append((frame, prepared.path))
            return {"max_val": 0.2 if len(frames) == 1 else 0.99}

        monkeypatch.setattr(
            monthly_module.Matcher, "match_screenshot", staticmethod(fake_match)
        )
        frame = object()

        match = monthly.match_frame(frame)

        assert [item[0] is frame for item in frames] == [True, True]
        assert match is not None
        assert match[2] == "月卡动画中心图片", "第一张没过阈值，第二张命中"

    def test_match_frame_returns_none_when_nothing_passes(self, monthly, screen, monkeypatch):
        import utils.flows.monthly_pass as monthly_module

        monkeypatch.setattr(
            monthly_module.Matcher,
            "match_screenshot",
            staticmethod(lambda *a, **k: {"max_val": 0.1}),
        )

        assert monthly.match_frame(object()) is None

    def test_claim_match_adds_the_frame_origin(self, monthly, screen):
        confirmed = []
        monthly._confirm_reward_claim = lambda: confirmed.append(1)
        monthly.img = ScriptedScreen([])
        pic_data = SimpleNamespace(shape=(4, 4, 3))

        monthly.claim_match(pic_data, {"max_val": 0.99}, "月卡", 100, 200)

        assert screen.clicks == [(110, 220)]
        assert screen.slept == [5]
        assert confirmed == [1]


class TestConstructorInjection:
    """`pass_pictures` / `pass_threshold` 可注入：生产默认值不变，测试入口换图。"""

    @pytest.fixture(autouse=True)
    def stub_singletons(self, monkeypatch):
        import utils.flows.monthly_pass as monthly_module

        monkeypatch.setattr(
            monthly_module,
            "ConfigurationManager",
            lambda: SimpleNamespace(config_file={}),
        )
        monkeypatch.setattr(monthly_module, "Img", lambda: SimpleNamespace())
        monkeypatch.setattr(monthly_module, "MouseEvent", lambda: SimpleNamespace())

    def test_constructor_keeps_injected_picture_and_threshold(self):
        import utils.flows.monthly_pass as monthly_module

        injected = monthly_module.MonthlyPass(
            pass_pictures=(("setting_icon", "流程测试图"),), pass_threshold=0.80
        )

        assert injected.pass_pictures == (("setting_icon", "流程测试图"),)
        assert injected.pass_threshold == 0.80

    def test_constructor_defaults_to_the_real_pass_pictures(self):
        import utils.flows.monthly_pass as monthly_module

        monthly = monthly_module.MonthlyPass()

        assert monthly.pass_pictures == MonthlyPass.PASS_PICTURES
        assert monthly.pass_threshold == MONTHLY_PASS


class TestExecuteCheckFlow:
    def test_waits_thirty_seconds_when_just_past_the_refresh_point(self, monthly, screen):
        calls = []
        monthly.try_click_pass = lambda **kwargs: calls.append(kwargs.get("delay", 0))
        monthly.next_check_time = datetime(2026, 1, 1, 4, 0)

        monthly._execute_check_flow(datetime(2026, 1, 1, 4, 0, 10))

        assert calls == [30], "刚过刷新点，先等一会儿再认"

    def test_does_not_wait_otherwise(self, monthly, screen):
        calls = []
        monthly.try_click_pass = lambda **kwargs: calls.append(kwargs.get("delay", 0))
        monthly.next_check_time = datetime(2026, 1, 1, 4, 0)

        monthly._execute_check_flow(datetime(2026, 1, 1, 4, 1))

        assert calls == [0]


class TestWaitUntilRefreshTime:
    def test_sleeps_until_the_target_moment(self, monthly, screen, monkeypatch):
        import utils.flows.monthly_pass as monthly_module

        target = datetime(2026, 1, 1, 4, 0)
        monthly.next_check_time = target
        # 两个 3:59：一个给「当前时间」那句日志，一个给 while 的第一次判断
        before = datetime(2026, 1, 1, 3, 59)
        ticks = iter([before, before])
        monkeypatch.setattr(
            monthly_module,
            "datetime",
            type("D", (), {"now": staticmethod(lambda: next(ticks, target))}),
        )

        monthly._wait_until_refresh_time()

        assert screen.slept == [2], "还没到就等两秒再看一次"


class TestMonthlyPassCheck:
    """主流程只做编排：等 / 查 / 记时间，三件事各由上面那些方法负责。"""

    def test_first_run_initialises_then_checks(self, monthly):
        events = []
        monthly.monthly_update_check_time = lambda: events.append("init")
        monthly._need_wait_before_check = lambda current: False
        monthly._should_perform_check = lambda current: True
        monthly._execute_check_flow = lambda current: events.append("check")
        monthly._update_check_timestamps = lambda current: events.append("stamp")

        monthly.monthly_pass_check()

        assert events == ["init", "check", "stamp"]

    def test_waits_first_when_the_refresh_point_is_imminent(self, monthly):
        events = []
        monthly.monthly_update_check_time = lambda: events.append("init")
        monthly._need_wait_before_check = lambda current: True
        monthly._wait_until_refresh_time = lambda: events.append("wait")
        monthly._should_perform_check = lambda current: False

        monthly.monthly_pass_check()

        assert events == ["init", "wait"], "等完之后没到该查的时间就不查"

    def test_does_nothing_between_checks(self, monthly):
        events = []
        monthly.monthly_update_check_time = lambda: events.append("init")
        monthly._need_wait_before_check = lambda current: False
        monthly._should_perform_check = lambda current: False

        monthly.monthly_pass_check()

        assert events == ["init"]
