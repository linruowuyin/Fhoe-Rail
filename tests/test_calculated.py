"""utils/flows/calculated.py —— 关机、购买检测、1 号位识别。"""

from types import SimpleNamespace

import numpy as np
import pytest

import utils.flows.calculated as calculated_module
from utils.flows.calculated import Calculated
from utils.vision.img import Img


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
    def test_presses_1_when_slot_matches_colour_range(self, make_instance, monkeypatch):
        image = np.empty((20, 20, 3), dtype=np.uint8)
        image[:, :] = (255, 255, 155)  # RGB，经 RGB2HSV 落在 [28,49,253]-[32,189,255]
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(
            take_screenshot=lambda **kwargs: (image, 0, 0, 20, 20)
        )
        pressed = []
        monkeypatch.setattr(calculated_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)))

        computed.first_role_check()

        assert pressed == ["1"]

    def test_does_not_press_when_no_match(self, make_instance, monkeypatch):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        computed = make_instance(Calculated)
        computed.img = SimpleNamespace(
            take_screenshot=lambda **kwargs: (image, 0, 0, 20, 20)
        )
        pressed = []
        monkeypatch.setattr(calculated_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)))

        computed.first_role_check()

        assert pressed == []
