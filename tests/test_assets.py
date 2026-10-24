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
    # 地图 JSON 步骤键的分发（数据里的键，不是代码资源）。
    "utils/flows/map_operations.py": 11,
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


class TestNoUnregisteredLiterals:
    def test_bare_picture_literals_only_shrink(self):
        counts = _literal_counts()

        assert counts == ALLOWED_LITERALS, (
            "utils/ 里出现了未登记的图片路径字面量（或名单已过期）。\n"
            "新代码请 `from utils.vision import assets` 然后用 `assets.path(key)`；"
            "确实属于数据契约/工具文案的，在 ALLOWED_LITERALS 里登记并写明原因。\n"
            f"当前：{counts}\n允许：{ALLOWED_LITERALS}"
        )
