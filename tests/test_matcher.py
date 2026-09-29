"""utils/vision/matcher.py —— 匹配、判定、以及「找到图就点它」。

这些用例原本在 test_mouse_event.py 里 —— `click_target` 一族住在 MouseEvent
的时候。2026-09 把它们搬到 vision 层（drivers 只该管设备），测试也跟着搬。
"""

import numpy as np
import pytest

import utils.vision.matcher as matcher_module
from utils.vision.matcher import Matcher


class FakeTime:
    """替换 matcher 模块内的 time，用来精确控制超时判定。"""

    def __init__(self, values=()):
        self.values = list(values)
        self.slept = []

    def time(self):
        return self.values.pop(0) if self.values else 999.0

    def sleep(self, seconds):
        self.slept.append(seconds)


class StubScreen:
    """截图源替身：scan_screenshot 已被替换，这里只是占位。"""

    def take_screenshot(self, *args, **kwargs):
        raise AssertionError("不应真的抓屏")


class StubMouse:
    """点击执行者替身，记录被点击的坐标。"""

    def __init__(self):
        self.clicked = []
        self.last_search_allow_retry = False

    def click(self, points, slot, clicks, delay):
        self.clicked.append(points)

    def click_center(self):
        self.clicked.append("center")


@pytest.fixture
def matcher(make_instance):
    """一个不依赖窗口、不依赖游戏的 Matcher。"""
    mouse = StubMouse()
    return make_instance(
        Matcher,
        screen=StubScreen(),
        ui_images={},
        _mouse=mouse,
        img_search_val_dict={},
    ), mouse


class TestClickTargetAboveThreshold:
    def test_clicks_and_reports_success(self, matcher):
        instance, mouse = matcher
        instance.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": 0.95,
            "max_loc": (11, 22),
        }

        ok, value = instance.click_target_above_threshold(
            np.zeros((4, 4, 3), np.uint8), 0.9, (0, 0, 0, 0)
        )

        assert ok is True
        assert value == 0.95
        assert mouse.clicked == [(13, 24)]  # max_loc + 半个模板尺寸（4x4 模板）

    def test_does_not_click_below_threshold(self, matcher):
        instance, mouse = matcher
        instance.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": 0.5,
            "max_loc": (0, 0),
        }

        ok, value = instance.click_target_above_threshold(
            np.zeros((4, 4, 3), np.uint8), 0.9, (0, 0, 0, 0)
        )

        assert ok is False
        assert value == 0.5
        assert mouse.clicked == []


class TestClickOffset:
    """静态锚点与可点热区不重合时，落点整体平移（地图 JSON 的 click_offset 修饰键）。"""

    @staticmethod
    def _matcher_with_match(matcher):
        instance, mouse = matcher
        instance.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": 0.95,
            "max_loc": (11, 22),
        }
        return instance, mouse

    def test_click_point_is_shifted_by_the_offset(self, matcher):
        instance, mouse = self._matcher_with_match(matcher)

        ok, _ = instance.click_target_above_threshold(
            np.zeros((4, 4, 3), np.uint8), 0.9, (0, 0, 0, 0), click_offset=(60, 0)
        )

        assert ok is True
        assert mouse.clicked == [(13 + 60, 24)], "匹配中心 (13,24) 再向右 60"

    def test_no_offset_keeps_the_match_center(self, matcher):
        instance, mouse = self._matcher_with_match(matcher)

        instance.click_target_above_threshold(
            np.zeros((4, 4, 3), np.uint8), 0.9, (0, 0, 0, 0)
        )

        assert mouse.clicked == [(13, 24)]


class TestClickTarget:
    @pytest.fixture
    def instance(self, matcher, monkeypatch):
        subject, _ = matcher
        monkeypatch.setattr(
            matcher_module.image_library,
            "get_img",
            lambda path: np.zeros((4, 4, 3), np.uint8),
        )
        return subject

    def test_missing_image_returns_false(self, matcher, monkeypatch, log_records):
        subject, _ = matcher
        monkeypatch.setattr(matcher_module.image_library, "get_img", lambda path: None)

        assert subject.click_target("gone.png", 0.9) is False
        assert any(r["level"].name == "ERROR" for r in log_records)

    def test_returns_true_on_first_match(self, instance):
        instance.click_target_above_threshold = lambda *args: (True, 0.99)
        assert instance.click_target("x.png", 0.9) is True

    def test_flag_false_stops_after_first_miss(self, instance):
        instance.click_target_above_threshold = lambda *args: (False, 0.5)
        assert instance.click_target("x.png", 0.9, flag=False) is False

    def test_keeps_lowest_match_value_for_reporting(self, instance):
        """报告里的“最相似图片”取历史最低匹配值。"""
        instance.img_search_val_dict["x.png"] = 0.8
        instance.click_target_above_threshold = lambda *args: (False, 0.7)

        instance.click_target("x.png", 0.9, flag=False)

        assert instance.img_search_val_dict["x.png"] == 0.7

    def test_does_not_raise_a_recorded_lower_value(self, instance):
        instance.img_search_val_dict["x.png"] = 0.5
        instance.click_target_above_threshold = lambda *args: (False, 0.7)

        instance.click_target("x.png", 0.9, flag=False)

        assert instance.img_search_val_dict["x.png"] == 0.5

    def test_close_matches_are_not_recorded(self, instance):
        instance.click_target_above_threshold = lambda *args: (False, 0.995)

        instance.click_target("x.png", 0.9, flag=False)

        assert "x.png" not in instance.img_search_val_dict

    def test_falls_back_to_inverted_image_after_one_second(self, instance, monkeypatch):
        """原图匹配不上时，1 秒后改用颜色反转图（“阴阳变转”）。"""
        calls = []

        def fake(target, threshold, offset, clicks, delay, click_offset=(0, 0)):
            calls.append(target)
            return len(calls) == 2, 0.5

        instance.click_target_above_threshold = fake
        monkeypatch.setattr(matcher_module, "time", FakeTime([0, 0, 2]))

        assert instance.click_target("x.png", 0.9, timeout=10) is True
        assert len(calls) == 2

    def test_inverted_pass_also_carries_the_offset(self, instance, monkeypatch):
        """原图没中改用反色图，第二击也要带偏移 —— 否则它会落回锚点。"""
        offsets = []

        def fake(target, threshold, offset, clicks, delay, click_offset=(0, 0)):
            offsets.append(click_offset)
            return len(offsets) == 2, 0.5

        instance.click_target_above_threshold = fake
        monkeypatch.setattr(matcher_module, "time", FakeTime([0, 0, 2]))

        assert (
            instance.click_target("x.png", 0.9, timeout=10, click_offset=(60, 0)) is True
        )
        assert offsets == [(60, 0), (60, 0)]

    def test_timeout_writes_the_retry_flag_onto_the_mouse(self, instance):
        """超时是唯一会写重试标志的路径，且标志必须落在读取方持有对象上。

        读取方是 flows/map_operations，它持有 self.mouse_event —— 所以标志写在
        MouseEvent 上。这是当初 img.search_img_allow_retry 静默失效的教训（R13）。
        """
        instance.click_target_above_threshold = lambda *args: (False, 0.5)
        instance.mouse.last_search_allow_retry = False

        assert instance.click_target("x.png", 0.9, flag=False) is False
        assert instance.mouse.last_search_allow_retry is False  # flag=False 不写

    def test_timeout_writes_retry_in_map_value(self, instance, monkeypatch):
        monkeypatch.setattr(matcher_module, "time", FakeTime([0, 0, 2, 2]))
        instance.click_target_above_threshold = lambda *args: (False, 0.5)

        instance.click_target("x.png", 0.9, timeout=10, retry_in_map=True, flag=True)

        assert instance.mouse.last_search_allow_retry is True

    @pytest.mark.xfail(
        strict=True,
        reason="timeout 为 0（或极小）时 while 循环体一次都不执行，"
        "结尾的日志会读未赋值的 img_search_val，抛 UnboundLocalError 而不是返回 False",
    )
    def test_zero_timeout_returns_false(self, instance):
        assert instance.click_target("x.png", 0.9, timeout=0) is False


class TestMatcherIsConstructibleWithoutAGame:
    """识别层必须能在没有游戏的机器上实例化 —— 黄金图测试的前提。"""

    def test_default_construction_does_not_touch_the_window(self, monkeypatch):
        screen = StubScreen()
        subject = Matcher(screen=screen, ui_images={}, mouse=StubMouse())

        assert subject.screen is screen

    def test_mouse_is_lazy(self, monkeypatch):
        """MouseEvent() 会连锁构造 Window()，只有真要点击时才该去拿它。"""
        subject = Matcher(screen=StubScreen(), ui_images={}, mouse=StubMouse())
        assert subject._mouse is not None  # 注入的替身不会被替换

    def test_mouse_property_resolves_lazily_when_not_injected(self, monkeypatch):
        sentinel = StubMouse()
        monkeypatch.setattr(matcher_module, "MouseEvent", lambda: sentinel)

        subject = Matcher(screen=StubScreen(), ui_images={})

        assert subject._mouse is None
        assert subject.mouse is sentinel
        assert subject.mouse is sentinel  # 只构造一次


class TestPurePrimitives:
    def test_match_screenshot_offsets_are_applied(self):
        screenshot = np.zeros((60, 80, 3), dtype=np.uint8)
        screenshot[20:30, 30:40] = 255
        prepared = np.full((10, 10, 3), 255, dtype=np.uint8)

        result = Matcher.match_screenshot(screenshot, prepared, left=100, top=200)

        assert result["max_loc"] == (130, 220)

    def test_img_center_point(self):
        assert Matcher.img_center_point({"max_loc": (100, 200)}, (40, 60, 3)) == (
            130,
            220,
        )

    def test_handle_rotate_val_identity_at_zero(self):
        assert np.allclose(
            Matcher.handle_rotate_val(50, 50, 0), [[1, 0, 0], [0, 1, 0]]
        )
