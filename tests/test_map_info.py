"""utils/core/map_info.py —— 地图文件名解析、目录扫描与缓存。"""

import pytest

from utils.config.config import ConfigurationManager
from utils.core.map_info import MapInfo


def write_map_content(root, version, filename, data):
    folder = root / "map" / version
    folder.mkdir(parents=True, exist_ok=True)
    import json

    path = folder / filename
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_map_file(root, version, filename, name="1-1 空间站「黑塔」", author="tester"):
    return write_map_content(
        root,
        version,
        filename,
        {"name": name, "author": author, "start": [], "map": []},
    )


class TestExtractKeys:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("map_1-1_0.json", ("1", "1_0")),
            ("map_12-3_4.json", ("12", "3_4")),
            ("map_2-10_1.json", ("2", "10_1")),
        ],
    )
    def test_splits_filename_into_keys(self, filename, expected):
        assert MapInfo.extract_keys(filename) == expected

    def test_filename_without_dash_raises(self):
        """命名不符合约定时直接抛 ValueError —— 一个坏文件名会让整个版本加载失败。"""
        with pytest.raises(ValueError):
            MapInfo.extract_keys("map_11_0.json")


class TestSortJsonFiles:
    def test_sorts_numerically_not_lexically(self):
        files = ["map_1-10_0.json", "map_1-2_0.json", "map_1-1_0.json"]
        assert MapInfo.sort_json_files(files) == [
            "map_1-1_0.json",
            "map_1-2_0.json",
            "map_1-10_0.json",
        ]

    def test_sorts_across_planets(self):
        files = ["map_3-1_0.json", "map_1-2_0.json", "map_2-1_0.json"]
        assert MapInfo.sort_json_files(files) == [
            "map_1-2_0.json",
            "map_2-1_0.json",
            "map_3-1_0.json",
        ]

    def test_empty_list(self):
        assert MapInfo.sort_json_files([]) == []


class TestFormatMapDataFirstName:
    def test_builds_prefixed_display_name(self):
        assert (
            MapInfo.format_map_data_first_name("1", "1", "1-1 空间站「黑塔」")
            == "1-1 1"
        )

    def test_strips_spaces_before_truncating(self):
        assert MapInfo.format_map_data_first_name("2", "3", "2-3 雅利洛-Ⅵ 大矿区") == "2-3 2"

    def test_map_name_without_dash_raises(self):
        with pytest.raises(ValueError):
            MapInfo.format_map_data_first_name("1", "1", "没有分隔符的名字")


class TestReadMapsVersions:
    def test_lists_subdirectories(self, isolated_cwd):
        (isolated_cwd / "map" / "default").mkdir(parents=True)
        (isolated_cwd / "map" / "HuangQuan").mkdir()
        (isolated_cwd / "map" / "readme.txt").write_text("x", encoding="utf-8")

        assert sorted(MapInfo.read_maps_versions()) == ["HuangQuan", "default"]

    def test_missing_map_dir_raises(self, isolated_cwd):
        with pytest.raises(FileNotFoundError):
            MapInfo.read_maps_versions()

    def test_missing_map_dir_logs_error(self, isolated_cwd, log_records):
        with pytest.raises(FileNotFoundError):
            MapInfo.read_maps_versions()
        assert any("地图文件目录不存在" in r["message"] for r in log_records)


class TestReadMaps:
    def test_reads_single_file(self, isolated_cwd):
        write_map_file(isolated_cwd, "default", "map_1-1_0.json")

        json_files, map_list_map, version = MapInfo.read_maps("default")

        assert json_files == ["map_1-1_0.json"]
        assert version == "default"
        assert map_list_map == {"1": {"1_0": ["1-1 空间站「黑塔」", "1-1 1"]}}

    def test_groups_multiple_submaps_under_one_planet(self, isolated_cwd):
        write_map_file(isolated_cwd, "default", "map_1-1_0.json")
        write_map_file(isolated_cwd, "default", "map_1-2_0.json")

        _, map_list_map, _ = MapInfo.read_maps("default")

        assert list(map_list_map) == ["1"]
        assert sorted(map_list_map["1"]) == ["1_0", "2_0"]

    def test_missing_version_dir_raises(self, isolated_cwd):
        (isolated_cwd / "map").mkdir()
        with pytest.raises(FileNotFoundError):
            MapInfo.read_maps("nope")

    def test_result_is_cached_until_directory_changes(self, isolated_cwd):
        write_map_file(isolated_cwd, "default", "map_1-1_0.json")

        first = MapInfo.read_maps("default")
        second = MapInfo.read_maps("default")

        assert first is second, "目录 mtime 未变时应复用上次的解析结果"

    def test_cache_is_invalidated_when_a_file_is_added(self, isolated_cwd):
        import os

        write_map_file(isolated_cwd, "default", "map_1-1_0.json")
        first = MapInfo.read_maps("default")

        write_map_file(isolated_cwd, "default", "map_2-1_0.json")
        folder = isolated_cwd / "map" / "default"
        os.utime(folder, (os.path.getmtime(folder) + 10, os.path.getmtime(folder) + 10))

        second = MapInfo.read_maps("default")

        assert second is not first
        assert "map_2-1_0.json" in second[0]

    def test_corrupt_json_propagates(self, isolated_cwd, log_records):
        folder = isolated_cwd / "map" / "default"
        folder.mkdir(parents=True)
        (folder / "map_1-1_0.json").write_text("{ broken", encoding="utf-8")

        with pytest.raises(Exception):
            MapInfo.read_maps("default")
        assert any("处理地图文件失败" in r["message"] for r in log_records)


class TestMapInfoProperties:
    @pytest.fixture
    def info(self, make_instance, isolated_cwd):
        write_map_file(isolated_cwd, "default", "map_1-1_0.json")
        write_map_file(isolated_cwd, "default", "map_2-1_0.json")
        return make_instance(
            MapInfo, cfg=ConfigurationManager(), _map_version="default"
        )

    def test_map_list_is_sorted(self, info):
        assert info.map_list == ["map_1-1_0.json", "map_2-1_0.json"]

    def test_map_list_map_groups_by_planet(self, info):
        assert sorted(info.map_list_map) == ["1", "2"]

    def test_map_version_tracks_config_changes(self, info, set_config):
        assert info.map_version == "default"
        set_config(info.cfg, map_version="HuangQuan")
        assert info.map_version == "HuangQuan"

    def test_map_version_is_cached_when_config_unchanged(self, info):
        assert info.map_version is info.map_version


class TestReadMapDataValidation:
    """`read_map_data` 读完地图就交给 `core/schema.py` 校验。

    结果**只记录、不抛出**——633 张图里坏一张，不该让整个程序起不来。
    """

    @staticmethod
    def _validation_records(log_records, level=None):
        return [
            r
            for r in log_records
            if "地图校验" in r["message"]
            and (level is None or r["level"].name == level)
        ]

    def test_valid_map_logs_nothing(self, isolated_cwd, log_records):
        write_map_file(isolated_cwd, "default", "map_1-1_0.json")

        MapInfo.read_maps("default")

        assert self._validation_records(log_records) == []

    def test_modifier_as_first_key_is_logged_as_error(self, isolated_cwd, log_records):
        """这个错今天不报——分发表只是静默把 "drag" 当成图片路径去查。"""
        write_map_content(
            isolated_cwd,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [{"drag": 1.5, "picture\\x.png": 1.0}],
                "map": [],
            },
        )

        MapInfo.read_maps("default")

        errors = self._validation_records(log_records, "ERROR")
        assert len(errors) == 1
        assert "map_1-1_0.json" in errors[0]["message"], "要指明是哪个文件"
        assert "修饰键" in errors[0]["message"]

    def test_unknown_step_key_is_logged_as_warning(self, isolated_cwd, log_records):
        """`{"w ": 1.0}` 多了个空格，会被当成移动键让角色往不存在的方向走。"""
        write_map_content(
            isolated_cwd,
            "default",
            "map_1-1_0.json",
            {
                "name": "1-1 空间站「黑塔」",
                "author": "tester",
                "start": [],
                "map": [{"w ": 1.0}],
            },
        )

        MapInfo.read_maps("default")

        warnings = self._validation_records(log_records, "WARNING")
        assert len(warnings) == 1
        assert "未知步骤键" in warnings[0]["message"]

    def test_broken_structure_is_logged_before_it_raises(
        self, isolated_cwd, log_records
    ):
        """缺 `name` 今天就会 KeyError（process_json_files 直接取它）。

        校验的价值是：抛之前日志里先写明「哪个文件缺哪个字段」。
        """
        write_map_content(
            isolated_cwd,
            "default",
            "map_1-1_0.json",
            {"author": "tester", "start": [], "map": []},
        )

        with pytest.raises(KeyError):
            MapInfo.read_maps("default")

        assert any(
            "map_1-1_0.json" in r["message"] and "缺少必需字段" in r["message"]
            for r in log_records
        )


class TestShippedMapLibrary:
    """随代码发布的整库地图必须零 error —— 这是校验器的第二道闸。

    与 `tools/validate_maps.py`（CI 里的那道）不同，这条走的是**真实读盘路径**：
    `read_maps` → `read_map_data` → `validate_map`，所以真实地图里的所有步骤键
    形状都被覆盖一遍，而不只是测试里手写的那几种。
    """

    def test_every_shipped_map_passes_validation(self, repo_root, log_records):
        for version in MapInfo.read_maps_versions():
            MapInfo.read_maps(version)

        errors = [
            r["message"]
            for r in log_records
            if r["level"].name == "ERROR" and "地图校验" in r["message"]
        ]
        assert errors == []
