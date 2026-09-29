"""utils/config/config.py —— 配置文件的读写、默认值、完整性与修复。"""

import json
import time

import pytest

from utils.config.config import ConfigurationManager

VALID_JSON_ERROR = ValueError  # orjson.JSONDecodeError 与 json.JSONDecodeError 都是 ValueError 子类


@pytest.fixture
def cfg():
    return ConfigurationManager()


def write_config(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestNormalizeFilePath:
    def test_returns_path_when_exists(self, tmp_path):
        target = tmp_path / "a.json"
        target.write_text("{}", encoding="utf-8")
        assert ConfigurationManager.normalize_file_path("a.json") == str(target)

    def test_returns_none_when_missing(self):
        assert ConfigurationManager.normalize_file_path("nope.json") is None

    def test_only_looks_in_cwd(self, tmp_path, monkeypatch):
        other = tmp_path / "sub"
        other.mkdir()
        (other / "a.json").write_text("{}", encoding="utf-8")
        monkeypatch.chdir(other)
        assert ConfigurationManager.normalize_file_path("a.json") is not None


class TestConfigKeys:
    def test_real_dimensions_default_to_zero(self):
        keys = ConfigurationManager.config_keys()
        assert keys["real_width"] == 0
        assert keys["real_height"] == 0

    def test_real_dimensions_are_parameterised(self):
        keys = ConfigurationManager.config_keys(1920, 1080)
        assert (keys["real_width"], keys["real_height"]) == (1920, 1080)

    @pytest.mark.parametrize(
        "key",
        [
            "map_version",
            "main_map",
            "auto_run_in_map",
            "auto_shutdown",
            "refresh_hour",
            "refresh_minute",
            "forbid_map",
            "allowlist_map",
            "allowlist_mode",
            "angle",
            "angle_set",
            "allow_map_buy",
            "allow_snack_buy",
            "allow_memory_token",
            "notify_enabled",
            "notify_channel",
        ],
    )
    def test_expected_key_present(self, key):
        assert key in ConfigurationManager.config_keys()

    def test_mutable_defaults_are_per_call(self):
        """config_keys 里的列表默认值不能是共享的可变对象。"""
        first = ConfigurationManager.config_keys()
        first["forbid_map"].append("mutated")
        assert ConfigurationManager.config_keys()["forbid_map"] == []


class TestInitConfigFile:
    def test_creates_file_when_missing(self, tmp_path):
        ConfigurationManager.init_config_file(1920, 1080)
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert data["real_width"] == 1920

    def test_does_not_overwrite_existing_file(self, tmp_path, cfg):
        (tmp_path / "config.json").write_text(
            json.dumps({"real_width": 1280}), encoding="utf-8"
        )
        ConfigurationManager.init_config_file(1920, 1080)
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert data["real_width"] == 1280


class TestReadJsonFile:
    def test_round_trip(self, tmp_path):
        write_config(tmp_path / "x.json", {"a": 1, "中文": "值"})
        assert ConfigurationManager.read_json_file("x.json") == {"a": 1, "中文": "值"}

    def test_returns_path_when_requested(self, tmp_path):
        write_config(tmp_path / "x.json", {"a": 1})
        data, path = ConfigurationManager.read_json_file("x.json", path=True)
        assert data == {"a": 1}
        assert path == str(tmp_path / "x.json")

    def test_strips_utf8_bom(self, tmp_path):
        (tmp_path / "x.json").write_bytes(
            b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode("utf-8")
        )
        assert ConfigurationManager.read_json_file("x.json") == {"a": 1}

    def test_recreates_default_when_missing(self, tmp_path):
        (tmp_path / "config.json").unlink()
        data = ConfigurationManager.read_json_file("config.json")
        assert "map_version" in data

    @pytest.mark.xfail(
        strict=True,
        reason="read_json_file 对 orjson.loads 没有任何异常处理，配置被写坏时会直接崩；"
        "同文件的 load_config 做了完整兜底，两套读法健壮性不一致",
    )
    def test_malformed_json_does_not_raise(self, tmp_path):
        (tmp_path / "x.json").write_text("{ this is not json", encoding="utf-8")
        assert ConfigurationManager.read_json_file("x.json") == {}


class TestModifyJsonFile:
    def test_updates_only_target_key(self, tmp_path):
        write_config(tmp_path / "x.json", {"a": 1, "b": {"nested": True}})
        ConfigurationManager.modify_json_file("x.json", "a", 2)
        data = json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))
        assert data == {"a": 2, "b": {"nested": True}}

    def test_adds_new_key(self, tmp_path):
        write_config(tmp_path / "x.json", {"a": 1})
        ConfigurationManager.modify_json_file("x.json", "new", [1, 2])
        data = json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))
        assert data["new"] == [1, 2]

    def test_preserves_non_ascii(self, tmp_path):
        write_config(tmp_path / "x.json", {})
        ConfigurationManager.modify_json_file("x.json", "名字", "值")
        raw = (tmp_path / "x.json").read_text(encoding="utf-8")
        assert "名字" in raw, "orjson 应输出 UTF-8 而非 \\uXXXX 转义"


class TestSaveAndLoadConfig:
    def test_round_trip(self, tmp_path):
        ConfigurationManager.save_config({"a": 1, "中文": "值"})
        assert ConfigurationManager.load_config() == {"a": 1, "中文": "值"}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        (tmp_path / "config.json").unlink()
        assert ConfigurationManager.load_config() == {}

    def test_malformed_json_returns_empty_dict(self, tmp_path, log_records):
        (tmp_path / "config.json").write_text("{ broken", encoding="utf-8")
        assert ConfigurationManager.load_config() == {}
        assert any(r["level"].name == "ERROR" for r in log_records)


class TestConfigCompleteness:
    def test_issubset_true_for_default_config(self):
        assert ConfigurationManager.config_issubset() is True

    def test_issubset_false_when_key_missing(self, tmp_path):
        write_config(tmp_path / "config.json", {"map_version": "default"})
        assert ConfigurationManager.config_issubset() is False

    def test_ensure_config_complete_restores_missing_keys(self, tmp_path, log_records):
        write_config(tmp_path / "config.json", {"map_version": "default"})
        ConfigurationManager.ensure_config_complete()
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert set(ConfigurationManager.config_all_keys()).issubset(data.keys())
        assert data["map_version"] == "default", "已有值不应被覆盖"

    def test_ensure_config_complete_is_noop_when_already_complete(
        self, tmp_path, log_records
    ):
        before = (tmp_path / "config.json").read_text(encoding="utf-8")
        ConfigurationManager.ensure_config_complete()
        assert (tmp_path / "config.json").read_text(encoding="utf-8") == before


class TestConfigFileProperty:
    def test_reads_and_caches(self, cfg):
        cfg.config_file["cached"] = True
        assert cfg.config_file["cached"] is True

    def test_refreshes_after_file_changes_on_disk(self, cfg, tmp_path):
        assert cfg.config_file["map_version"] == "default"
        time.sleep(0.01)  # 让新写入的文件拿到一个与旧值不同的 mtime
        write_config(tmp_path / "config.json", {**cfg.config_file, "map_version": "HuangQuan"})
        assert cfg.config_file["map_version"] == "HuangQuan"

    def test_untouched_file_is_never_reread(self, cfg, tmp_path):
        """文件一个字都没改，反复访问也不该重读 —— 那个测试偶发的回归测试。

        旧实现记的是 `time.time()`，再拿文件 mtime 和它比大小：两把尺子精度不同
        （Windows 时钟约 15.6ms，NTFS 的 mtime 是 100ns），于是「mtime 比刚记下的
        时刻更新」会**偶发**成立，被误判成「文件又变了」而重读 —— 重读是整个替换
        内存里那份 dict，会把刚写进去的键冲掉（`KeyError: 'cached'`）。

        判断依据换成「mtime 对 mtime」之后与时钟无关。旧实现下这条会以很高概率
        失败（几十次访问足够撞上时钟量化那一格）。
        """
        path = tmp_path / "config.json"
        cfg.config_file["cached"] = True

        for _ in range(50):
            assert cfg.config_file["cached"] is True

        assert cfg._last_mtime == path.stat().st_mtime, (
            "记下的必须是文件 mtime，不能是读钟得到的时刻"
        )

    def test_does_not_reread_when_file_unchanged(self, cfg, monkeypatch):
        cfg.config_file  # 建立缓存
        calls = []
        real_getmtime = __import__("os").path.getmtime
        monkeypatch.setattr(
            "os.path.getmtime",
            lambda path: (calls.append(path), real_getmtime(path))[1],
        )
        cfg.config_file
        assert calls, "属性访问仍会 stat 文件（虽然不会重新解析 JSON）"


class TestGetFile:
    @pytest.fixture
    def tree(self, tmp_path):
        """独立的目录树，避免和 autouse 夹具写入的 config.json / version.txt 混在一起。"""
        root = tmp_path / "tree"
        root.mkdir()
        return root

    def test_lists_files_recursively(self, tree):
        (tree / "a").mkdir()
        (tree / "a" / "1.json").write_text("{}", encoding="utf-8")
        (tree / "2.json").write_text("{}", encoding="utf-8")
        assert sorted(ConfigurationManager.get_file(tree, [])) == ["1.json", "2.json"]

    def test_get_path_returns_joined_paths(self, tree):
        (tree / "a").mkdir()
        (tree / "a" / "1.json").write_text("{}", encoding="utf-8")
        paths = ConfigurationManager.get_file(tree, [], get_path=True)
        assert len(paths) == 1
        assert paths[0].endswith("1.json")

    def test_exclude_skips_folder(self, tree):
        (tree / "skipme").mkdir()
        (tree / "skipme" / "x.json").write_text("{}", encoding="utf-8")
        (tree / "keep").mkdir()
        (tree / "keep" / "y.json").write_text("{}", encoding="utf-8")
        assert ConfigurationManager.get_file(tree, ["skipme"]) == ["y.json"]

    def test_exclude_file_skips_matching_names(self, tree):
        (tree / "keep.json").write_text("{}", encoding="utf-8")
        (tree / "drop.json").write_text("{}", encoding="utf-8")
        assert ConfigurationManager.get_file(tree, [], ["drop"]) == ["keep.json"]

    def test_missing_directory_yields_nothing(self, tmp_path):
        assert ConfigurationManager.get_file(tmp_path / "nope", []) == []


class TestConfigFix:
    def test_huangquan_forces_buy_prop(self, tmp_path):
        write_config(tmp_path / "config.json", {**ConfigurationManager.config_keys(0, 0),
                                                "map_version": "HuangQuan"})
        ConfigurationManager.config_fix()
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert data["allow_fight_e_buy_prop"] is True

    def test_silver_wolf_forces_consumable(self, tmp_path):
        write_config(tmp_path / "config.json", {**ConfigurationManager.config_keys(0, 0),
                                                "map_version": "SilverWolfLv999"})
        ConfigurationManager.config_fix()
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert data["auto_use_technique_consumable"] is True

    def test_other_versions_untouched(self, tmp_path):
        write_config(tmp_path / "config.json", ConfigurationManager.config_keys(0, 0))
        ConfigurationManager.config_fix()
        data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert data["allow_fight_e_buy_prop"] is False

    def test_empty_config_raises_key_error(self, tmp_path):
        """load_config 在解析失败时返回 {}，config_fix 用 [] 取键会 KeyError。"""
        (tmp_path / "config.json").write_text("{ broken", encoding="utf-8")
        with pytest.raises(KeyError):
            ConfigurationManager.config_fix()
