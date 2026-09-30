"""fhoe.py 的两件事：启动模式分发（`_start_for_mode`）与编排顺序（`run_once`）。

两者都是从 `main()` 抽出来的：`main()` 一跑就会切窗口、启动游戏，单测驱动不了。
抽出来之后，窗口 / 地图流程 / 时钟 / 关机都成了参数，测试传替身进来就能断言**顺序** ——
这正是「关机曾经排在跨日连锄之前」那类 bug 唯一能被钉住的地方。
"""

import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeCfg:
    CONFIG_FILE_NAME = "config.json"

    def __init__(self, **flags):
        self.flags = flags
        self.calls = []

    def main_start(self):
        self.calls.append("main_start")

    def main_start_rewrite(self, setting):
        self.calls.append(("main_start_rewrite", setting))

    def config_fix(self):
        self.calls.append("config_fix")

    def modify_json_file(self, filename, key, value):
        self.calls.append(("modify_json_file", key, value))

    def load_config(self):
        return dict(self.flags)

    def read_json_file(self, filename, path=False):
        return dict(self.flags)

    @property
    def config_file(self):
        return dict(self.flags)


class FakeTimeMgr:
    def __init__(self, crossed=False, next_in_seconds=3600):
        self.crossed = crossed
        self.next_in_seconds = next_in_seconds

    def has_crossed_refresh(self, start, end):
        return self.crossed

    def next_refresh_after(self, moment, hour, minute):
        return moment + datetime.timedelta(seconds=self.next_in_seconds)


class FakeClock:
    def __init__(self, order):
        self.order = order

    def now(self):
        return datetime.datetime(2026, 1, 1, 3, 0)

    def sleep(self, seconds):
        self.order.append(("sleep", seconds))


class FakeNotify:
    def __init__(self, order):
        self.order = order

    def send_start(self, start):
        self.order.append("send_start")

    def send_end(self, summary):
        self.order.append("send_end")


class FakeWindow:
    def __init__(self, order):
        self.order = order

    def switch_window(self):
        self.order.append("switch_window")


class FakeMapOps:
    def __init__(self, order):
        self.order = order
        self.handle = SimpleNamespace(
            back_to_main=lambda delay=2.0: self.order.append("back_to_main"),
            total_fight_cnt=0,
            total_no_fight_cnt=0,
            tatol_save_time=0,
            time_error_cnt=0,
        )
        self.map_statu = SimpleNamespace(total_time=1.0)

    def process_map(self, start, start_in_mid, dev=False, single_map=False):
        self.order.append(("process_map", start))


@pytest.fixture
def fhoe_mod(tmp_path, monkeypatch):
    """导入 fhoe。

    fhoe 在**模块级**就构造 `Setting()`，而它会读 `map/` —— 临时目录里没有就会
    FileNotFoundError。所以先摆一个只含空版本目录的 map/：`read_maps_versions()`
    只 listdir 取版本名，不读内容。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "map" / "default").mkdir(parents=True)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "version.txt").write_text("test", encoding="utf-8")
    import fhoe

    return fhoe


def _run(fhoe_mod, *, flags=None, crossed=False, next_in_seconds=3600,
         start="3-5_1", single_map_mode=False):
    """跑一趟 run_once，返回按发生顺序记录的事件表。"""
    order = []
    fhoe_mod.run_once(
        start,
        False,
        single_map_mode=single_map_mode,
        cfg=FakeCfg(**(flags or {})),
        time_mgr=FakeTimeMgr(crossed, next_in_seconds),
        notify=FakeNotify(order),
        clock=FakeClock(order),
        window_factory=lambda: FakeWindow(order),
        map_ops_factory=lambda: FakeMapOps(order),
        check_screens=lambda: order.append("check_screens"),
        shutdown=lambda shutdown_type: order.append(("shutdown", shutdown_type)),
    )
    return order


class TestShutdownOrdering:
    """回归：关机/注销曾经排在跨日连锄之前。"""

    def test_shutdown_comes_after_the_cross_day_wait(self, fhoe_mod):
        order = _run(
            fhoe_mod,
            flags={"allow_run_next_day": True, "auto_shutdown": 1},
            crossed=False,
            next_in_seconds=3600,  # wait_time = 3660 <= 14400，会真的等
        )
        assert ("sleep", 3660) in order, "应该走了等待分支"
        assert order.index("back_to_main") < order.index(("shutdown", 1))
        assert order.index(("sleep", 3660)) < order.index(("shutdown", 1)), (
            "关机排在跨日等待之前的话，10 秒后机器就没了，最长 4 小时的等待永远走不完"
        )
        # 等完还要再锄一趟，然后才关机
        assert order.index(("process_map", "1-1_0")) < order.index(("shutdown", 1))

    def test_shutdown_comes_after_running_again_when_the_refresh_was_crossed(self, fhoe_mod):
        order = _run(
            fhoe_mod,
            flags={"allow_run_next_day": True, "auto_shutdown": 1},
            crossed=True,
        )
        assert ("sleep", 3660) not in order, "已跨过刷新点就不该再等"
        assert order.index(("process_map", "1-1_0")) < order.index(("shutdown", 1))

    def test_long_wait_skips_the_extra_run_but_still_shuts_down(self, fhoe_mod):
        order = _run(
            fhoe_mod,
            flags={"allow_run_next_day": True, "auto_shutdown": 2},
            crossed=False,
            next_in_seconds=20000,  # wait_time = 20060 > 14400
        )
        assert ("sleep", 20060) not in order
        assert ("process_map", "1-1_0") not in order
        assert ("shutdown", 2) in order, "等待过久只是不连锄，关机照旧"


class TestCrossDayBranching:
    def test_no_wait_or_rerun_when_cross_day_is_disabled(self, fhoe_mod):
        order = _run(fhoe_mod, flags={"allow_run_next_day": False})
        assert ("sleep", 3660) not in order
        assert "back_to_main" not in order
        assert ("process_map", "1-1_0") not in order

    def test_single_map_mode_skips_everything_after_the_first_route(self, fhoe_mod):
        order = _run(
            fhoe_mod,
            flags={"allow_run_next_day": True, "allow_run_again": True, "auto_shutdown": 1},
            start="3-5_1",
            single_map_mode=True,
        )
        runs = [e for e in order if isinstance(e, tuple) and e[0] == "process_map"]
        assert runs == [("process_map", "3-5_1")], "单图模式只跑指定的那一张"


class TestRunOnceBasics:
    def test_window_is_switched_before_mapping(self, fhoe_mod):
        order = _run(fhoe_mod)
        assert order.index("check_screens") < order.index("switch_window")
        assert order.index("switch_window") < order.index(("process_map", "3-5_1"))
        assert order.index("send_start") < order.index(("process_map", "3-5_1"))
        assert order.index("send_end") > order.index(("process_map", "3-5_1"))

    def test_auto_shutdown_zero_still_calls_the_hook(self, fhoe_mod):
        """关不关由 shutdown_computer 自己按类型判断，编排层不做二次判断。"""
        order = _run(fhoe_mod, flags={"auto_shutdown": 0})
        assert ("shutdown", 0) in order


def _dispatch(fhoe_mod, monkeypatch, mode, map_arg=None):
    """跑一次 _start_for_mode，把协作对象全换掉。"""
    fake_cfg = FakeCfg()
    switched = []
    recorded = []

    monkeypatch.setattr(fhoe_mod, "cfg", fake_cfg)
    monkeypatch.setattr(fhoe_mod, "setting", "FAKE_SETTING")
    monkeypatch.setattr(fhoe_mod, "choose_map", lambda info: ("CONFIGURED", True))
    monkeypatch.setattr(fhoe_mod, "choose_map_debug", lambda info: ("MENU", True))

    class FakeSwitchWindow:
        def switch_window(self):
            switched.append(True)

    monkeypatch.setattr(fhoe_mod, "Window", FakeSwitchWindow)
    # 用假模块顶掉 utils.ui.record，避免为了测 --record 真去 import 它
    monkeypatch.setitem(
        sys.modules,
        "utils.ui.record",
        SimpleNamespace(record_main=lambda: recorded.append("record")),
    )

    start, dev = fhoe_mod._start_for_mode(mode, map_arg)
    return SimpleNamespace(
        start=start, dev=dev, cfg=fake_cfg, switched=switched, recorded=recorded
    )


class TestStartForMode:
    """启动模式矩阵。把原先那串 if-elif 抽成函数，就是为了能这样一条条钉住。"""

    def test_record_mode_does_not_produce_a_start(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--record")
        assert r.start is fhoe_mod._MODE_DONE
        assert r.recorded == ["record"]
        assert r.cfg.calls == [], "录制模式不该去动配置"

    def test_test_mode_only_switches_the_window(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--test")
        assert r.start is fhoe_mod._MODE_DONE
        assert r.switched == [True]
        assert r.cfg.calls == ["main_start"]

    def test_config_mode_rewrites_then_uses_the_debug_menu(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--config")
        assert r.start == ("MENU", True)
        assert r.dev is False
        assert r.cfg.calls == [("main_start_rewrite", "FAKE_SETTING")]

    def test_white_mode_arms_the_one_shot_allowlist(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--white")
        assert r.start == ("CONFIGURED", True)
        assert ("modify_json_file", "allowlist_mode_once", True) in r.cfg.calls

    def test_dev_mode_uses_the_menu_and_marks_dev(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--dev")
        assert r.start == ("MENU", True)
        assert r.dev is True

    def test_debug_mode_with_a_map_argument_skips_the_menu(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--debug", map_arg="3-5_1")
        assert r.start == ("3-5_1", False)
        assert r.dev is False

    def test_map_mode_uses_the_given_map(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--map", map_arg="3-5_1")
        assert r.start == ("3-5_1", False)
        assert r.dev is False

    def test_no_mode_uses_the_configured_start(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "")
        assert r.start == ("CONFIGURED", True)
        assert r.dev is False
        assert r.cfg.calls == ["main_start"]

    def test_unknown_mode_behaves_like_no_mode(self, fhoe_mod, monkeypatch):
        r = _dispatch(fhoe_mod, monkeypatch, "--并不存在")
        assert r.start == ("CONFIGURED", True)
        assert r.dev is False
