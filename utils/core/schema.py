"""地图 JSON 的校验器 —— 纯逻辑，不碰文件系统。

目前 633 个地图文件没有任何校验。写错一个键名、少一层嵌套，要一路跑进游戏才炸，
而且崩在分发表的 `else` 分支里，看不出是哪张图、哪一步。**更糟的是不崩的那种**：
`process_single_map_handle` 的 `else` 分支会把任何未知键当成移动键
（`handle_move(value, key)`），于是 `{"w ": 1.0}` 这种多了个空格的键不会报错，
只会让角色往一个不存在的方向走。

校验分三级：
    error    结构不对 —— 一定会崩或一定跑错
    warning  键不在已知集合里 —— 可能是新步骤，也可能是笔误
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 步骤键（来自 flows/map_operations.py 的两张分发表）
# ---------------------------------------------------------------------------

#: `process_single_map_start` 里显式分派的键
START_KEYS = {
    "check",
    "need_allow_map_buy",
    "need_allow_snack_buy",
    "need_allow_memory_token",
    "normal_run",
    "blackscreen",
    "esc",
    "map",
    "main",
    "b",
    "await",
    "space",
    "floor",
    "f",
    "w",
    "a",
    "s",
    "d",
    "F4",
    "picture\\max.png",
    "picture\\transfer.png",
}

#: `start` 里除上表外，任何 `picture\\...` 都当作待点击的点位
START_PICTURE_PREFIX = "picture\\"

#: `start` 条目上的**修饰键**。它们和步骤键挤在同一个字典里，由
#: `allow_map_drag` / `allow_scene_drag` / `allow_multi_click` /
#: `allow_retry_in_map` / `allow_click_offset` 从整个条目上读，而不是当步骤处理。
MODIFIER_KEYS = {
    "drag",
    "drag_exact",
    "drag_offset",
    "scene",
    "clicks",
    "forbid_retry",
    "click_offset",
}

#: `process_single_map_handle` 里显式分派的键
MAP_KEYS = {
    "space",
    "caps",
    "r",
    "f",
    "allow_skip_f",
    "check",
    "mouse_move",
    "fighting",
    "scroll",
    "shutdown",
    "e",
    "esc",
    "1",
    "2",
    "3",
    "4",
    "5",
    "main",
    "view_set",
    "view_reset",
    "view_rotate",
    "await",
}

#: `map` 的 else 分支把这些键交给 handle_move；其它键名同样会被当成移动键
MOVEMENT_KEYS = {"w", "a", "s", "d"}

#: 值必须是数字的键（秒 / 次数 / 角度）
NUMERIC_KEYS = {
    "await",
    "scroll",
    "view_set",
    "view_reset",
    "view_rotate",
    "space",
    "caps",
    "r",
    "b",
    "map",
    "main",
    "blackscreen",
    "normal_run",
    "allow_skip_f",
    "f",
    "mouse_move",
} | MOVEMENT_KEYS


@dataclass(frozen=True)
class Issue:
    """一条校验发现。"""

    level: str  # "error" | "warning"
    path: str  # 例如 "map[3].fighting"
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.path}: {self.message}"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_entry(entry, path, allowed, picture_prefix=None) -> list:
    """校验一条步骤：必须是单键字典，且键在允许集合里。"""
    issues = []
    if not isinstance(entry, dict):
        return [Issue("error", path, f"步骤必须是对象，实际是 {type(entry).__name__}")]
    if len(entry) != 1:
        return [
            Issue(
                "error",
                path,
                f"步骤必须是「单键字典」，实际有 {len(entry)} 个键：{sorted(entry)}",
            )
        ]

    key, value = next(iter(entry.items()))
    if key not in allowed and not (
        picture_prefix and isinstance(key, str) and key.startswith(picture_prefix)
    ):
        issues.append(
            Issue("warning", f"{path}.{key}", f"未知步骤键；已知的有 {sorted(allowed)}")
        )
        return issues

    if key in NUMERIC_KEYS and not _is_number(value):
        issues.append(
            Issue("error", f"{path}.{key}", f"值应为数字，实际是 {value!r}")
        )
    return issues


def validate_map(data, filename: str = "") -> list:
    """校验一份地图数据，返回 Issue 列表；空列表表示通过。

    :param data: 已解析的 JSON（dict）
    :param filename: 仅用于消息里指明是哪个文件
    """
    issues = []
    where = filename or "<内存中的地图>"

    if not isinstance(data, dict):
        return [Issue("error", where, f"顶层应为对象，实际是 {type(data).__name__}")]

    for field in ("name", "author"):
        if field not in data:
            issues.append(Issue("error", f"{where}.{field}", "缺少必需字段"))
        elif not isinstance(data[field], str):
            issues.append(
                Issue("error", f"{where}.{field}", f"应为字符串，实际是 {data[field]!r}")
            )

    for field in ("start", "map"):
        if field not in data:
            issues.append(Issue("error", f"{where}.{field}", "缺少必需字段"))
        elif not isinstance(data[field], list):
            issues.append(
                Issue("error", f"{where}.{field}", f"应为数组，实际是 {type(data[field]).__name__}")
            )

    if issues:
        return issues  # 结构都不对，再往下查没意义

    for index, entry in enumerate(data["start"]):
        issues += _check_start_entry(entry, f"{where}.start[{index}]")
        if not isinstance(entry, dict) or not entry:
            continue
        key, value = next(iter(entry.items()))
        # start 独有的值形状
        if key == "check" and not (value == 1 or isinstance(value, list)):
            issues.append(
                Issue("error", f"{where}.start[{index}].check", f"应为 1 或星期数组，实际是 {value!r}")
            )
        if key == "floor":
            issues += _check_floor(value, f"{where}.start[{index}].floor")

    for index, entry in enumerate(data["map"]):
        issues += _check_entry(entry, f"{where}.map[{index}]", MAP_KEYS | MOVEMENT_KEYS)
        if not isinstance(entry, dict) or len(entry) != 1:
            continue
        key, value = next(iter(entry.items()))
        if key == "fighting" and value not in (1, 2):
            issues.append(
                Issue(
                    "error",
                    f"{where}.map[{index}].fighting",
                    f"只接受 1（进入战斗）或 2（打障碍物），实际是 {value!r}",
                )
            )
        if key == "check" and not _is_number(value) and not isinstance(value, list):
            issues.append(
                Issue("error", f"{where}.map[{index}].check", f"应为 1、星期数组或字符串，实际是 {value!r}")
            )

    return issues


def _check_start_entry(entry, path) -> list:
    """校验一条 `start`：第一个键是步骤，其余只允许是修饰键。

    **键顺序有意义**：`map_operations` 用 `list(start.keys())[0]` 取步骤键，
    所以把 `drag` 写在第一个位置（而不是图片路径之后）会让整条步骤走错分支
    —— 而且不报错，只是静默地把 "drag" 当成一个图片路径去查。
    """
    if not isinstance(entry, dict):
        return [Issue("error", path, f"步骤必须是对象，实际是 {type(entry).__name__}")]
    if not entry:
        return [Issue("error", path, "空步骤")]

    first_key = next(iter(entry))
    value = entry[first_key]
    issues = []

    if first_key in MODIFIER_KEYS:
        return [
            Issue(
                "error",
                f"{path}.{first_key}",
                f"第一个键是修饰键 {first_key!r} —— 分发表会把它当成步骤键，"
                f"而修饰键必须写在步骤键之后。当前条目：{list(entry)}",
            )
        ]

    if first_key in NUMERIC_KEYS and not _is_number(value):
        issues.append(
            Issue("error", f"{path}.{first_key}", f"值应为数字，实际是 {value!r}")
        )

    if first_key not in START_KEYS and not (
        isinstance(first_key, str) and first_key.startswith(START_PICTURE_PREFIX)
    ):
        issues.append(Issue("warning", f"{path}.{first_key}", "未知步骤键"))

    for extra in list(entry)[1:]:
        if extra not in MODIFIER_KEYS:
            issues.append(
                Issue(
                    "warning",
                    f"{path}.{extra}",
                    f"未知的修饰键；已知的有 {sorted(MODIFIER_KEYS)}",
                )
            )
        elif extra == "click_offset":
            issues += _check_click_offset(entry[extra], f"{path}.{extra}")
    return issues


def _check_click_offset(value, path) -> list:
    """`click_offset` 必须是 [dx, dy] 两个数字 —— 否则运行时会在下标/加法处抛异常。"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return [Issue("error", path, f"应为 [dx, dy] 两个数字，实际是 {value!r}")]
    if not all(_is_number(item) for item in value):
        return [Issue("error", path, f"dx/dy 必须是数字，实际是 {value!r}")]
    return []


def _check_floor(value, path) -> list:
    """`floor` 的值必须是 [楼层列表, 目标] 且目标在列表里 —— 否则运行时才 IndexError。"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return [Issue("error", path, f"应为 [楼层数组, 目标]，实际是 {value!r}")]
    floors, target = value
    if not isinstance(floors, (list, tuple)):
        return [Issue("error", path, f"第一个元素应为数组，实际是 {type(floors).__name__}")]
    if target not in floors:
        return [
            Issue(
                "error",
                path,
                f"目标 {target!r} 不在楼层数组 {list(floors)} 里 —— 运行时会在 arr.index() 处抛异常",
            )
        ]
    return []


def summarize(issues, filename: str = "") -> str:
    """把 Issue 列表压成一行摘要。"""
    errors = sum(1 for i in issues if i.level == "error")
    warnings = len(issues) - errors
    return f"{filename or '<地图>'}: {errors} 个错误, {warnings} 个警告"
