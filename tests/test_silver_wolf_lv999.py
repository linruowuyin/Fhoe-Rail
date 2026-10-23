"""utils/flows/roles/silver_wolf_lv999.py —— 银狼 LV.999 秘技 lv999_e 与 E 状态检测。

钉住：设置整轮只做一次、失败不置位且抛 CustomException、每次 lv999_e 只按
`handle_e(2)`（只放秘技、不引战）、按完用状态图验证、没检测到就终止（不盲按第二次）。
"""

import numpy as np
import pytest

from utils.core.exceptions import CustomException
from utils.core.thresholds import SILVER_WOLF_LV999_E_ICON
from utils.flows.roles.silver_wolf_lv999 import (
    E_STATE_CHECK_DELAY,
    SILVER_WOLF_LV999_E_IMAGE,
    SilverWolfLv999,
    e_state_offset,
)


def no_sleep(_seconds):
    """测试里不真睡（否则每个 lv999_e 都要等 2 秒）。"""


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

    def __init__(self, settings_ok=True, e_states=(False, True), template=True):
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


class TestIsLv999EActive:
    def test_passes_the_computed_offset_and_threshold(self):
        handle = FakeHandle(e_states=(True,))

        assert SilverWolfLv999(sleep=no_sleep).is_lv999_e_active(handle) is True

        call = handle.img.calls[0]
        assert call["offset"] == e_state_offset((7, 14))
        assert call["threshold"] == SILVER_WOLF_LV999_E_ICON
        assert call["timeout"] == 0.0, "等满 2 秒后只判一次"
        assert call["check_list"] == [handle.img.template]
        assert handle.img.path == SILVER_WOLF_LV999_E_IMAGE

    def test_returns_false_when_template_does_not_match(self):
        handle = FakeHandle(e_states=(False,))
        assert SilverWolfLv999(sleep=no_sleep).is_lv999_e_active(handle) is False

    def test_missing_template_is_a_configuration_error(self):
        handle = FakeHandle(template=False)
        with pytest.raises(CustomException):
            SilverWolfLv999(sleep=no_sleep).is_lv999_e_active(handle)


class TestCheckE:
    def test_already_active_skips_e_and_sleep(self):
        handle = FakeHandle(e_states=(True,))
        sleeps = []
        lv999 = SilverWolfLv999(sleep=sleeps.append)

        lv999.ensure_lv999_e(1, handle)

        assert handle.e_values == [], "状态已经开着就不该再按 E"
        assert sleeps == [], "没按 E 就不需要等 2 秒"
        assert len(handle.img.calls) == 1

    def test_waits_two_seconds_after_pressing_e(self):
        sleeps = []
        handle = FakeHandle(e_states=(False, True))
        lv999 = SilverWolfLv999(sleep=sleeps.append)

        lv999.ensure_lv999_e(1, handle)

        assert E_STATE_CHECK_DELAY == 2.0
        assert sleeps == [2.0], "按 E 后要等 2 秒再判状态"
        assert handle.e_values == [2]
        assert len(handle.img.calls) == 2, "按 E 前先查一次、按完再判一次"

    def test_first_call_runs_settings_then_presses_e_and_verifies(self):
        handle = FakeHandle(e_states=(False, True))
        lv999 = SilverWolfLv999(sleep=no_sleep)

        lv999.ensure_lv999_e(1, handle)

        assert handle.settings_calls == 1
        assert handle.e_values == [2], "地图开头只放秘技，不引战"
        assert len(handle.img.calls) == 2
        assert lv999.settings_ready is True

    def test_second_call_skips_settings_and_e_when_already_active(self):
        handle = FakeHandle(e_states=(False, True, True))
        lv999 = SilverWolfLv999(sleep=no_sleep)

        lv999.ensure_lv999_e(1, handle)
        lv999.ensure_lv999_e(1, handle)

        assert handle.settings_calls == 1, "设置阶段只该做一次"
        assert handle.e_values == [2], "第二张图状态还在，就不该再按 E"
        assert len(handle.img.calls) == 3

    def test_settings_failure_raises_and_does_not_mark_ready(self):
        handle = FakeHandle(settings_ok=False)
        lv999 = SilverWolfLv999(sleep=no_sleep)

        with pytest.raises(CustomException):
            lv999.ensure_lv999_e(1, handle)

        assert handle.e_values == [], "设置失败时不该按 E"
        assert handle.img.calls == []
        assert lv999.settings_ready is False

    def test_settings_are_retried_after_failure(self):
        handle = FakeHandle(settings_ok=False)
        lv999 = SilverWolfLv999(sleep=no_sleep)
        with pytest.raises(CustomException):
            lv999.ensure_lv999_e(1, handle)

        handle.settings_ok = True
        lv999.ensure_lv999_e(1, handle)

        assert handle.settings_calls == 2, "失败不能把设置标记成已完成"
        assert handle.e_values == [2]

    def test_inactive_after_press_aborts(self):
        handle = FakeHandle(e_states=(False, False))
        lv999 = SilverWolfLv999(sleep=no_sleep)

        with pytest.raises(CustomException):
            lv999.ensure_lv999_e(1, handle)

        assert handle.e_values == [2], "不自动重按：E 若有开关语义，第二次会把状态关掉"
        assert len(handle.img.calls) == 2, "按前查一次、按后 2 秒再判一次"

    @pytest.mark.parametrize("value", [0, 2, "1", None])
    def test_invalid_value_is_refused(self, value):
        handle = FakeHandle()
        lv999 = SilverWolfLv999(sleep=no_sleep)

        with pytest.raises(CustomException):
            lv999.ensure_lv999_e(value, handle)

        assert handle.settings_calls == 0
        assert handle.e_values == []


class TestEnsureSettings:
    def test_returns_true_and_skips_when_already_ready(self):
        handle = FakeHandle()
        lv999 = SilverWolfLv999(sleep=no_sleep)
        lv999.settings_ready = True

        assert lv999.ensure_settings(handle) is True
        assert handle.settings_calls == 0

    def test_returns_false_on_failure_without_marking_ready(self):
        handle = FakeHandle(settings_ok=False)
        lv999 = SilverWolfLv999(sleep=no_sleep)

        assert lv999.ensure_settings(handle) is False
        assert lv999.settings_ready is False

    def test_sets_ready_on_success(self):
        handle = FakeHandle()
        lv999 = SilverWolfLv999(sleep=no_sleep)

        assert lv999.ensure_settings(handle) is True
        assert lv999.settings_ready is True
