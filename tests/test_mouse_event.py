"""utils/drivers/mouse_event.py —— 点击、拖拽、识图点击与视角旋转。"""

from types import SimpleNamespace

import pytest
import win32api
import win32con

import utils.drivers.mouse_event as mouse_event_module
from utils.config.config import ConfigurationManager
from utils.drivers.mouse_event import MouseEvent


class FakeTime:
    """替换 mouse_event 模块内的 time，用来精确控制超时判定。"""

    def __init__(self, values=()):
        self.values = list(values)
        self.slept = []

    def time(self):
        return self.values.pop(0) if self.values else 999.0

    def sleep(self, seconds):
        self.slept.append(seconds)


class StubImg:
    def __init__(self, max_val=0.0, point=(50, 60)):
        self.max_val = max_val
        self.point = point
        self.scanned = []

    def scan_screenshot(self, prepared, offset=(0, 0, 0, 0)):
        self.scanned.append(prepared)
        return {"max_val": self.max_val, "max_loc": (0, 0)}

    def img_center_point(self, result, shape):
        return self.point


class TestClick:
    def test_single_click_delegates_to_mouse_press(self, make_instance):
        event = make_instance(MouseEvent)
        presses = []
        event.mouse_press = lambda x, y, delay: presses.append((x, y, delay))

        event.click((10.7, 20.2))

        assert presses == [(10, 20, 0.05)]

    def test_multiple_clicks_repeat(self, make_instance):
        event = make_instance(MouseEvent)
        presses = []
        event.mouse_press = lambda x, y, delay: presses.append((x, y, delay))

        event.click((1, 2), clicks=3, delay=0.2)

        assert presses == [(1, 2, 0.2)] * 3


class TestMousePress:
    def test_sends_left_down_then_left_up(self, monkeypatch, make_instance):
        positions = []
        events = []
        monkeypatch.setattr(
            win32api, "SetCursorPos", lambda position: positions.append(position)
        )
        monkeypatch.setattr(
            win32api, "mouse_event", lambda *args: events.append(args[0])
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        make_instance(MouseEvent).mouse_press(5, 6)

        assert positions == [(5, 6)]
        assert events == [
            win32con.MOUSEEVENTF_LEFTDOWN,
            win32con.MOUSEEVENTF_LEFTUP,
        ]


class TestMousePressAlt:
    def test_releases_alt_on_success(self, monkeypatch, make_instance):
        flags = []
        monkeypatch.setattr(
            win32api, "keybd_event", lambda vk, scan, value, extra: flags.append(value)
        )
        event = make_instance(MouseEvent)
        event.mouse_press = lambda x, y, delay: None

        event.mouse_press_alt(1, 2)

        assert flags == [0, win32con.KEYEVENTF_KEYUP]

    def test_releases_alt_even_when_click_raises(self, monkeypatch, make_instance):
        flags = []
        monkeypatch.setattr(
            win32api, "keybd_event", lambda vk, scan, value, extra: flags.append(value)
        )
        event = make_instance(MouseEvent)

        def boom(*args):
            raise RuntimeError("点击失败")

        event.mouse_press = boom

        with pytest.raises(RuntimeError):
            event.mouse_press_alt(1, 2)

        assert flags == [0, win32con.KEYEVENTF_KEYUP], "ALT 必须被释放，否则键盘会卡住"


class TestClickTargetWithAlt:
    def test_presses_and_releases_alt(self, monkeypatch, make_instance):
        state = {"pressed": False}
        flags = []

        def keybd_event(vk, scan, value, extra):
            flags.append(value)
            # 没有 KEYUP 标志就是按下；EXTENDEDKEY(0x1) 只是修饰位
            state["pressed"] = not (value & win32con.KEYEVENTF_KEYUP)

        monkeypatch.setattr(win32api, "keybd_event", keybd_event)
        monkeypatch.setattr(
            win32api, "GetKeyState", lambda vk: -128 if state["pressed"] else 0
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        event = make_instance(MouseEvent)
        matcher = SimpleNamespace(click_target=lambda *args, **kwargs: True)

        event.click_target_with_alt(matcher, "x.png", 0.9)

        assert flags[0] == win32con.KEYEVENTF_EXTENDEDKEY
        assert any(value & win32con.KEYEVENTF_KEYUP for value in flags)


class TestMouseMove:
    def test_splits_large_angle_into_clamped_steps(self, monkeypatch, make_instance):
        deltas = []
        monkeypatch.setattr(
            win32api, "mouse_event", lambda flags, dx, dy: deltas.append(dx)
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        event = make_instance(MouseEvent, scale=1.0, multi_num=1.0)
        event.get_multi_num = lambda: 1.0

        event.mouse_move(100)

        # 100 -> 30, 剩 70 -> 30, 剩 40 -> 30, 剩 10；每步 int(16.5 * 角度)
        assert deltas == [495, 495, 495, 165]

    def test_negative_angle_is_clamped_symmetrically(self, monkeypatch, make_instance):
        deltas = []
        monkeypatch.setattr(
            win32api, "mouse_event", lambda flags, dx, dy: deltas.append(dx)
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        event = make_instance(MouseEvent, scale=1.0, multi_num=1.0)
        event.get_multi_num = lambda: 1.0

        event.mouse_move(-100)

        assert deltas == [-495, -495, -495, -165]

    def test_align_ignores_user_multiplier(self, monkeypatch, make_instance):
        deltas = []
        monkeypatch.setattr(
            win32api, "mouse_event", lambda flags, dx, dy: deltas.append(dx)
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        event = make_instance(MouseEvent, scale=1.0, multi_num=9.9)

        event.mouse_move(10, align=True)

        assert deltas == [165], "校准模式必须用固定倍率，否则无法收敛"

    def test_dpi_scale_is_applied(self, monkeypatch, make_instance):
        deltas = []
        monkeypatch.setattr(
            win32api, "mouse_event", lambda flags, dx, dy: deltas.append(dx)
        )
        monkeypatch.setattr(mouse_event_module, "time", FakeTime())

        event = make_instance(MouseEvent, scale=1.5, multi_num=1.0)
        event.mouse_move(10, align=True)

        assert deltas == [int(16.5 * 10 * 1.5)]


class TestGetMultiNum:
    def test_reads_angle_from_config(self, make_instance, set_config):
        event = make_instance(MouseEvent, cfg=ConfigurationManager())
        set_config(event.cfg, angle="1.25")
        assert event.get_multi_num() == pytest.approx(1.25)

    def test_defaults_to_one_when_missing(self, make_instance):
        event = make_instance(MouseEvent, cfg=ConfigurationManager())
        event.cfg.config_file.pop("angle", None)
        assert event.get_multi_num() == 1.0


class TestCoordinateBasedClicks:
    def test_relative_click_converts_percentages(self, make_instance, fake_window_factory):
        event = make_instance(MouseEvent, window=fake_window_factory(rect=(100, 200, 2020, 1280)))
        clicks = []
        event.mouse_press_alt = lambda x, y, delay=0.4: clicks.append((x, y))

        event.relative_click((50, 75))

        assert clicks == [(100 + 960, 200 + 810)]

    def test_relative_click_skipped_when_window_hidden(
        self, make_instance, fake_window_factory
    ):
        event = make_instance(MouseEvent, window=fake_window_factory(visible=False))
        clicks = []
        event.mouse_press_alt = lambda *args: clicks.append(args)

        event.relative_click((50, 50))

        assert clicks == []

    def test_click_center_uses_window_centre(self, make_instance, fake_window_factory):
        event = make_instance(MouseEvent, window=fake_window_factory(rect=(0, 0, 1920, 1080)))
        clicks = []
        event.mouse_press = lambda x, y, delay=0.05: clicks.append((x, y))

        event.click_center()

        assert clicks == [(960, 540)]
