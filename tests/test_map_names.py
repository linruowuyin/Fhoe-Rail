"""地图展示名：版本 / 星球 / 区域（`utils/core/map_names.py`，CLAUDE.md R23）。

这张表以前散在四处（webui/server.py、ui/map_selector.py、ui/setting.py 的提示语、
README），还互不同步 —— 目录里有 `default_lite`，`VERSION_NAMES` 里没有，图鉴标签
就那么显示了很久。这里的第一组测试就是"盯住磁盘"：**库里有几个版本/星球，表里就得
有几个**，新增版本目录忘了登记会立刻红。
"""

import json
import re
from pathlib import Path

import pytest

from utils.core.map_names import (
    AREA_NAMES,
    PLANET_EMOJI,
    PLANET_NAMES,
    VERSION_NAMES,
    area_key,
    area_label,
    planet_emoji,
    planet_label,
    version_label,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = REPO_ROOT / "map"


def shipped_versions():
    return sorted(p.name for p in MAP_DIR.iterdir() if p.is_dir())


def shipped_planets():
    """库里出现过的星球主号（文件名 map_<主>-<次>_<序号>.json）。"""
    planets = set()
    for version in shipped_versions():
        for path in (MAP_DIR / version).glob("map_*.json"):
            match = re.match(r"map_(\d+)-\d+_\d+\.json", path.name)
            if match:
                planets.add(match.group(1))
    return planets


def shipped_map_names():
    for version in shipped_versions():
        for path in sorted((MAP_DIR / version).glob("map_*.json")):
            yield version, path.name, json.loads(path.read_text(encoding="utf-8")).get("name", "")


class TestCoverageAgainstTheLibrary:
    """磁盘上有的，表里必须有 —— default_lite 那次漏项就该被这几条拦住。"""

    def test_every_version_directory_has_a_chinese_name(self):
        missing = [v for v in shipped_versions() if v not in VERSION_NAMES]
        assert missing == [], f"这些版本目录没有中文名（会显示成裸目录名）：{missing}"

    def test_every_planet_in_the_library_has_a_chinese_name(self):
        missing = sorted(shipped_planets() - set(PLANET_NAMES))
        assert missing == [], f"这些星球编号没有中文名：{missing}"

    def test_every_planet_has_an_emoji(self):
        missing = sorted(shipped_planets() - set(PLANET_EMOJI))
        assert missing == [], f"这些星球没有 emoji：{missing}"

    def test_labels_are_unique_per_table(self):
        # CLI 的版本选择是 {显示名: 值} 的字典 —— 显示名重复会静默吞掉一个选项
        assert len(set(VERSION_NAMES.values())) == len(VERSION_NAMES)
        assert len(set(PLANET_NAMES.values())) == len(PLANET_NAMES)

    def test_every_shipped_map_name_follows_the_area_pattern(self):
        # 区域是从名字里派生的，名字不按「区域-序号」写就会自成一类
        bad = [(v, f, n) for v, f, n in shipped_map_names() if not re.match(r"^.*-\d+$", n or "")]
        assert bad == [], f"这些地图名不符合「区域-序号」：{bad[:5]}"


class TestValidatorCatchesMissingNames:
    """CI 那道闸（tools/validate_maps.py）也得能抓住漏项 —— 破坏验证一下。

    校验器按相对路径找 `map/`（CI 里就是从仓库根跑的），所以这里用 repo_root 夹具
    把 cwd 切回仓库根；否则它一张图都看不到，"0 个有错误"会变成假通过。
    """

    def test_validator_fails_when_a_version_has_no_chinese_name(
        self, repo_root, monkeypatch, capsys
    ):
        import tools.validate_maps as validate

        monkeypatch.delitem(VERSION_NAMES, "default_lite", raising=False)

        assert validate.main([]) == 1
        out = capsys.readouterr().out
        assert "638 个地图文件" in out, "得真的读到整库，不然这条测试是假通过"
        assert "没有登记中文名" in out
        assert "default_lite" in out

    def test_validator_passes_on_the_shipped_library(self, repo_root, capsys):
        import tools.validate_maps as validate

        assert validate.main([]) == 0
        out = capsys.readouterr().out
        assert "638 个地图文件，0 个有错误" in out


class TestAreaKey:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("主控舱段-1", "主控舱段"),
            ("收容舱段-4", "收容舱段"),
            ("工造司（金人）-1", "工造司（金人）"),
            ("大剧院（3D）-3", "大剧院（3D）"),
            ("城郊雪原-12", "城郊雪原"),
        ],
    )
    def test_takes_the_prefix_before_the_sequence(self, name, expected):
        assert area_key(name) == expected

    def test_collapses_stray_whitespace(self):
        # 实测有张图叫「绥  园-6」，多打了个空格 —— 不能因此变成另一个区域
        assert area_key("绥  园-6") == "绥 园"
        assert area_key("绥 园-1") == "绥 园"

    def test_name_without_sequence_falls_back_to_the_whole_name(self):
        assert area_key("月卡") == "月卡"

    def test_empty_name(self):
        assert area_key("") == ""
        assert area_key(None) == ""


class TestAreaLabel:
    def test_default_is_the_derived_name(self):
        assert area_label("主控舱段-1") == "主控舱段"

    def test_override_wins(self):
        assert AREA_NAMES["绥 园"] == "绥园"
        assert area_label("绥  园-1") == "绥园"

    def test_override_keys_are_normalized(self):
        # 键必须是规范化后的形式，否则永远命中不了
        for key in AREA_NAMES:
            assert key == " ".join(key.split())


class TestPlanetAndVersionLabels:
    def test_known_values(self):
        assert planet_label("1") == "黑塔"
        assert version_label("HuangQuan") == "黄泉专用"

    def test_unknown_falls_back_to_the_raw_key(self):
        assert planet_label("9") == "9"
        assert version_label("whatever") == "whatever"

    def test_fallback_argument_is_used_when_given(self):
        assert planet_label("9", "未知星球") == "未知星球"

    def test_planet_emoji_falls_back_to_a_globe(self):
        assert planet_emoji("1")
        assert planet_emoji("9") == "🌍"
