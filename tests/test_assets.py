"""utils/vision/assets.py —— 图片资源登记表的存在性、唯一性与「不许再裸写路径」棘轮。

三条约束：

1. 登记表里每一条路径都能解析到真实文件（后缀按 webp > png > jpg 回退，
   所以登记 `.png`、磁盘上是 `.webp` 是正常的）。
2. key 与路径都不重复，分类都在 `CATEGORIES` 里。
3. `utils/` 里除登记表自身外，**裸写的图片路径字面量只减不增**。地图 JSON 的
   `picture\\xxx.png` 是数据契约（`core/schema.py` 与 `flows/map_operations.py`
   的分发表），不属于这次收敛范围，登记在名单里并写清原因。
"""

import ast
import os
import re
from pathlib import Path

import pytest

from utils.vision import assets
from utils.vision import images as image_library


REPO_ROOT = Path(__file__).resolve().parent.parent

#: 截图/模板路径字面量的匹配式。`picture_version` 这类配置键不匹配。
PICTURE_LITERAL = re.compile(r"picture[\\/]")

#: 登记表自身当然全是路径字面量，扫描时排除。
REGISTRY_FILE = "utils/vision/assets.py"

#: 允许保留的裸路径字面量（棘轮，只减不增）。每条都写明为什么不能换 key：
ALLOWED_LITERALS = {
    # 地图 JSON 的格式契约：合法的 start 图片 + `picture\` 前缀规则。
    "utils/core/schema.py": 3,
    # 调试参数 `use_sample_image` 的历史路径，文件已不存在；只影响调试分支。
    "utils/vision/get_angle.py": 1,
    # 报告文案里的字符串，不是路径。
    "utils/vision/samples.py": 1,
}


def _docstring_nodes(tree):
    """模块/类/函数的 docstring 节点 id —— 扫描字面量时要排除它们。"""
    ids = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def _literal_counts():
    """`{相对路径: 裸路径字面量个数}`，不含 docstring。"""
    counts = {}
    for path in sorted((REPO_ROOT / "utils").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative == REGISTRY_FILE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_nodes(tree)
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and PICTURE_LITERAL.search(node.value)
        )
        if count:
            counts[relative] = count
    return counts


def _offset_literal_counts():
    """`{相对路径: 非零 offset 字面量个数}`（只扫 `offset=` / `search_offset=` 关键字）。

    位置参数形式的 offset（如 `scan_screenshot(img, (a,b,c,d))`）扫不到 —— 那正是
    这次收拢时改掉的一类写法，新代码一律用 `assets.region()` / `assets.search_offset()`
    传命名区域，别再把元组塞进位置参数。
    """
    counts = {}
    for path in sorted((REPO_ROOT / "utils").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative == REGISTRY_FILE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg not in ("offset", "search_offset"):
                    continue
                value = keyword.value
                if not isinstance(value, ast.Tuple) or len(value.elts) != 4:
                    continue
                items = [
                    elt.value
                    for elt in value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, int)
                ]
                if len(items) == 4 and any(items):
                    count += 1
        if count:
            counts[relative] = count
    return counts


class TestRegistry:
    def test_every_registered_file_exists(self, repo_root):
        missing = [
            key
            for key, asset in assets.ASSETS.items()
            if not os.path.isfile(image_library.resolve_path(asset.path))
        ]
        assert not missing, f"登记了不存在的图片：{missing}"

    def test_paths_are_unique(self):
        paths = [asset.path for asset in assets.ASSETS.values()]
        duplicates = {path for path in paths if paths.count(path) > 1}
        assert not duplicates, f"同一张图被登记了多次：{sorted(duplicates)}"

    def test_categories_are_known(self):
        unknown = {
            key: asset.category
            for key, asset in assets.ASSETS.items()
            if asset.category not in assets.CATEGORIES
        }
        assert not unknown, f"未声明过的分类：{unknown}"

    def test_all_registered_files_live_under_the_picture_root(self):
        outside = [
            key
            for key, asset in assets.ASSETS.items()
            if not asset.path.startswith(assets.PICTURE_ROOT + "/")
        ]
        assert not outside, f"登记表只管理 {assets.PICTURE_ROOT}/ 下的图片：{outside}"

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            assets.path("no_such_asset")


class TestSearchOffset:
    """调用点搜索区域登记在 `Asset.search_offset` —— 运行时点击与探针共用这一份。"""

    def test_registered_offset_is_returned(self):
        assert assets.search_offset("setting_icon") == (1843, 0, -35, 0)

    def test_assets_without_a_region_return_none(self):
        assert assets.search_offset("transfer") is None

    def test_lookup_by_path_normalizes_separators(self):
        path = assets.path("setting_icon")

        assert assets.search_offset_for_path(path) == (1843, 0, -35, 0)
        assert assets.search_offset_for_path(path.replace("/", "\\")) == (
            1843,
            0,
            -35,
            0,
        )

    def test_lookup_by_absolute_path_finds_the_asset(self):
        """WebUI 探针按 `PICTURE_DIR`（绝对路径）加载模板，反查也要认得回来。"""
        absolute = os.path.abspath(assets.path("setting_icon"))

        assert assets.search_offset_for_path(absolute) == (1843, 0, -35, 0)
        assert assets.strategy_for_path(absolute) == assets.MATCH_SHAPE

    def test_an_unregistered_path_has_no_region(self):
        assert assets.search_offset_for_path("./picture/nope.webp") is None

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            assets.search_offset("no_such_asset")

    def test_every_registered_region_is_four_integers(self):
        invalid = {
            key: asset.search_offset
            for key, asset in assets.ASSETS.items()
            if asset.search_offset is not None
            and (
                len(asset.search_offset) != 4
                or not all(isinstance(v, int) for v in asset.search_offset)
            )
        }
        assert not invalid, f"search_offset 必须是 4 个整数（四边增量）：{invalid}"

class TestSearchRegion:
    """没有模板的搜索区域：动态地图资源、色域/HSV/动态截图的区域。"""

    def test_named_region_is_returned(self):
        assert assets.region("mini_map") == (125, 136, -1765, -914)

    def test_unknown_region_raises(self):
        with pytest.raises(KeyError):
            assets.region("no_such_region")

    def test_every_region_is_four_integers(self):
        invalid = {
            key: value
            for key, value in assets.SEARCH_REGIONS.items()
            if len(value) != 4 or not all(isinstance(v, int) for v in value)
        }
        assert not invalid, f"搜索区域必须是 4 个整数（四边增量）：{invalid}"

    def test_the_dynamic_map_regions_are_registered(self):
        """floor / fanhui 是地图 JSON 里的动态资源，没有模板可挂，只能按区域名引用。"""
        assert assets.region("floor_button") == (30, 740, -1820, -70)
        assert assets.region("back_button") == (1660, 100, -40, -910)

    def test_the_registered_asset_regions_match_their_call_sites(self):
        assert assets.search_offset("finish_fighting") == (0, 0, -1630, -800)
        assert assets.search_offset("contraction") == (530, 960, -1050, -50)
        assert assets.search_offset("map_back") == (1830, 0, 0, -975)
        assert assets.search_offset("kaituoli_1") == (1580, 0, 0, -910)
        assert assets.search_offset("qiqiao") == (900, 300, -400, -300)
        assert assets.search_offset("switch_run") == (1720, 930, 0, 0)
        assert assets.search_offset("battle_esc_check") == (0, 0, -1800, -970)


class TestNoHardcodedOffsets:
    def test_offsets_live_in_the_registry(self):
        counts = _offset_literal_counts()

        assert counts == {}, (
            "utils/ 里还有硬编码的搜索区域字面量。\n"
            "模板相关的登记到 `Asset.search_offset`，没有模板的登记到 "
            "`SEARCH_REGIONS`，代码里用 `assets.search_offset(key)` / "
            "`assets.region(key)` 引用。\n"
            f"当前：{counts}"
        )

class TestNoUnregisteredLiterals:
    def test_bare_picture_literals_only_shrink(self):
        counts = _literal_counts()

        assert counts == ALLOWED_LITERALS, (
            "utils/ 里出现了未登记的图片路径字面量（或名单已过期）。\n"
            "新代码请 `from utils.vision import assets` 然后用 `assets.path(key)`；"
            "确实属于数据契约/工具文案的，在 ALLOWED_LITERALS 里登记并写明原因。\n"
            f"当前：{counts}\n允许：{ALLOWED_LITERALS}"
        )
