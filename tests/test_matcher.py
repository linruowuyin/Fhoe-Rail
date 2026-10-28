"""utils/vision/matcher.py —— 匹配、判定、以及「找到图就点它」。

这些用例原本在 test_mouse_event.py 里 —— `click_target` 一族住在 MouseEvent
的时候。2026-09 把它们搬到 vision 层（drivers 只该管设备），测试也跟着搬。
"""

import cv2
import numpy as np
import pytest

import utils.vision.matcher as matcher_module
from utils.vision import assets
from utils.vision import images as image_library
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

    def test_shape_registered_targets_skip_the_inverted_pass(self, instance, monkeypatch):
        """轮廓模板不跑「阴阳变转」。

        取反后的梯度幅值与原图相同（Sobel 是线性的），跑一遍是空转；更糟的是
        反色数组查不回模板路径，会退回颜色匹配 —— 低阈值下等于绕开轮廓判定。
        """
        targets = []

        def fake(target, threshold, offset, clicks, delay, click_offset=(0, 0)):
            targets.append(id(target))
            return False, 0.5

        instance.click_target_above_threshold = fake
        monkeypatch.setattr(
            matcher_module.image_library,
            "strategy_of",
            lambda image: assets.MATCH_SHAPE,
        )
        monkeypatch.setattr(matcher_module, "time", FakeTime([0, 0, 2, 3, 999]))

        assert instance.click_target("x.png", 0.85, timeout=10) is False
        assert len(targets) == 2, "超时前应逐轮比原图"
        assert len(set(targets)) == 1, "只该比原图，不该出现反色图"

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


class TestSampleCollectionHook:
    """匹配的汇聚点顺带喂给图片样本收集器（开发者模式 collect_picture_samples）。"""

    def test_a_disabled_collector_is_never_touched(self, monkeypatch):
        from utils.vision import samples

        called = []
        monkeypatch.setattr(samples, "enabled", lambda: False)
        monkeypatch.setattr(samples, "note_match", lambda *args: called.append(args))

        Matcher.match_screenshot(
            np.zeros((60, 80, 3), np.uint8), np.zeros((10, 10, 3), np.uint8), 0, 0
        )

        assert called == [], "开关关着时不该有任何开销之外的副作用"

    def test_the_box_and_the_score_are_handed_over(self, monkeypatch):
        from utils.vision import samples

        seen = []
        monkeypatch.setattr(samples, "enabled", lambda: True)
        monkeypatch.setattr(
            samples,
            "note_match",
            lambda path, frame, region, box, score: seen.append((path, region, box, score)),
        )
        screenshot = np.zeros((60, 80, 3), dtype=np.uint8)
        prepared = np.full((10, 10, 3), 255, dtype=np.uint8)
        screenshot[20:30, 30:40] = 255

        Matcher.match_screenshot(screenshot, prepared, left=100, top=200)

        path, region, box, score = seen[0]
        assert region == (100, 200, 180, 260), "区域是「帧 + 它的屏幕原点」"
        assert box == (130, 220, 140, 230), "框是屏幕绝对坐标，尺寸 = 模板尺寸"
        assert score == pytest.approx(1.0)
        assert path is None, "合成数组没有对应文件，反查本来就该是 None"


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


class TestMatchPeaks:
    """次优峰值：标定阈值时比最优值更该看的数（CLAUDE.md §1.2 的负样本余量）。"""

    def test_second_peak_skips_every_position_overlapping_the_best(self):
        rng = np.random.default_rng(0)
        screenshot = rng.integers(0, 60, (60, 80, 3), dtype=np.uint8)
        prepared = np.zeros((8, 8, 3), dtype=np.uint8)
        prepared[2:6, 2:6] = 255
        screenshot[10:18, 10:18] = prepared  # 唯一一处精确吻合

        result = Matcher.match_peaks(screenshot, prepared, left=5, top=7)

        assert result["max_loc"] == (15, 17), "left/top 要加到位置上去"
        assert result["max_val"] > result["second_val"], (
            "次优峰屏蔽了最优峰周围一个模板大小的邻域，剩下的只是噪声"
        )

    def test_second_peak_is_zero_when_only_one_candidate_exists(self):
        """模板与帧一样大时只有一个候选位置，没有「次优」。"""
        prepared = np.zeros((8, 8, 3), dtype=np.uint8)
        prepared[2:6, 2:6] = 255

        result = Matcher.match_peaks(prepared.copy(), prepared)

        assert result["max_loc"] == (0, 0)
        assert result["second_val"] == 0.0


def _icon_mask(template):
    """模板里「亮色图标」的像素（setting_other 是深底亮图形）。"""
    return (cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) > 80).astype(np.uint8)


def _paste_icon(frame, icon, mask, x, y):
    """只把图标像素贴上去，底色保持目标背景 —— 模拟游戏里的透明图标。"""
    roi = frame[y:y + icon.shape[0], x:x + icon.shape[1]]
    roi[mask > 0] = icon[mask > 0]
    return frame


class TestShapeMatching:
    """`assets.MATCH_SHAPE`：只看轮廓，不看底色（设置菜单的「其他设置」页签）。"""

    @pytest.fixture
    def template(self, repo_root):
        template = image_library.get_img(assets.path("setting_other"))
        assert template is not None
        return template

    def test_setting_other_is_registered_for_shape_matching(self, template):
        assert image_library.strategy_of(template) == assets.MATCH_SHAPE

    def test_setting_icon_is_registered_for_shape_matching(self, repo_root):
        icon = image_library.get_img(assets.path("setting_icon"))
        assert image_library.strategy_of(icon) == assets.MATCH_SHAPE

    def test_other_assets_stay_on_color_matching(self, repo_root):
        icon = image_library.get_img(assets.path("setting_yes"))
        assert image_library.strategy_of(icon) == assets.MATCH_COLOR

    @pytest.mark.parametrize("index", [1, 2, 3])
    def test_check_4_1_points_are_registered_for_shape_matching(self, repo_root, index):
        """筑梦机关检查三张图走轮廓识别（2026-10-28 用户指定，阈值 0.85）。"""
        template = image_library.get_img(assets.path(f"check_4-1_point_{index}"))

        assert template is not None
        assert image_library.strategy_of(template) == assets.MATCH_SHAPE

    @pytest.mark.parametrize("index", [1, 2, 3])
    def test_check_4_1_shape_score_survives_colour_inversion(self, repo_root, index):
        """整图颜色反过来、轮廓没变：形状分应过 0.85，颜色分过不了。"""
        template = image_library.get_img(assets.path(f"check_4-1_point_{index}"))
        inverted = cv2.bitwise_not(template)

        shape = Matcher.match_peaks(inverted, template, strategy=assets.MATCH_SHAPE)
        color = Matcher.match_peaks(inverted, template, strategy=assets.MATCH_COLOR)

        assert shape["max_val"] >= 0.85
        assert color["max_val"] < 0.85

    @pytest.mark.parametrize(
        "template_index,frame_index", [(1, 2), (1, 3), (3, 1)]
    )
    def test_a_different_check_point_does_not_match(
        self, repo_root, template_index, frame_index
    ):
        """负样本：另外两个机关的画面不能误判成这个检查点（实测 ≤0.28）。"""
        template = image_library.get_img(
            assets.path(f"check_4-1_point_{template_index}")
        )
        frame = image_library.get_img(assets.path(f"check_4-1_point_{frame_index}"))
        padded = cv2.copyMakeBorder(
            frame, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(30, 30, 30)
        )

        # 不显式传 strategy —— 顺带验证登记表反查到的就是轮廓识别
        result = Matcher.match_peaks(padded, template)

        assert result["max_val"] < 0.85

    def test_shape_features_are_uint8_gradient_magnitude(self, template):
        features = Matcher.shape_features(template)

        assert features.shape == template.shape[:2]
        assert features.dtype == np.uint8
        assert features.max() > 0

    @pytest.mark.parametrize("background", ["black", "white", "gradient", "blur"])
    def test_scores_stay_high_when_the_background_changes(self, template, background):
        rng = np.random.default_rng(0)
        if background == "black":
            frame = np.zeros((300, 400, 3), np.uint8)
        elif background == "white":
            frame = np.full((300, 400, 3), 255, np.uint8)
        elif background == "gradient":
            frame = np.tile(
                np.linspace(0, 255, 400, dtype=np.uint8)[None, :, None], (300, 1, 3)
            )
        else:
            frame = cv2.GaussianBlur(
                rng.integers(0, 255, (300, 400, 3), dtype=np.uint8), (0, 0), 20
            )
        _paste_icon(frame, template, _icon_mask(template), 200, 100)

        result = Matcher.match_screenshot(frame, template, 0, 0)

        assert result["max_loc"] == (200, 100)
        assert result["max_val"] >= 0.90

    def test_flat_frame_does_not_match(self, template):
        frame = np.zeros((300, 400, 3), np.uint8)

        assert Matcher.match_screenshot(frame, template, 0, 0)["max_val"] < 0.5

    def test_another_icon_does_not_match(self, template, repo_root):
        other = image_library.get_img(assets.path("setting_icon"))
        frame = np.full((300, 400, 3), 255, np.uint8)
        _paste_icon(frame, other, _icon_mask(other), 200, 100)

        assert Matcher.match_screenshot(frame, template, 0, 0)["max_val"] < 0.5


class TestExplicitStrategy:
    def test_match_peaks_can_run_each_strategy_on_demand(self):
        rng = np.random.default_rng(0)
        screenshot = rng.integers(0, 60, (80, 100, 3), dtype=np.uint8)
        prepared = np.zeros((16, 20, 3), dtype=np.uint8)
        prepared[3:13, 4:16] = 200
        screenshot[30:46, 40:60] = prepared

        color = Matcher.match_peaks(screenshot, prepared, strategy="color")
        shape = Matcher.match_peaks(screenshot, prepared, strategy="shape")

        assert color["max_loc"] == (40, 30)
        assert shape["max_loc"] == (40, 30)
        assert color["max_val"] >= 0.99
        assert shape["max_val"] >= 0.95  # 梯度幅值化后有轻微量化损失
