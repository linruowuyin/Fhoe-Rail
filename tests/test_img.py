"""utils/drivers/img.py —— 图片加载缓存、模板匹配、截图范围计算。"""

import os

import cv2
import numpy as np
import pytest

from utils.vision.img import Img


@pytest.fixture
def img_factory(monkeypatch, fake_window_factory):
    """构造 Img 但把 Window 换成替身，并把默认的 11 张图片列表清空。"""

    def _make(image_paths=None, window=None):
        monkeypatch.setattr(
            "utils.drivers.screen.Window",
            lambda *args, **kwargs: window or fake_window_factory(),
        )
        return Img(image_paths=image_paths if image_paths is not None else {})

    return _make


def save_image(path, shape=(30, 40, 3), value=120):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full(shape, value, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)
    return image


class TestResolvePath:
    def test_prefers_webp(self, tmp_path):
        # resolve_path 只做 os.path.isfile 判断，不需要内容真实可解码
        (tmp_path / "a.webp").touch()
        save_image(tmp_path / "a.png")
        assert Img.resolve_path(str(tmp_path / "a.png")) == str(tmp_path / "a.webp")

    def test_falls_back_to_png(self, tmp_path):
        (tmp_path / "a.png").touch()
        assert Img.resolve_path(str(tmp_path / "a.jpg")) == str(tmp_path / "a.png")

    def test_falls_back_to_jpg(self, tmp_path):
        (tmp_path / "a.jpg").touch()
        assert Img.resolve_path(str(tmp_path / "a.png")) == str(tmp_path / "a.jpg")

    def test_returns_input_when_nothing_exists(self, tmp_path):
        missing = str(tmp_path / "nope.png")
        assert Img.resolve_path(missing) == missing

    def test_non_image_extension_untouched(self, tmp_path):
        target = str(tmp_path / "a.txt")
        assert Img.resolve_path(target) == target


class TestGetImg:
    def test_missing_file_returns_none(self, tmp_path, log_records):
        assert Img.get_img(str(tmp_path / "gone.png")) is None
        assert any(r["level"].name == "ERROR" for r in log_records)

    def test_loads_existing_file(self, tmp_path):
        save_image(tmp_path / "a.png")
        loaded = Img.get_img(str(tmp_path / "a.png"))
        assert isinstance(loaded, np.ndarray)

    def test_second_call_is_served_from_cache(self, tmp_path):
        save_image(tmp_path / "a.png")
        first = Img.get_img(str(tmp_path / "a.png"))
        assert Img.get_img(str(tmp_path / "a.png")) is first

    def test_cache_invalidated_when_file_changes(self, tmp_path):
        path = tmp_path / "a.png"
        save_image(path, value=10)
        first = Img.get_img(str(path))

        save_image(path, value=200)
        os.utime(path, (os.path.getmtime(path) + 10, os.path.getmtime(path) + 10))

        second = Img.get_img(str(path))
        assert second is not first
        assert second.mean() == pytest.approx(200, abs=1)

    def test_corrupt_file_returns_none(self, tmp_path, log_records):
        path = tmp_path / "broken.png"
        path.write_bytes(b"definitely not a png")
        assert Img.get_img(str(path)) is None

    def test_resolves_sibling_extension(self, tmp_path):
        save_image(tmp_path / "a.png")
        assert Img.get_img(str(tmp_path / "a.webp")) is not None


class TestLoadImages:
    def test_sets_attribute_for_present_image(self, tmp_path, img_factory):
        save_image(tmp_path / "hit.png")
        img = img_factory({"hit": str(tmp_path / "hit.png")})
        assert isinstance(img.hit, np.ndarray)

    def test_missing_image_logs_warning_and_skips_attribute(
        self, tmp_path, img_factory, log_records
    ):
        img = img_factory({"miss": str(tmp_path / "nope.png")})
        assert not hasattr(img, "miss")
        assert any("miss" in r["message"] for r in log_records)


class TestMatchScreenshot:
    def test_reports_match_position_in_screen_coordinates(self):
        screenshot = np.zeros((60, 80, 3), dtype=np.uint8)
        screenshot[20:30, 30:40] = 255
        prepared = np.full((10, 10, 3), 255, dtype=np.uint8)

        result = Img.match_screenshot(screenshot, prepared, left=100, top=200)

        assert result["max_loc"] == (30 + 100, 20 + 200)
        assert result["max_val"] == pytest.approx(1.0, abs=1e-5)

    def test_returns_all_expected_keys(self):
        screenshot = np.zeros((20, 20, 3), dtype=np.uint8)
        result = Img.match_screenshot(screenshot, np.zeros((5, 5, 3), np.uint8), 0, 0)
        assert set(result) == {"screenshot", "min_val", "max_val", "min_loc", "max_loc"}

    def test_offsets_are_independent_for_x_and_y(self):
        screenshot = np.zeros((50, 50, 3), dtype=np.uint8)
        screenshot[10:15, 5:10] = 255
        prepared = np.full((5, 5, 3), 255, dtype=np.uint8)

        result = Img.match_screenshot(screenshot, prepared, left=7, top=11)

        assert result["max_loc"] == (5 + 7, 10 + 11)


class TestImgCenterPoint:
    def test_returns_center_of_matched_region(self):
        assert Img.img_center_point({"max_loc": (100, 200)}, (40, 60, 3)) == (130, 220)

    def test_zero_position(self):
        assert Img.img_center_point({"max_loc": (0, 0)}, (10, 20, 3)) == (10, 5)


class TestCalScreenshot:
    def test_exact_1920x1080_window_is_used_as_is(self, img_factory, fake_window_factory):
        img = img_factory(window=fake_window_factory(rect=(100, 50, 2020, 1130)))
        assert img.cal_screenshot() == (100, 50, 2020, 1130)

    def test_larger_window_is_centred_with_letterbox_trimmed(
        self, img_factory, fake_window_factory
    ):
        img = img_factory(window=fake_window_factory(rect=(0, 0, 2560, 1440)))
        left, top, right, bottom = img.cal_screenshot()
        assert (right - left, bottom - top) == (1920, 1080)
        assert (left, top) == (320, 40)

    def test_smaller_window_yields_oversized_region(self, img_factory, fake_window_factory):
        """分辨率低于 1920x1080 时不会报错，而是算出一个比窗口还大的区域。

        get_width.py 只对此打警告、不做拦截，所以截图区域可能超出窗口边界。
        """
        img = img_factory(window=fake_window_factory(rect=(0, 0, 1600, 900)))
        left, top, right, bottom = img.cal_screenshot()
        assert (right - left, bottom - top) == (1920, 1080)
        assert left < 0 or right > 1600 or top < 0 or bottom > 900


class TestTakeScreenshot:
    @pytest.mark.xfail(
        strict=True,
        reason="check_window_visibility() 为 False 时函数没有任何 return，隐式返回 None；"
        "而所有调用点都在做 5 元组解包，会抛 TypeError 而不是给出可读的错误",
    )
    def test_raises_when_window_invisible(self, img_factory, fake_window_factory):
        img = img_factory(window=fake_window_factory(visible=False))
        with pytest.raises(Exception):
            img.take_screenshot(max_retries=0, retry_interval=0)


class TestScanTempScreenshot:
    def test_takes_a_screenshot_when_cache_is_uninitialised(self, img_factory):
        img = img_factory()
        assert isinstance(img.temp_screenshot, tuple)  # 初始值 (0,0,0,0,0)

        screen = np.zeros((20, 20, 3), dtype=np.uint8)
        screen[5:10, 5:10] = 255
        taken = []

        def fake_take_screenshot(*args, **kwargs):
            taken.append(1)
            img.temp_screenshot = (screen, 0, 0, 20, 20)
            return img.temp_screenshot

        # 注意：要替换的是截图源，不是门面 —— scan_temp_screenshot 走
        # Matcher -> ScreenSource，替换 Img.take_screenshot 会被绕过
        img.screen.take_screenshot = fake_take_screenshot
        result = img.scan_temp_screenshot(np.full((5, 5, 3), 255, dtype=np.uint8))

        assert taken == [1]
        assert result["max_loc"] == (5, 5)

    def test_reuses_cached_screenshot(self, img_factory):
        img = img_factory()
        screen = np.zeros((20, 20, 3), dtype=np.uint8)
        screen[5:10, 5:10] = 255
        img.temp_screenshot = (screen, 0, 0, 20, 20)

        taken = []
        img.screen.take_screenshot = lambda *a, **k: taken.append(1)

        img.scan_temp_screenshot(np.full((5, 5, 3), 255, dtype=np.uint8))

        assert taken == []


class TestHaveScreenshot:
    """have_screenshot 内部调的是 matcher.scan_screenshot，替换门面会被绕过。"""

    def test_true_when_any_image_exceeds_threshold(self, img_factory):
        img = img_factory()
        img.matcher.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": prepared["val"]
        }
        prepared = [{"val": 0.5}, {"val": 0.99}]
        assert img.have_screenshot(prepared, threshold=0.9) is True

    def test_false_when_all_below_threshold(self, img_factory):
        img = img_factory()
        img.matcher.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": prepared["val"]
        }
        assert img.have_screenshot([{"val": 0.1}], threshold=0.9) is False


class TestRotationHelpers:
    def test_zero_rotation_matrix_is_identity(self, img_factory):
        img = img_factory()
        assert np.allclose(img.handle_rotate_val(50, 50, 0), [[1, 0, 0], [0, 1, 0]])

    def test_rotate_preserves_shape(self, img_factory):
        img = img_factory()
        source = np.zeros((40, 60, 3), dtype=np.uint8)
        assert img.image_rotate(source, 45).shape == source.shape

    def test_zero_rotation_preserves_content(self, img_factory):
        img = img_factory()
        source = np.full((20, 30, 3), 200, dtype=np.uint8)
        assert np.array_equal(img.image_rotate(source, 0), source)


class TestImgBitwiseCheck:
    """注意：这几个用例要替换的是**图片加载函数本身**（vision/images.get_img），
    不是 Img.get_img 这个门面转发 —— Matcher 内部直接调 image_library，
    替换门面会被绕过。"""

    @staticmethod
    def stub_image(monkeypatch):
        save = np.full((5, 5, 3), 100, dtype=np.uint8)
        monkeypatch.setattr(
            "utils.vision.images.get_img", lambda path: save.copy()
        )

    def test_returns_true_when_original_matches_better(self, img_factory, monkeypatch):
        img = img_factory()
        self.stub_image(monkeypatch)
        img.matcher.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": 0.4 if prepared.mean() > 100 else 0.9
        }
        assert img.img_bitwise_check("./picture/x.png") is True

    def test_returns_false_when_inverted_matches_better(self, img_factory, monkeypatch):
        img = img_factory()
        self.stub_image(monkeypatch)
        img.matcher.scan_screenshot = lambda prepared, offset=(0, 0, 0, 0): {
            "max_val": 0.9 if prepared.mean() > 100 else 0.4
        }
        assert img.img_bitwise_check("./picture/x.png") is False
