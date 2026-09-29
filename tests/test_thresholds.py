"""utils/core/thresholds.py —— 阈值的集中与取值固定。

这个文件的作用是给「把散落阈值搬进 core/thresholds.py」这一步做安全网：
搬运过程**不允许改变任何数值**，下面逐个钉住。

改这里的值时请连同 `core/thresholds.py` 的「来源待补」一起处理 ——
没有实测依据就调阈值等于盲调。
"""

import pytest

from utils.core import thresholds


#: 常量名 -> 搬运时的原值。新增阈值时在这里补一行。
GOLDEN_VALUES = {
    "DEFAULT_MATCH": 0.90,
    "MAIN_INTERFACE": 0.90,
    "MAIN_INTERFACE_STRICT": 0.92,
    "DOUBT_ICON": 0.92,
    "ROUND_ICON": 0.95,
    "BATTLE_ESC_CHECK": 0.97,
    "AUTO_OFF_ICON": 0.95,
    "ACTION_BAR": 0.97,
    "SPRINT_ICON": 0.996,
    "F_ICON": 0.95,
    "MAP_LOADING": 0.95,
    "MAP_OPEN": 0.97,
    "MAP_BACK": 0.99,
    "TRANSFER_POINT_SEARCH": 0.99,
    "TRANSFER_POINT_MIN": 0.93,
    "SCENE_SEARCH": 0.99,
    "SCENE_MIN": 0.93,
    "PLANET": 0.975,
    "PLANET_CLICK": 0.93,
    "POINT_SEARCH": 0.975,
    "TELEPORT_POINT": 0.93,
    "STAR_MAP": 0.97,
    "BACK_BUTTON": 0.94,
    "FLOOR_BUTTON": 0.93,
    "TRANSFER_ICON": 0.93,
    "BUY_ICON": 0.93,
    "DREAM_MACHINE": 0.992,
    "DREAM_POINT": 0.975,
    "DREAM_POINT_CLICK": 0.95,
    "DREAM_SCENE": 0.990,
    "DREAM_BUILD": 0.90,
    "SETTING_ICON": 0.98,
    "SETTING_OPTION": 0.98,
    "TECHNIQUE_CONSUMABLE": 0.98,
    "SETTING_CONFIRM": 0.99,
    "TECHNIQUE_DIALOG": 0.90,
    "QIQIAO_ICON": 0.95,
    "FINISH_FIGHTING": 0.9,
    "QIQIAO_LAB": 0.97,
    "SNACK_CRAFT_BUTTON": 0.9,
    "ROUND_DISABLE": 0.95,
    "ORIENTATION_ICON": 0.97,
    "CANCEL_BUTTON": 0.95,
    "CONTINUE_FIGHTING": 0.98,
    "DEFEAT": 0.98,
    "MONTHLY_PASS": 0.91,
    "MONTHLY_PASS_NO_PASS": 0.92,
    "LOW_MATCH_REPORT_FLOOR": 0.99,
}


@pytest.mark.parametrize("name,expected", sorted(GOLDEN_VALUES.items()))
def test_threshold_keeps_its_relocated_value(name, expected):
    actual = getattr(thresholds, name)
    assert actual == pytest.approx(expected), (
        f"{name} 的值从 {expected} 变成了 {actual}。"
        "搬运阈值不允许改变数值；如果是有意调整，请一并补上实测依据并更新本表。"
    )


def test_every_public_constant_is_pinned():
    """新增常量必须登记到 GOLDEN_VALUES，否则这条会失败。"""
    public = {
        name
        for name in dir(thresholds)
        if name.isupper() and not name.startswith("_")
    }
    assert public == set(GOLDEN_VALUES), (
        f"未登记的常量：{sorted(public - set(GOLDEN_VALUES))}；"
        f"已失效的登记：{sorted(set(GOLDEN_VALUES) - public)}"
    )


def test_thresholds_are_probabilities():
    """matchTemplate 归一化结果落在 [0, 1]。"""
    for name, value in GOLDEN_VALUES.items():
        assert 0.0 < value <= 1.0, f"{name} = {value} 不在匹配度取值范围内"


def test_thresholds_module_is_pure():
    """core 层必须能被无副作用地导入（不碰窗口/输入/图像库）。"""
    import ast
    from pathlib import Path

    source = Path(thresholds.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    assert imported == set(), f"core/thresholds.py 不应 import 任何东西：{imported}"
