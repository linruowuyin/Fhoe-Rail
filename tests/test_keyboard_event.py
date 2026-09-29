"""utils/drivers/keyboard_event.py —— 键名映射与按下/释放配对。"""

import pytest
from pynput.keyboard import Key as KeyboardKey

import utils.drivers.keyboard_event as keyboard_event_module
from utils.drivers.keyboard_event import KeyboardEvent


class RecordingController:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))


@pytest.fixture
def controller(monkeypatch):
    instance = RecordingController()
    monkeypatch.setattr(keyboard_event_module, "KeyboardController", lambda: instance)
    return instance


class TestTranslateKey:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("space", KeyboardKey.space),
            ("caps", KeyboardKey.caps_lock),
            ("esc", KeyboardKey.esc),
            ("enter", KeyboardKey.enter),
            ("shift", KeyboardKey.shift),
            ("ctrl", KeyboardKey.ctrl),
            ("alt", KeyboardKey.alt),
        ],
    )
    def test_special_keys_are_mapped(self, name, expected):
        assert KeyboardEvent.translate_key(name) is expected

    def test_regular_keys_pass_through(self):
        assert KeyboardEvent.translate_key("w") == "w"
        assert KeyboardEvent.translate_key("1") == "1"

    def test_unknown_name_is_returned_as_is(self):
        assert KeyboardEvent.translate_key("not_a_key") == "not_a_key"

    def test_left_right_modifiers_are_distinguishable(self):
        assert KeyboardEvent.translate_key("alt_l") is not KeyboardEvent.translate_key(
            "alt_r"
        )
        assert KeyboardEvent.translate_key("ctrl_l") is not KeyboardEvent.translate_key(
            "ctrl_r"
        )

    def test_shift_aliases_follow_pynput_semantics(self):
        """pynput 里 Key.shift_l 与 Key.shift 是同一个枚举成员，属库行为。"""
        assert KeyboardEvent.translate_key("shift_l") is KeyboardEvent.translate_key(
            "shift"
        )


class TestKeyboardPress:
    def test_presses_then_releases(self, controller, monkeypatch):
        monkeypatch.setattr(keyboard_event_module.time, "sleep", lambda seconds: None)

        KeyboardEvent.keyboard_press("w", delay=0.5)

        assert controller.events == [("press", "w"), ("release", "w")]

    def test_translates_before_pressing(self, controller, monkeypatch):
        monkeypatch.setattr(keyboard_event_module.time, "sleep", lambda seconds: None)

        KeyboardEvent.keyboard_press("caps")

        assert controller.events == [
            ("press", KeyboardKey.caps_lock),
            ("release", KeyboardKey.caps_lock),
        ]

    def test_releases_even_when_sleep_is_interrupted(self, controller, monkeypatch):
        def boom(seconds):
            raise KeyboardInterrupt("用户中断")

        monkeypatch.setattr(keyboard_event_module.time, "sleep", boom)

        with pytest.raises(KeyboardInterrupt):
            KeyboardEvent.keyboard_press("w", delay=1)

        assert ("release", "w") in controller.events, "按键必须被释放，否则会卡住"
