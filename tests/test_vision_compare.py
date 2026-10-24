"""utils/vision/compare.py —— 固定位置相似度与整帧平移估计。"""

import cv2
import numpy as np
import pytest

from utils.vision.compare import (
    equivalent_duration,
    estimate_shift,
    projection,
    ratio_along,
    scene_score,
)


def texture(seed=0, size=(200, 300)):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (*size, 3), dtype=np.uint8)


def shifted(image, dx, dy):
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    height, width = image.shape[:2]
    return cv2.warpAffine(
        image, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE
    )


class TestSceneScore:
    def test_identical_images_score_one(self):
        image = texture()
        assert scene_score(image, image.copy()) == pytest.approx(1.0, abs=1e-6)

    def test_shifted_image_scores_lower_at_fixed_position(self):
        image = texture()
        score = scene_score(image, shifted(image, 12, -7))
        assert score < 0.5

    def test_flat_image_does_not_produce_nan(self):
        image = np.full((40, 40, 3), 128, dtype=np.uint8)
        assert scene_score(image, image.copy()) == 0.0

    def test_shape_mismatch_is_refused(self):
        with pytest.raises(ValueError):
            scene_score(texture(size=(40, 40)), texture(size=(41, 41)))


class TestEstimateShift:
    def test_recovers_translation(self):
        image = texture()
        (dx, dy), response = estimate_shift(image, shifted(image, 12, -7))
        assert dx == pytest.approx(12, abs=1.0)
        assert dy == pytest.approx(-7, abs=1.0)
        assert response > 0.5

    def test_shift_is_reversed_when_arguments_swap(self):
        image = texture()
        forward, _ = estimate_shift(image, shifted(image, 12, -7))
        backward, _ = estimate_shift(shifted(image, 12, -7), image)
        assert forward[0] == pytest.approx(-backward[0], abs=0.1)
        assert forward[1] == pytest.approx(-backward[1], abs=0.1)

    def test_shape_mismatch_is_refused(self):
        with pytest.raises(ValueError):
            estimate_shift(texture(size=(40, 40)), texture(size=(41, 41)))


class TestEquivalentDuration:
    def test_linear_ratio(self):
        # E 位移 120px，0.8 秒 ss 位移 100px → E ≈ 0.96 秒
        duration, cosine = equivalent_duration((120, 0), (100, 0), 0.8)
        assert duration == pytest.approx(0.96)
        assert cosine == pytest.approx(1.0)

    def test_opposite_direction_gives_negative_cosine(self):
        duration, cosine = equivalent_duration((120, 0), (-100, 0), 0.8)
        assert duration == pytest.approx(-0.96)
        assert cosine < -0.9

    def test_zero_sample_shift_is_refused(self):
        duration, cosine = equivalent_duration((120, 0), (0, 0), 0.8)
        assert duration == 0.0
        assert cosine == 1.0


class TestRatioAlong:
    def test_half_of_baseline(self):
        ratio, cosine = ratio_along((50, 0), (100, 0))
        assert ratio == pytest.approx(0.5)
        assert cosine == pytest.approx(1.0)

    def test_opposite_direction(self):
        ratio, cosine = ratio_along((-50, 0), (100, 0))
        assert ratio == pytest.approx(-0.5)
        assert cosine == pytest.approx(-1.0)

    def test_zero_baseline(self):
        assert ratio_along((50, 0), (0, 0)) == (0.0, 0.0)


class TestProjection:
    def test_projects_onto_direction(self):
        assert projection((3, 4), (1, 0)) == pytest.approx(3)
        assert projection((3, 4), (0, 2)) == pytest.approx(4)

    def test_zero_direction(self):
        assert projection((3, 4), (0, 0)) == 0.0
