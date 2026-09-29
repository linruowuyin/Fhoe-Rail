"""utils/vision/blackscreen.py —— 黑屏判定与 finish_fighting 图片匹配。"""

from types import SimpleNamespace

import numpy as np
import pytest

import utils.vision.blackscreen as blackscreen_module
from utils.vision.blackscreen import BlackScreen
from utils.vision.img import Img


def stub_img(screenshot=None, scan_max_val=None):
    """构造一个只实现被测方法所需的 Img 替身。"""
    stub = SimpleNamespace()
    if screenshot is not None:
        stub.take_screenshot = lambda *args, **kwargs: (
            screenshot,
            0,
            0,
            screenshot.shape[1],
            screenshot.shape[0],
        )
    if scan_max_val is not None:
        stub.scan_screenshot = lambda target: {"max_val": scan_max_val}
    return stub


@pytest.fixture
def screen(make_instance, monkeypatch):
    monkeypatch.setattr(blackscreen_module.time, "sleep", lambda seconds: None)
    return make_instance(BlackScreen, image_folder="./picture/")


class TestPixelHelpers:
    def test_grayscale_uses_bgr_channel_weights(self):
        """纯红在 BGR2GRAY 下应得到 0.299*255 ≈ 76，用错色彩顺序会明显偏色。"""
        red_bgr = np.zeros((4, 4, 3), dtype=np.uint8)
        red_bgr[:, :] = (0, 0, 255)
        assert np.all(BlackScreen.convert_to_grayscale(red_bgr) == 76)

    def test_mean_pixel_value(self):
        grayscale = np.full((4, 4), 50, dtype=np.uint8)
        assert BlackScreen.calculate_mean_pixel_value(grayscale) == pytest.approx(50)


class TestCheckBlackscreen:
    def test_detects_black_screen(self, screen):
        screen.img = stub_img(screenshot=np.zeros((10, 10, 3), dtype=np.uint8))
        assert screen.check_blackscreen() is True

    def test_rejects_bright_screen(self, screen):
        bright = np.full((10, 10, 3), 200, dtype=np.uint8)
        screen.img = stub_img(screenshot=bright)
        assert screen.check_blackscreen() is False

    def test_threshold_is_configurable(self, screen):
        dim = np.full((10, 10, 3), 20, dtype=np.uint8)
        screen.img = stub_img(screenshot=dim)
        assert screen.check_blackscreen(threshold=10) is False
        assert screen.check_blackscreen(threshold=30) is True


class TestLoadFinishFightingImages:
    def test_lists_only_matching_prefix(self, screen, isolated_cwd):
        folder = isolated_cwd / "picture"
        folder.mkdir()
        (folder / "finish_fighting.png").write_bytes(b"")
        (folder / "finish_fighting2_1.png").write_bytes(b"")
        (folder / "other.png").write_bytes(b"")

        assert sorted(screen.load_finish_fighting_images()) == [
            "finish_fighting.png",
            "finish_fighting2_1.png",
        ]

    def test_returns_empty_for_empty_folder(self, screen, isolated_cwd):
        (isolated_cwd / "picture").mkdir()
        assert screen.load_finish_fighting_images() == []

    @pytest.mark.xfail(
        strict=True,
        reason="图片目录缺失时 os.listdir 抛 FileNotFoundError，"
        "而调用方 check_exit_blackscreen 本意是返回 True/False",
    )
    def test_missing_picture_folder_degrades_gracefully(self, screen):
        assert screen.load_finish_fighting_images() == []


class TestMatchFinishFightingImages:
    def test_returns_false_when_a_target_matches(self, screen, monkeypatch):
        monkeypatch.setattr(
            Img, "get_img", staticmethod(lambda path: np.zeros((4, 4, 3), np.uint8))
        )
        screen.img = stub_img(scan_max_val=0.95)

        assert screen.match_finish_fighting_images(["a.png"]) is False

    def test_returns_true_after_exhausting_attempts(self, screen, monkeypatch):
        monkeypatch.setattr(
            Img, "get_img", staticmethod(lambda path: np.zeros((4, 4, 3), np.uint8))
        )
        screen.img = stub_img(scan_max_val=0.1)

        assert screen.match_finish_fighting_images(["a.png"], max_attempts=2) is True

    def test_empty_image_list_is_not_a_match(self, screen):
        screen.img = stub_img(scan_max_val=0.99)
        assert screen.match_finish_fighting_images([]) is True


class TestCheckExitBlackscreen:
    def test_true_while_screen_is_black(self, screen):
        screen.check_blackscreen = lambda threshold=10: True
        assert screen.check_exit_blackscreen() is True

    def test_falls_through_to_image_matching(self, screen):
        screen.check_blackscreen = lambda threshold=10: False
        screen.load_finish_fighting_images = lambda: ["a.png"]
        screen.match_finish_fighting_images = lambda images: False
        assert screen.check_exit_blackscreen() is False


class TestRunBlackscreenCalTime:
    def test_returns_elapsed_time(self, screen):
        sequence = iter([True, True, False])
        screen.check_exit_blackscreen = lambda threshold=10: next(sequence, False)

        assert screen.run_blackscreen_cal_time() >= 1
