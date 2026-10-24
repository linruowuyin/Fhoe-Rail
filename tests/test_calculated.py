"""utils/flows/calculated.py —— 关机、购买检测、1 号位识别、两个加载轮询。"""

from types import SimpleNamespace

import numpy as np
import pytest

import utils.flows.calculated as calculated_module
from utils.flows.calculated import Calculated
from utils.vision.img import Img


class ScriptedImg:
    """按队列回答查询的 img 替身。

    队列空了就报错 —— 否则「本该提前跳出」的用例会静默多转几圈，测试就失去意义了。
    """

    def __init__(self, scans=(), on_main=(), on_interface=()):
        self.queues = {
            "scan_screenshot": list(scans),
            "on_main_interface": list(on_main),
            "on_interface": list(on_interface),
        }
        self.calls = {name: 0 for name in self.queues}
        for name in (
            "main_ui",
            "finish2_ui",
            "finish2_1_ui",
            "finish2_2_ui",
            "finish3_ui",
            "finish5_ui",
        ):
            setattr(self, name, name)

    def _next(self, name):
        self.calls[name] += 1
        queue = self.queues[name]
        assert queue, f"{name} 被调用次数超出脚本"
        return queue.pop(0)

    def scan_screenshot(self, target, *args, **kwargs):
        return self._next("scan_screenshot")

    def on_main_interface(self, **kwargs):
        return self._next("on_main_interface")

    def on_interface(self, **kwargs):
        return self._next("on_interface")


class FakeBlackScreen:
    def __init__(self, answers=()):
        self.answers = list(answers)
        self.cal_time_calls = 0

    def check_blackscreen(self):
        assert self.answers, "check_blackscreen 被调用次数超出脚本"
        return self.answers.pop(0)

    def run_blackscreen_cal_time(self):
        self.cal_time_calls += 1


@pytest.fixture
def computed(make_instance, monkeypatch):
    """不真等待、不读图片文件的 Calculated。"""
    monkeypatch.setattr(
        calculated_module,
        "time",
        SimpleNamespace(time=lambda: 100.0, sleep=lambda seconds: None),
    )
    monkeypatch.setattr(
        calculated_module.Img, "get_img", staticmethod(lambda path: f"IMG:{path}")
    )
    return make_instance(Calculated)


def wire(computed, scans=(), on_main=(), on_interface=(), blackscreen=()):
    img = ScriptedImg(scans=scans, on_main=on_main, on_interface=on_interface)
    screens = FakeBlackScreen(blackscreen)
    computed.img = img
    computed.blackscreen = screens
    return img, screens


class TestHandleShutdown:
    def test_runs_shutdown_when_enabled(self, make_instance, monkeypatch):
        commands = []
        monkeypatch.setattr(
            calculated_module.os, "system", lambda cmd: commands.append(cmd)
        )
        computed = make_instance(
            Calculated, cfg=SimpleNamespace(config_file={"auto_shutdown": 1})
        )

        computed.handle_shutdown()

        assert commands == ["shutdown /s /f /t 0"]

    def test_does_nothing_when_disabled(self, make_instance, monkeypatch):
        commands = []
        monkeypatch.setattr(
            calculated_module.os, "system", lambda cmd: commands.append(cmd)
        )
        computed = make_instance(
            Calculated, cfg=SimpleNamespace(config_file={"auto_shutdown": 0})
        )

        computed.handle_shutdown()

        assert commands == []

    @pytest.mark.xfail(
        strict=True,
        reason="设置界面里 auto_shutdown 提供 0=无操作 / 1=关机 / 2=注销，"
        "但 handle_shutdown 只做真值判断，选了“注销”依然会执行关机命令",
    )
    def test_logoff_mode_does_not_shut_down(self, make_instance, monkeypatch):
        commands = []
        monkeypatch.setattr(
            calculated_module.os, "system", lambda cmd: commands.append(cmd)
        )
        computed = make_instance(
            Calculated, cfg=SimpleNamespace(config_file={"auto_shutdown": 2})
        )

        computed.handle_shutdown()

        assert commands != ["shutdown /s /f /t 0"]


class TestAllowBuyItem:
    @pytest.fixture(autouse=True)
    def stub_image(self, monkeypatch):
        monkeypatch.setattr(
            Img, "get_img", staticmethod(lambda path: np.zeros((4, 4, 3), np.uint8))
        )

    def test_false_when_purchase_disabled_dialog_visible(self, make_instance):
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(on_interface=lambda **kwargs: True)
        assert computed.allow_buy_item() is False

    def test_true_when_no_dialog(self, make_instance):
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(on_interface=lambda **kwargs: False)
        assert computed.allow_buy_item() is True


class TestFirstRoleCheck:
    @pytest.fixture(autouse=True)
    def stub_role_check(self, monkeypatch):
        """1 号位角色校验本身在 test_first_role.py 里测；这里只钉住调用参数。"""
        self.role_checks = []
        monkeypatch.setattr(
            calculated_module,
            "check_first_role",
            lambda map_version, img: self.role_checks.append(map_version),
        )

    def test_presses_1_when_slot_matches_colour_range(self, make_instance, monkeypatch):
        image = np.empty((20, 20, 3), dtype=np.uint8)
        image[:, :] = (255, 255, 155)  # RGB，经 RGB2HSV 落在 [28,49,253]-[32,189,255]
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(
            take_screenshot=lambda **kwargs: (image, 0, 0, 20, 20)
        )
        pressed = []
        monkeypatch.setattr(calculated_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)))

        computed.first_role_check("default")

        assert pressed == ["1"]

    def test_does_not_press_when_no_match(self, make_instance, monkeypatch):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(
            take_screenshot=lambda **kwargs: (image, 0, 0, 20, 20)
        )
        pressed = []
        monkeypatch.setattr(calculated_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)))

        computed.first_role_check("default")

        assert pressed == []

    def test_forwards_the_map_version_to_the_role_check(self, make_instance):
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(
            take_screenshot=lambda **kwargs: (np.zeros((2, 2, 3), np.uint8), 0, 0, 2, 2)
        )

        computed.first_role_check("HuangQuan")

        assert self.role_checks == ["HuangQuan"]


class TestRunMaploadCheck:
    """地图加载轮询：四个提前退出的条件，加一个超时兜底。"""

    def test_breaks_when_map_load_shows_and_main_ui_follows(self, computed):
        img, _ = wire(computed, scans=[{"max_val": 0.99}], on_main=[True])

        computed.run_mapload_check()

        assert img.calls == {
            "scan_screenshot": 1,
            "on_main_interface": 1,
            "on_interface": 0,
        }

    def test_breaks_on_black_screen(self, computed):
        img, screens = wire(computed, scans=[{"max_val": 0.0}], blackscreen=[True])

        computed.run_mapload_check()

        assert screens.cal_time_calls == 1
        assert img.calls["on_main_interface"] == 0, "黑屏就跳出了，不用再查主界面"

    def test_breaks_after_main_ui_seen_twice(self, computed):
        img, _ = wire(
            computed,
            scans=[{"max_val": 0.0}],
            on_main=[True, True],
            blackscreen=[False],
        )

        computed.run_mapload_check()

        assert img.calls["on_main_interface"] == 2, "要连续两次才算数"
        assert img.calls["on_interface"] == 0

    def test_breaks_after_the_simulated_universe_reward_screen_seen_twice(self, computed):
        img, _ = wire(
            computed,
            scans=[{"max_val": 0.0}],
            on_main=[False],
            on_interface=[True, True],
            blackscreen=[False],
        )

        computed.run_mapload_check()

        assert img.calls["on_interface"] == 2

    def test_gives_up_after_max_retries(self, computed, log_records):
        img, _ = wire(
            computed,
            scans=[{"max_val": 0.0}] * 2,
            on_main=[False] * 2,
            on_interface=[False] * 2,
            blackscreen=[False] * 2,
        )

        computed.run_mapload_check(max_error_count=2)

        assert img.calls["scan_screenshot"] == 2
        assert any("加载地图超时" in r["message"] for r in log_records)

    def test_single_main_ui_sighting_is_not_enough(self, computed):
        """只看到一次主界面不能收工，得连续两次 —— 否则会把过场当成加载完成。

        第一轮「看到一次就没再看到」，于是不跳转、也不计错；后两轮全落空才计满退出。
        """
        img, _ = wire(
            computed,
            scans=[{"max_val": 0.0}] * 3,
            on_main=[True, False, False, False],
            on_interface=[False] * 3,
            blackscreen=[False] * 3,
        )

        computed.run_mapload_check(max_error_count=2)

        assert img.calls["scan_screenshot"] == 3, "第一轮那次不算数，还要继续看"


class TestRunDreamBuildCheck:
    def test_breaks_when_the_module_shows_up(self, computed):
        img, _ = wire(computed, scans=[{"max_val": 0.99}])

        computed.run_dreambuild_check()

        assert img.calls["scan_screenshot"] == 1

    def test_times_out_after_max_retries(self, computed, log_records):
        img, _ = wire(computed, scans=[{"max_val": 0.0}] * 2)

        computed.run_dreambuild_check(max_error_count=2)

        assert img.calls["scan_screenshot"] == 2
        assert any("移动模块加载超时" in r["message"] for r in log_records)
