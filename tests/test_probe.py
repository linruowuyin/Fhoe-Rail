"""utils/vision/probe.py —— CLI 与 WebUI 共用的探针实现。

用替身截图源 + 合成帧，不需要游戏窗口。预览图那几条会真的解码 PNG 回来数像素 ——
画框是净新增的能力，得验它确实画在框的位置上，而不是只验「产出了字节」。
"""

import cv2
import numpy as np
import pytest

from utils.core.match_offsets import FUZZY_PADDING
from utils.core.thresholds import DEFAULT_MATCH
from utils.drivers.screen import CAPTURE_PRINTWINDOW, CAPTURE_SCREENGRAB
from utils.vision import probe

#: 一次截图对应的屏幕区域（1920×1080 的一块，故意不从 0 开始 —— 坐标换算容易在这里错）
REGION = (100, 200, 2020, 1280)
#: 模板贴在屏幕上的位置；换算到帧内是 (712, 440)
BOX_AT = (812, 640)


def structured_template():
    """有结构的模板。纯色模板配 TM_CCORR_NORMED 会到处都打 1.0，测不出东西。"""
    template = np.zeros((16, 24, 3), np.uint8)
    template[4:12, 6:18] = (255, 128, 0)
    return template


class StubScreen:
    def __init__(self, frame, source=CAPTURE_PRINTWINDOW, region=REGION):
        self.frame = frame
        self.region = region
        self.last_capture_source = source
        self.calls = []

    def take_screenshot(self, offset=(0, 0, 0, 0), max_retries=50, retry_interval=2):
        self.calls.append({"max_retries": max_retries, "retry_interval": retry_interval})
        return self.frame, *self.region


def frame_with(template, left=None, top=None):
    """合成帧，模板放在 BOX_AT 对应的帧内位置上。"""
    frame = np.zeros((1080, 1920, 3), np.uint8)
    height, width = template.shape[:2]
    if left is None:
        left = BOX_AT[0] - REGION[0]
    if top is None:
        top = BOX_AT[1] - REGION[1]
    frame[top : top + height, left : left + width] = template
    return frame


@pytest.fixture
def measured():
    template = structured_template()
    screen = StubScreen(frame_with(template))
    return probe.measure(screen, template, threshold=0.9), template


class TestMeasure:
    def test_finds_the_box_in_screen_coordinates(self, measured):
        result, _ = measured

        assert result["box"] == (812, 640, 836, 656)
        assert result["center"] == (824, 648)

    def test_a_perfect_match_scores_one(self, measured):
        result, _ = measured

        assert result["score"] == pytest.approx(1.0)
        assert result["passed"] is True

    def test_margin_is_score_minus_threshold(self, measured):
        result, _ = measured

        assert result["margin"] == pytest.approx(0.1, abs=1e-5)

    def test_reports_both_offsets(self, measured):
        result, _ = measured

        assert result["exact_offset"] == (712, 440, -1184, -624)
        assert result["fuzzy_offset"] == (707, 435, -1179, -619)
        assert result["pad_applied"] == FUZZY_PADDING

    def test_passed_uses_strict_greater_than(self):
        """全项目都是严格大于 —— 分数正好等于阈值算没通过。"""
        template = structured_template()
        screen = StubScreen(frame_with(template))

        result = probe.measure(screen, template, threshold=1.0)

        assert result["score"] == pytest.approx(1.0)
        assert result["passed"] is False

    def test_default_threshold_comes_from_core_thresholds(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        assert probe.measure(screen, template)["threshold"] == DEFAULT_MATCH

    def test_carries_the_capture_source(self):
        template = structured_template()
        screen = StubScreen(frame_with(template), source=CAPTURE_SCREENGRAB)

        result = probe.measure(screen, template, allow_screen_fallback=True)

        assert result["capture_source"] == CAPTURE_SCREENGRAB

    def test_the_frame_rides_along_so_the_preview_shows_the_same_one(self):
        template = structured_template()
        frame = frame_with(template)
        screen = StubScreen(frame)

        result = probe.measure(screen, template)

        assert result["frame"] is frame, "预览要画的就是量出这些数字的那一帧"

    def test_capture_retries_are_capped_for_a_hand_triggered_probe(self):
        """不能按 take_screenshot 的默认 50×2 秒挂着 —— WebUI 那边还占着请求线程。"""
        template = structured_template()
        screen = StubScreen(frame_with(template))

        probe.measure(screen, template)

        assert screen.calls[-1]["max_retries"] <= 5
        assert screen.calls[-1]["retry_interval"] <= 1

    def test_capture_retries_are_overridable(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        probe.measure(screen, template, max_retries=1, retry_interval=0.5)

        assert screen.calls[-1] == {"max_retries": 1, "retry_interval": 0.5}

    def test_a_template_bigger_than_the_frame_is_a_clear_error(self):
        """不然 cv2.matchTemplate 会抛一句没人看得懂的断言，调用方也没法报 400。"""
        template = np.zeros((2000, 2000, 3), np.uint8)
        screen = StubScreen(np.zeros((1080, 1920, 3), np.uint8))

        with pytest.raises(ValueError, match="比截图区域还大"):
            probe.measure(screen, template)


class TestScreenFallbackIsRejected:
    """回退去抓屏幕拿到的帧可能根本不是游戏画面 —— 默认不放过。

    主程序在 PrintWindow 失败时会退到按屏幕坐标抓，抓到的可能是盖在游戏上的别的
    窗口。那种帧量出来的数字看着正常，其实量错了对象，探针宁可报错。
    """

    def test_rejects_a_screengrab_frame(self):
        template = structured_template()
        screen = StubScreen(frame_with(template), source=CAPTURE_SCREENGRAB)

        with pytest.raises(probe.ScreenFallbackRejected):
            probe.measure(screen, template)

    def test_the_rejection_is_a_runtime_error(self):
        """WebUI 靠这一点把它映射成 503（RuntimeError 分支）。"""
        assert issubclass(probe.ScreenFallbackRejected, RuntimeError)

    def test_can_be_allowed_explicitly(self):
        template = structured_template()
        screen = StubScreen(frame_with(template), source=CAPTURE_SCREENGRAB)

        result = probe.measure(screen, template, allow_screen_fallback=True)

        assert result["capture_source"] == CAPTURE_SCREENGRAB

    def test_a_printwindow_frame_is_never_rejected(self, measured):
        result, _ = measured

        assert result["capture_source"] == CAPTURE_PRINTWINDOW


class TestAnnotateMatch:
    def test_crops_a_padded_window_around_the_match(self, measured):
        result, _ = measured

        crop = probe.annotate_match(result, margin=120)

        # 外扩框在帧内是 (707,435)-(741,461)，四边再留 120：266 × 274
        assert crop.shape == (266, 274, 3)

    def test_clamps_at_the_frame_edge(self):
        template = structured_template()

        frame = np.zeros((1080, 1920, 3), np.uint8)
        frame[0:16, 0:24] = template  # 模板贴在帧的左上角
        screen = StubScreen(frame, region=(0, 0, 1920, 1080))

        crop = probe.annotate_match(probe.measure(screen, template), margin=120)

        # 框 (0,0)-(24,16) 外扩到 (0,0)-(29,21)（左边被夹住），再留 120 的上下文
        assert crop.shape == (16 + FUZZY_PADDING + 120, 24 + FUZZY_PADDING + 120, 3)

    def test_draws_the_exact_box_in_green(self, measured):
        result, _ = measured

        crop = probe.annotate_match(result, margin=120)

        # 精确框帧内 (712,440)，裁掉左 587、上 315 → 裁剪图里的 (125,125)
        assert tuple(crop[125, 125]) == probe.BOX_COLOR_EXACT

    def test_draws_the_padded_box_in_amber(self, measured):
        result, _ = measured

        crop = probe.annotate_match(result, margin=120)

        # 外扩框帧内 (707,435)，裁掉左 587、上 315 → 裁剪图里的 (120,120)
        assert tuple(crop[120, 120]) == probe.BOX_COLOR_PADDED

    def test_the_padding_did_not_swallow_the_setting(self, measured):
        """标注的是副本 —— 不能把框画回 measure 拿到的原始帧上。"""
        result, _ = measured

        probe.annotate_match(result, margin=120)

        assert tuple(result["frame"][440, 712]) == (0, 0, 0), "原始帧必须干净"

    def test_returns_none_when_there_is_nothing_to_crop(self):
        degenerate = {
            "frame": np.zeros((0, 0, 3), np.uint8),
            "region": (0, 0, 0, 0),
            "box": (0, 0, 0, 0),
            "padded_box": (0, 0, 0, 0),
        }

        assert probe.annotate_match(degenerate) is None


class TestRenderPreviewPng:
    def test_returns_png_bytes(self, measured):
        result, _ = measured

        data = probe.render_preview_png(result)

        assert data.startswith(b"\x89PNG\r\n\x1a\n")

    def test_the_bytes_decode_back_to_the_annotated_crop(self, measured):
        result, _ = measured

        decoded = cv2.imdecode(
            np.frombuffer(probe.render_preview_png(result), np.uint8), cv2.IMREAD_COLOR
        )

        assert decoded.shape == probe.annotate_match(result).shape
        assert tuple(decoded[125, 125]) == probe.BOX_COLOR_EXACT

    def test_returns_none_when_there_is_nothing_to_crop(self):
        degenerate = {
            "frame": np.zeros((0, 0, 3), np.uint8),
            "region": (0, 0, 0, 0),
            "box": (0, 0, 0, 0),
            "padded_box": (0, 0, 0, 0),
        }

        assert probe.render_preview_png(degenerate) is None


class TestTwoStrategies:
    """探针同时给出原始颜色匹配与轮廓（梯度）匹配，共用同一帧。"""

    def test_reports_color_and_shape_side_by_side(self, measured):
        result, _ = measured

        comparisons = result["comparisons"]
        assert [item["strategy"] for item in comparisons] == ["color", "shape"]
        assert [item["label"] for item in comparisons] == [
            "原始识别（颜色）",
            "轮廓识别（形状）",
        ]
        primary = [item for item in comparisons if item["primary"]]
        assert len(primary) == 1
        assert primary[0]["strategy"] == result["strategy"]

    def test_both_comparisons_use_the_same_frame(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        probe.measure(screen, template, threshold=0.9)

        assert len(screen.calls) == 1, "两种策略要复用同一帧，不能各抓一次"

    def test_each_comparison_has_its_own_box_and_offsets(self, measured):
        result, _ = measured

        for item in result["comparisons"]:
            for field in (
                "score",
                "second",
                "box",
                "center",
                "margin",
                "passed",
                "exact_offset",
                "fuzzy_offset",
            ):
                assert field in item
            assert item["box"][0] == BOX_AT[0]


class TestSearchArea:
    """搜索区域：调用点带 offset 时，探针在同一帧上再量一次那个子区域。"""

    def test_default_has_only_the_full_area(self, measured):
        result, _ = measured

        assert [area["area"] for area in result["areas"]] == ["full"]
        assert result["areas"][0]["region"] == REGION
        assert result["areas"][0]["error"] is None
        assert result["search_offset"] is None

    def test_top_level_fields_stay_the_full_screen_result(self):
        """给 search_offset 不能改变旧字段的含义，否则旧调用方读到的就是子区域数字。"""
        template = structured_template()
        screen = StubScreen(frame_with(template))

        with_offset = probe.measure(
            screen, template, threshold=0.9, search_offset=(700, 430, 0, 0)
        )
        without = probe.measure(screen, template, threshold=0.9)

        assert with_offset["box"] == without["box"]
        assert with_offset["score"] == pytest.approx(without["score"])
        assert with_offset["region"] == REGION

    def test_measures_the_cropped_region_in_screen_coordinates(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        result = probe.measure(
            screen, template, threshold=0.9, search_offset=(700, 430, 0, 0)
        )

        assert len(screen.calls) == 1, "调用点区域要从同一帧裁，不能重新抓一帧"
        areas = {area["area"]: area for area in result["areas"]}
        search = areas["search"]
        assert search["offset"] == (700, 430, 0, 0)
        assert search["region"] == (800, 630, 2020, 1280)
        color = next(c for c in search["comparisons"] if c["strategy"] == "color")
        assert color["score"] == pytest.approx(1.0)
        # 帧内坐标 → 屏幕坐标，和全屏那次一致
        assert color["box"] == (812, 640, 836, 656)

    def test_a_region_that_cuts_the_match_gets_a_lower_score(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        result = probe.measure(
            screen, template, threshold=0.9, search_offset=(740, 470, 0, 0)
        )

        areas = {area["area"]: area for area in result["areas"]}
        color = next(
            c for c in areas["search"]["comparisons"] if c["strategy"] == "color"
        )
        assert color["score"] < result["score"]

    def test_an_invalid_offset_reports_instead_of_crashing(self):
        template = structured_template()
        screen = StubScreen(frame_with(template))

        result = probe.measure(
            screen, template, threshold=0.9, search_offset=(5000, 0, -5000, 0)
        )

        areas = {area["area"]: area for area in result["areas"]}
        assert areas["search"]["comparisons"] == []
        assert "退回全屏" in areas["search"]["error"]
        assert areas["search"]["region"] == REGION


class TestCropToOffset:
    def test_matches_the_take_screenshot_region(self):
        frame = np.arange(12 * 20 * 3, dtype=np.uint8).reshape(12, 20, 3)
        region = (100, 200, 120, 212)

        crop, cropped_region, applied = probe.crop_to_offset(
            frame, region, (2, 3, -4, -5)
        )

        assert applied is True
        assert cropped_region == (102, 203, 116, 207)
        assert crop.shape == (4, 14, 3)
        assert np.array_equal(crop, frame[3:7, 2:16])

    def test_an_invalid_offset_returns_the_frame_untouched(self):
        frame = np.zeros((4, 4, 3), np.uint8)
        region = (0, 0, 4, 4)

        crop, cropped_region, applied = probe.crop_to_offset(
            frame, region, (10, 0, -10, 0)
        )

        assert applied is False
        assert cropped_region == region
        assert crop is frame
