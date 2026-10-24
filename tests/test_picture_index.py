"""图片资源 ID 解析与校验。

钉住 R25 的第二层语义：地图 JSON 里的 `picture\\xxx.png` 是**资源 ID**，
文件搬进子目录后仍按 stem 解析；前提是 stem 全局唯一（`tools/validate_pictures.py`）。
"""

import pytest

from tools import validate_pictures as validator
from utils.vision import assets
from utils.vision import images


def write_image(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.fixture
def picture_root(tmp_path, monkeypatch):
    """把 `assets.PICTURE_ROOT` 指到临时目录，并清掉 stem 索引缓存。"""
    root = tmp_path / "picture"
    root.mkdir()
    monkeypatch.setattr(assets, "PICTURE_ROOT", str(root))
    images.clear_cache()
    yield root
    images.clear_cache()


class TestScanPictureFiles:
    def test_index_uses_stem_and_prefers_webp(self, tmp_path):
        write_image(tmp_path / "ui" / "transfer.webp")
        write_image(tmp_path / "ui" / "transfer.png")

        index, duplicates = assets.scan_picture_files(tmp_path)

        assert index["transfer"] == str(tmp_path / "ui" / "transfer.webp")
        assert duplicates == {}, "同一目录的 png/webp 是同一张图，不算重名"

    def test_keys_are_case_insensitive(self, tmp_path):
        write_image(tmp_path / "ui" / "F_Teleport.webp")

        index, _ = assets.scan_picture_files(tmp_path)

        assert index["f_teleport"] == str(tmp_path / "ui" / "F_Teleport.webp")

    def test_new_pic_samples_are_skipped(self, tmp_path):
        write_image(tmp_path / "new_pic" / "20261024" / "transfer.webp")
        write_image(tmp_path / "transfer.webp")

        index, duplicates = assets.scan_picture_files(tmp_path)

        assert index == {"transfer": str(tmp_path / "transfer.webp")}
        assert duplicates == {}

    def test_same_stem_in_two_directories_is_a_duplicate(self, tmp_path):
        write_image(tmp_path / "a" / "point.webp")
        write_image(tmp_path / "b" / "point.png")

        index, duplicates = assets.scan_picture_files(tmp_path)

        assert set(duplicates) == {"point"}
        assert len(duplicates["point"]) == 2
        # 索引仍给出确定的结果（webp 优先），但校验会把它拦下
        assert index["point"] == str(tmp_path / "a" / "point.webp")

    def test_only_picture_extensions_are_indexed(self, tmp_path):
        write_image(tmp_path / "notes.txt")
        write_image(tmp_path / "logo.ico")

        index, _ = assets.scan_picture_files(tmp_path)

        assert index == {}


class TestResolveByStem:
    def test_moved_file_resolves_from_a_json_style_reference(self, picture_root):
        target = picture_root / "map_ui" / "transfer.webp"
        write_image(target)

        # 地图 JSON 里的写法：反斜杠 + 旧后缀 + 已经不在根目录
        assert images.resolve_path("picture\\transfer.png") == str(target)

    def test_reference_is_case_insensitive(self, picture_root):
        target = picture_root / "ui" / "F_Teleport.webp"
        write_image(target)

        assert images.resolve_path("picture\\f_teleport.png") == str(target)

    def test_absolute_path_under_the_root_also_resolves(self, picture_root):
        target = picture_root / "ui" / "setting_icon.webp"
        write_image(target)

        ref = str(picture_root / "missing" / "setting_icon.png")

        assert images.resolve_path(ref) == str(target)

    def test_literal_path_still_wins(self, picture_root):
        write_image(picture_root / "ui" / "round.webp")
        literal = picture_root / "round.png"
        write_image(literal)

        # 字面路径存在时走第一步，不查索引（此时 stem 重名，校验器会报错）
        assert images.resolve_path(str(literal)) == str(literal)

    def test_paths_outside_picture_root_do_not_fall_back(self, picture_root):
        write_image(picture_root / "ui" / "transfer.webp")

        assert images.resolve_path("./elsewhere/transfer.png") == "./elsewhere/transfer.png"

    def test_unknown_stem_returns_the_original(self, picture_root):
        assert images.resolve_path("picture\\nope.png") == "picture\\nope.png"

    def test_cache_reset_picks_up_a_moved_file(self, picture_root):
        old = picture_root / "transfer.webp"
        write_image(old)
        assert images.resolve_path("picture\\transfer.png") == str(old)

        new = picture_root / "map_ui" / "transfer.webp"
        new.parent.mkdir()
        old.rename(new)
        images.clear_cache()

        assert images.resolve_path("picture\\transfer.png") == str(new)


class TestValidator:
    def test_duplicates_are_reported(self, tmp_path, monkeypatch):
        write_image(tmp_path / "a" / "point.webp")
        write_image(tmp_path / "b" / "point.webp")
        (tmp_path / "map").mkdir()
        monkeypatch.setattr(assets, "PICTURE_ROOT", str(tmp_path))
        images.clear_cache()

        errors, _ = validator.check(map_dir=tmp_path / "map")

        assert any("重名" in error for error in errors)

    def test_repo_passes_all_checks(self, repo_root):
        """全库 877 张地图、3000+ 处引用，必须全部可解析。"""
        errors, stats = validator.check()

        assert errors == []
        assert stats["images"] > 300
        assert stats["maps"] > 800
        assert stats["refs"] > 3000

    def test_map_refs_extraction_sees_keys_and_values(self):
        data = {
            "name": "测试",
            "start": ["picture\\transfer.png", {"picture\\1floor.png": 1}],
            "map": [{"picture\\map_1-2_point_1.png": 1.5, "w": 1}],
        }

        assert validator.picture_refs(data) == [
            "picture\\1floor.png",
            "picture\\map_1-2_point_1.png",
            "picture\\transfer.png",
        ]
