"""utils/drivers/screen.py —— 截图范围计算、后台截图与重试。

这一层直接调 PrintWindow / ImageGrab，没法在单测里真截屏。所以：
范围换算那两段是纯函数，直接测；`capture_window_background` 与 `take_screenshot`
用替身把 Win32 那几层挡掉，只验「裁剪对不对、通道序对不对、重试是不是按预期走」。

（`Img` 门面委托过来的那几条在 tests/test_img.py 里，不重复。）
"""

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import utils.drivers.screen as screen_module
from utils.drivers.screen import ScreenSource, apply_offset, crop_box


class TestCropBox:
    def test_translates_absolute_crop_into_relative(self):
        assert crop_box((100, 50, 1920, 1080), (200, 100, 300, 200)) == (100, 50, 200, 150)

    def test_clamps_to_the_captured_region(self):
        # 裁剪框右下角超出截取范围，夹到边界
        assert crop_box((0, 0, 100, 100), (50, 50, 999, 999)) == (50, 50, 100, 100)

    def test_crop_starting_before_the_region_is_clamped_to_zero(self):
        assert crop_box((100, 100, 50, 50), (0, 0, 120, 120)) == (0, 0, 20, 20)

    def test_empty_result_is_none(self):
        assert crop_box((0, 0, 10, 10), (999, 999, 1000, 1000)) is None

    def test_reversed_box_is_none(self):
        assert crop_box((0, 0, 100, 100), (80, 80, 20, 20)) is None


class TestApplyOffset:
    def test_applies_a_valid_offset(self):
        assert apply_offset((0, 0, 1920, 1080), (10, 20, -30, -40)) == (
            (10, 20, 1890, 1040),
            True,
        )

    def test_zero_offset_is_still_an_offset(self):
        assert apply_offset((0, 0, 10, 10), (0, 0, 0, 0)) == ((0, 0, 10, 10), True)

    def test_offset_that_empties_the_region_is_rejected(self):
        assert apply_offset((0, 0, 1920, 1080), (5000, 0, 0, 0)) == (
            (0, 0, 1920, 1080),
            False,
        )

    def test_offset_inverting_the_vertical_range_is_rejected(self):
        # 下边界被推到上边界之上 —— 区域反了
        assert apply_offset((0, 0, 1920, 1080), (0, 0, 0, -2000)) == (
            (0, 0, 1920, 1080),
            False,
        )

    def test_a_positive_offset_grows_the_region(self):
        """右下偏移为正时区域是变大的，这是合法用法。"""
        assert apply_offset((0, 0, 1920, 1080), (0, 0, 10, 10)) == (
            (0, 0, 1930, 1090),
            True,
        )


# ---------------------------------------------------------------------------
# 后台截图：把 Win32 那几层换成假的
# ---------------------------------------------------------------------------


class FakeBitmap:
    def __init__(self):
        self.size = (0, 0)

    def CreateCompatibleBitmap(self, dc, width, height):
        self.size = (width, height)

    def GetInfo(self):
        return {"bmWidth": self.size[0], "bmHeight": self.size[1]}

    def GetBitmapBits(self, as_bytes):
        return bytes(self.size[0] * self.size[1] * 4)

    def GetHandle(self):
        return "HBITMAP"


class FakeDC:
    def __init__(self, cleanup):
        self.cleanup = cleanup

    def CreateCompatibleDC(self):
        return FakeDC(self.cleanup)

    def SelectObject(self, bitmap):
        return None

    def GetSafeHdc(self):
        return "HDC"

    def DeleteDC(self):
        self.cleanup.append("DeleteDC")


@pytest.fixture
def win32(monkeypatch):
    """把 capture_window_background 用到的 Win32 调用都换成假的。"""
    cleanup = []
    monkeypatch.setattr(screen_module.win32gui, "GetWindowDC", lambda hwnd: "WDC")
    monkeypatch.setattr(screen_module.win32gui, "SendMessage", lambda *args: None)
    monkeypatch.setattr(
        screen_module.win32gui, "DeleteObject", lambda handle: cleanup.append("DeleteObject")
    )
    monkeypatch.setattr(
        screen_module.win32gui, "ReleaseDC", lambda *args: cleanup.append("ReleaseDC")
    )
    monkeypatch.setattr(
        screen_module.win32ui, "CreateDCFromHandle", lambda handle: FakeDC(cleanup)
    )
    monkeypatch.setattr(screen_module.win32ui, "CreateBitmap", FakeBitmap)

    import ctypes

    def print_window(hwnd, hdc, flag, _result=[1]):
        return _result[0]

    monkeypatch.setattr(ctypes.windll.user32, "PrintWindow", print_window)
    return cleanup


class TestCaptureWindowBackground:
    def test_returns_the_full_region_when_no_crop_is_asked(self, win32):
        picture = ScreenSource.capture_window_background("HWND", (0, 0, 8, 4))

        assert picture.size == (8, 4)

    def test_crops_to_the_requested_box(self, win32):
        picture = ScreenSource.capture_window_background(
            "HWND", (100, 50, 1920, 1080), crop_region=(200, 100, 300, 200)
        )

        assert picture.size == (100, 100)

    def test_returns_none_when_the_crop_box_is_empty(self, win32):
        assert (
            ScreenSource.capture_window_background(
                "HWND", (0, 0, 100, 100), crop_region=(999, 999, 1000, 1000)
            )
            is None
        )

    def test_returns_none_when_printwindow_fails(self, win32, monkeypatch):
        import ctypes

        monkeypatch.setattr(ctypes.windll.user32, "PrintWindow", lambda *args: 0)

        assert ScreenSource.capture_window_background("HWND", (0, 0, 8, 4)) is None

    def test_releases_every_dc_even_when_it_fails(self, win32, monkeypatch):
        """失败路径也必须把 DC 还回去，否则一次失败泄漏一组句柄。"""
        import ctypes

        monkeypatch.setattr(ctypes.windll.user32, "PrintWindow", lambda *args: 0)

        ScreenSource.capture_window_background("HWND", (0, 0, 8, 4))

        assert sorted(win32) == [
            "DeleteDC",
            "DeleteDC",
            "DeleteObject",
            "ReleaseDC",
        ]


# ---------------------------------------------------------------------------
# take_screenshot：范围、通道序、重试
# ---------------------------------------------------------------------------


class FakeWindow:
    def __init__(self, rect=(0, 0, 1920, 1080), visible=True, hwnd="HWND"):
        self.rect = rect
        self.visible = visible
        self.hwnd = hwnd

    def get_rect(self):
        return self.rect

    def check_window_visibility(self):
        return self.visible


@pytest.fixture
def shot(monkeypatch):
    """一个窗口正常、截图立刻成功的 ScreenSource；返回被问到的裁剪框列表。"""
    asked = []
    monkeypatch.setattr(
        ScreenSource,
        "capture_window_background",
        staticmethod(
            lambda hwnd, region, crop_region=None: (
                asked.append(crop_region),
                Image.new("RGB", (2, 2), (10, 20, 30)),
            )[1]
        ),
    )
    monkeypatch.setattr(
        screen_module, "time", SimpleNamespace(sleep=lambda seconds: None)
    )
    source = ScreenSource(window=FakeWindow())
    return source, asked


class TestTakeScreenshot:
    def test_converts_pil_rgb_into_bgr(self, shot):
        """模板匹配是拿 cv2.imread 的约定去比的，通道反了整条识别链就废了。"""
        source, _ = shot

        frame, left, top, right, bottom = source.take_screenshot()

        assert frame[0, 0].tolist() == [30, 20, 10], "PIL 给 RGB，这里要 BGR"
        assert isinstance(frame, np.ndarray)

    def test_records_the_frame_and_its_region(self, shot):
        source, _ = shot

        frame, *region = source.take_screenshot()

        assert source.temp_screenshot == (frame, *region)
        assert region == [0, 0, 1920, 1080]

    def test_offset_narrows_the_captured_region(self, shot):
        source, asked = shot

        source.take_screenshot(offset=(10, 20, -30, -40))

        assert asked == [(10, 20, 1890, 1040)]

    def test_invalid_offset_falls_back_to_the_window_region(self, shot, log_records):
        source, asked = shot

        source.take_screenshot(offset=(5000, 0, 0, 0))

        assert asked == [(0, 0, 1920, 1080)]
        assert any("偏移值错误" in r["message"] for r in log_records)

    def test_retries_then_succeeds(self, monkeypatch):
        attempts = []

        def flaky(hwnd, region, crop_region=None):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("第一帧失败")
            return Image.new("RGB", (2, 2), (0, 0, 0))

        monkeypatch.setattr(ScreenSource, "capture_window_background", staticmethod(flaky))
        monkeypatch.setattr(
            screen_module, "time", SimpleNamespace(sleep=lambda seconds: None)
        )
        source = ScreenSource(window=FakeWindow())

        frame, *rest = source.take_screenshot(max_retries=3, retry_interval=0)

        assert len(attempts) == 2, "第一次失败、第二次成功"
        assert frame.shape == (2, 2, 3)

    def test_raises_after_exhausting_retries(self, monkeypatch):
        def always_fail(hwnd, region, crop_region=None):
            raise RuntimeError("总是失败")

        monkeypatch.setattr(
            ScreenSource, "capture_window_background", staticmethod(always_fail)
        )
        monkeypatch.setattr(
            screen_module, "time", SimpleNamespace(sleep=lambda seconds: None)
        )
        source = ScreenSource(window=FakeWindow())

        with pytest.raises(RuntimeError, match="最大重试次数"):
            source.take_screenshot(max_retries=1, retry_interval=0)


class TestHasFreshFrame:
    def test_false_before_anything_is_captured(self):
        source = ScreenSource(window=FakeWindow())
        assert source.has_fresh_frame() is False

    def test_true_after_a_capture(self, shot):
        source, _ = shot
        source.take_screenshot()
        assert source.has_fresh_frame() is True

    def test_false_for_a_malformed_cache(self):
        source = ScreenSource(window=FakeWindow())
        source.temp_screenshot = (0, 0, 0, 0, 0)
        assert source.has_fresh_frame() is False
