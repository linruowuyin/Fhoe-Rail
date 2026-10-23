"""utils/flows/technique.py —— 银狼秘技 check_e 与 E 状态检测。

钉住：设置整轮只做一次、失败不置位且抛 CustomException、每次 check_e 只按
`handle_e(2)`（只放秘技、不引战）、按完用状态图验证、没检测到就终止（不盲按第二次）。
"""

import numpy as np
import pytest

from utils.core.exceptions import CustomException
from utils.core.thresholds import SILVER_WOLF_LV999_E_ICON
from utils.flows.technique import (
    SILVER_WOLF_LV999_E_IMAGE,
    Technique,
    e_state_offset,
)


class FakeImg:
    """记录 on_interface 的调用；`results` 依次作为检测结果。"""

    def __init__(self, results=(True,), template=True):
        self.results = list(results)
        self.template = (
            np.zeros((14, 7, 3), dtype=np.uint8) if template else None
        )
        self.calls = []

    def get_img(self, path):
        self.path = path
        return self.template

    def on_interface(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


class FakeHandle:
    """记录设置与 E 的调用顺序。"""

    def __init__(self, settings_ok=True, e_states=(True,), template=True):
        self.settings_ok = settings_ok
        self.settings_calls = 0
        self.e_values = []
        self.img = FakeImg(e_states, template)

    def auto_use_technique_consumable(self):
        self.settings_calls += 1
        return self.settings_ok

    def handle_e(self, value):
        self.e_values.append(value)


class TestEStateOffset:
    def test_7x14_template_with_2px_padding(self):
        # 7×14 在 (1630,320)：外扩 2px → 11×18，换算成四边增量
        assert e_state_offset((7, 14)) == (1628, 318, -281, -744)

    def test_padding_is_configurable(self):
        assert e_state_offset((7, 14), pad=0) == (1630, 320, -283, -746)

    def test_template_touching_the_corner(self):
        assert e_state_offset((7, 14), position=(1913, 1066)) == (
            1911,
            1064,
            0,
            0,
        )

    def test_template_overflowing_the_screen_is_refused(self):
        with pytest.raises(CustomException):
            e_state_offset((7, 14), position=(1915, 320))


class TestIsEActive:
    def test_passes_the_computed_offset_and_threshold(self):
        handle = FakeHandle()

        assert Technique().is_e_active(handle) is True

        call = handle.img.calls[0]
        assert call["offset"] == e_state_offset((7, 14))
        assert call["threshold"] == SILVER_WOLF_LV999_E_ICON
        assert call["check_list"] == [handle.img.template]
        assert handle.img.path == SILVER_WOLF_LV999_E_IMAGE

    def test_returns_false_when_template_does_not_match(self):
        handle = FakeHandle(e_states=(False,))
        assert Technique().is_e_active(handle) is False

    def test_missing_template_is_a_configuration_error(self):
        handle = FakeHandle(template=False)
        with pytest.raises(CustomException):
            Technique().is_e_active(handle)


class TestCheckE:
    def test_first_call_runs_settings_then_presses_e_and_verifies(self):
        handle = FakeHandle()
        technique = Technique()

        technique.check_e(1, handle)

        assert handle.settings_calls == 1
        assert handle.e_values == [2], "地图开头只放秘技，不引战"
        assert len(handle.img.calls) == 1
        assert technique.settings_ready is True

    def test_second_call_skips_settings_and_only_presses_e(self):
        handle = FakeHandle()
        technique = Technique()

        technique.check_e(1, handle)
        technique.check_e(1, handle)

        assert handle.settings_calls == 1, "设置阶段只该做一次"
        assert handle.e_values == [2, 2], "E 每张图都要按"
        assert len(handle.img.calls) == 2

    def test_settings_failure_raises_and_does_not_mark_ready(self):
        handle = FakeHandle(settings_ok=False)
        technique = Technique()

        with pytest.raises(CustomException):
            technique.check_e(1, handle)

        assert handle.e_values == [], "设置失败时不该按 E"
        assert handle.img.calls == []
        assert technique.settings_ready is False

    def test_settings_are_retried_after_failure(self):
        handle = FakeHandle(settings_ok=False)
        technique = Technique()
        with pytest.raises(CustomException):
            technique.check_e(1, handle)

        handle.settings_ok = True
        technique.check_e(1, handle)

        assert handle.settings_calls == 2, "失败不能把设置标记成已完成"
        assert handle.e_values == [2]

    def test_inactive_after_press_aborts(self):
        handle = FakeHandle(e_states=(False,))
        technique = Technique()

        with pytest.raises(CustomException):
            technique.check_e(1, handle)

        assert handle.e_values == [2], "不自动重按：E 若有开关语义，第二次会把状态关掉"
        assert len(handle.img.calls) == 1

    @pytest.mark.parametrize("value", [0, 2, "1", None])
    def test_invalid_value_is_refused(self, value):
        handle = FakeHandle()
        technique = Technique()

        with pytest.raises(CustomException):
            technique.check_e(value, handle)

        assert handle.settings_calls == 0
        assert handle.e_values == []


class TestEnsureSettings:
    def test_returns_true_and_skips_when_already_ready(self):
        handle = FakeHandle()
        technique = Technique()
        technique.settings_ready = True

        assert technique.ensure_settings(handle) is True
        assert handle.settings_calls == 0

    def test_returns_false_on_failure_without_marking_ready(self):
        handle = FakeHandle(settings_ok=False)
        technique = Technique()

        assert technique.ensure_settings(handle) is False
        assert technique.settings_ready is False

    def test_sets_ready_on_success(self):
        handle = FakeHandle()
        technique = Technique()

        assert technique.ensure_settings(handle) is True
        assert technique.settings_ready is True
