"""utils/vision/images.py —— 模板图的加载、缓存与**身份反查**。

`path_of` 是给「匹配那一层」用的：它只拿得到 ndarray，靠对象身份认回文件。放在这里而不是
matcher 里，是因为身份表必须和缓存同生共死（缓存持有强引用，`id` 才不会被回收复用）。
"""

import os

import numpy as np
import pytest
from PIL import Image

from utils.vision import images


@pytest.fixture(autouse=True)
def clean_cache():
    images.clear_cache()
    yield
    images.clear_cache()


@pytest.fixture
def picture(tmp_path, monkeypatch):
    """把相对路径解析到临时目录，免得读到仓库里真正的 picture/。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "picture").mkdir()
    return tmp_path / "picture"


def write(path, color=(10, 20, 30)):
    Image.new("RGB", (8, 6), color).save(path)


class TestPathOf:
    def test_finds_the_file_a_loaded_image_came_from(self, picture):
        write(picture / "alpha.webp")

        img = images.get_img("picture/alpha.webp")

        assert os.path.basename(images.path_of(img)) == "alpha.webp"

    def test_another_spelling_of_the_same_file_still_resolves(self, picture):
        """`./picture/x.png` 这种写法（`Img.ui_images` 用的就是它）也要认得出。

        注意它和图里另一条路径**不是同一个对象** —— 缓存键是 `resolve_path` 之后的原样
        字符串，`./a` 与 `a` 各占一条。收集器用的是 basename，所以认得出来就够了。
        """
        write(picture / "alpha.webp")

        img = images.get_img("./picture/alpha.png")  # 后缀按 webp > png > jpg 找回来

        assert os.path.basename(images.path_of(img)) == "alpha.webp"

    def test_an_unknown_array_has_no_path(self):
        assert images.path_of(np.zeros((4, 4, 3), np.uint8)) is None

    def test_none_has_no_path(self):
        assert images.path_of(None) is None

    def test_a_derived_array_has_no_path(self, picture):
        """反色 / 旋转造出来的新数组不在表里 —— 收集器据此跳过。"""
        write(picture / "alpha.webp")
        img = images.get_img("picture/alpha.webp")

        assert images.path_of(np.ascontiguousarray(img[::-1])) is None

    def test_clearing_the_cache_clears_the_identity_table(self, picture):
        """R15：身份表只对缓存里活着的数组有意义，缓存清了它也得清。"""
        write(picture / "alpha.webp")
        img = images.get_img("picture/alpha.webp")

        images.clear_cache()

        assert images.path_of(img) is None
