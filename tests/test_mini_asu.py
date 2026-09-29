"""utils/vision/mini_asu.py —— 小地图箭头角度识别。"""

import numpy as np
import pytest

import utils.vision.mini_asu as mini_asu_module
from utils.vision.img import Img
from utils.vision.mini_asu import ASU


@pytest.fixture
def asu():
    instance = ASU()
    instance.screen = np.zeros((300, 300, 3), dtype=np.uint8)
    return instance


@pytest.fixture
def stub_arrow(monkeypatch):
    monkeypatch.setattr(
        Img, "get_img", staticmethod(lambda path: np.full((20, 20, 3), 100, np.uint8))
    )


class TestRotationHelpers:
    def test_zero_rotation_is_identity(self, asu):
        assert np.allclose(asu.handle_rotate_val(50, 50, 0), [[1, 0, 0], [0, 1, 0]])

    def test_image_rotate_preserves_shape(self, asu):
        source = np.zeros((30, 40, 3), dtype=np.uint8)
        assert asu.image_rotate(source, 30).shape == source.shape

    def test_zero_rotation_preserves_content(self, asu):
        source = np.full((10, 10, 3), 7, dtype=np.uint8)
        assert np.array_equal(asu.image_rotate(source, 0), source)


class TestGetNowDirec:
    def test_returns_zero_when_no_arrow_present(self, asu, stub_arrow):
        assert asu.get_now_direc() == 0

    def test_returns_an_int_angle(self, asu, stub_arrow):
        angle = asu.get_now_direc()
        assert isinstance(angle, int)
        assert 0 <= angle < 360

    def test_slices_the_expected_minimap_region(self, asu, stub_arrow):
        """loc_scr 固定取 screen[101:241, 94:224]，形状变了就会静默匹配到错误区域。"""
        captured = {}
        real_match = mini_asu_module.cv.matchTemplate

        def spy(image, template, method):
            captured["shape"] = image.shape
            return real_match(image, template, method)

        monkeypatch_target = mini_asu_module.cv
        original = monkeypatch_target.matchTemplate
        monkeypatch_target.matchTemplate = spy
        try:
            asu.get_now_direc()
        finally:
            monkeypatch_target.matchTemplate = original

        assert captured["shape"] == (140, 130, 3)
