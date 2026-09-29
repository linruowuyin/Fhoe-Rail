"""utils/vision/get_angle.py —— 箭头最远点与朝向角度计算。"""

import numpy as np
import pytest

import utils.vision.get_angle as get_angle_module
from utils.vision.get_angle import get_angle, get_furthest_point
from utils.vision.img import Img

CYAN_BGR = (255, 255, 0)  # OpenCV HSV 下 H=90，落在青色掩膜区间
X0, Y0, SIZE = 117, 128, 47


def build_screenshot(blobs):
    """构造一张至少 (Y0+SIZE, X0+SIZE) 的 BGR 截图，并在裁剪区内画青色方块。"""
    image = np.zeros((Y0 + SIZE, X0 + SIZE, 3), dtype=np.uint8)
    for top, left, height, width in blobs:
        image[Y0 + top : Y0 + top + height, X0 + left : X0 + left + width] = CYAN_BGR
    return image


class TestGetFurthestPoint:
    def test_picks_the_most_distant_point(self):
        points = np.array([[0, 0], [10, 0], [10, 10]])
        assert list(get_furthest_point(points)) == [0, 0]

    def test_single_point_returns_itself(self):
        assert list(get_furthest_point(np.array([[3, 4]]))) == [3, 4]

    def test_equidistant_points_keep_the_first(self):
        points = np.array([[0, 0], [2, 0], [1, 1]])
        assert list(get_furthest_point(points)) == [0, 0]


class TestGetAngle:
    @pytest.fixture
    def stub_screenshot(self, monkeypatch):
        def _install(blobs):
            image = build_screenshot(blobs)
            monkeypatch.setattr(Img, "get_img", staticmethod(lambda path: image))
            return image

        return _install

    def test_returns_false_when_no_cyan_arrow(self, stub_screenshot, capsys):
        stub_screenshot([])

        assert get_angle(use_sample_image=True) is False
        assert capsys.readouterr().out == ""

    def test_returns_false_when_multiple_arrows_detected(self, stub_screenshot):
        """代码“暴力断定只有一个青色箭头”，多于一个直接放弃。"""
        stub_screenshot([(5, 5, 8, 8), (25, 25, 8, 8)])

        assert get_angle(use_sample_image=True) is False

    def test_returns_float_for_single_arrow(self, stub_screenshot, capsys):
        stub_screenshot([(18, 18, 11, 11)])

        angle = get_angle(use_sample_image=True)

        assert isinstance(angle, float)
        assert -180 <= angle <= 180
        assert capsys.readouterr().out.strip(), "函数里有遗留的裸 print(angle)"

    def test_angle_is_deterministic(self, stub_screenshot):
        stub_screenshot([(18, 18, 11, 11)])
        first = get_angle(use_sample_image=True)
        second = get_angle(use_sample_image=True)
        assert first == second

    def test_debug_mode_does_not_change_the_result(
        self, stub_screenshot, monkeypatch
    ):
        stub_screenshot([(18, 18, 11, 11)])
        shown = []
        monkeypatch.setattr(
            get_angle_module.cv2, "imshow", lambda name, image: shown.append(name)
        )
        monkeypatch.setattr(get_angle_module.cv2, "waitKey", lambda delay: None)

        get_angle(debug=True, use_sample_image=True)

        assert shown == ["result"]

    def test_missing_sample_image_raises(self, monkeypatch):
        """Img.get_img 返回 None 时直接下标切片，会抛 TypeError 而不是可读错误。"""
        monkeypatch.setattr(Img, "get_img", staticmethod(lambda path: None))
        with pytest.raises(TypeError):
            get_angle(use_sample_image=True)
