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

import re
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
    "lv999_e",
    "lv999_fighting",
    "lv999_await",
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

#: `map` 的 else 分支把这些键交给 handle_move。
#: `aa/ww/ss/dd` 是「同方向续走、不要打断疾跑」的变体（见 flows/movement.py）。
MOVEMENT_KEYS = {"w", "a", "s", "d", "ww", "aa", "ss", "dd"}

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
    "lv999_e",
    "lv999_fighting",
    "lv999_await",
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


# ---------------------------------------------------------------------------
# v2 格式（utils/core/map_format.py 的保留字段，docs/MAP_FORMAT.md）
# ---------------------------------------------------------------------------

#: v2 步骤保留字段。v1 的合法键里没有它们，所以「v1 文件里出现即报错」不会误伤。
RESERVED_KEYS = ("img", "delay", "rep", "c")

#: 图片资源 stem 的形状（如 `transfer` / `map_4-3_point_5` / `fanhui_1`）：
#: 不含路径分隔符、不含后缀。是否真的解析得到图片文件由 tools/validate_pictures.py 查。
IMG_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


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

    # ---- 版本判定（docs/MAP_FORMAT.md）：有 "v" 就是 v2，只接受 2 ----
    version = 1
    if "v" in data:
        if not isinstance(data["v"], int) or isinstance(data["v"], bool) or data["v"] != 2:
            issues.append(
                Issue("error", f"{where}.v", f'"v" 只接受 2，实际是 {data["v"]!r}')
            )
        version = 2

    if version == 2:
        for index, entry in enumerate(data["start"]):
            issues += _check_v2_start_entry(entry, f"{where}.start[{index}]")
        for index, entry in enumerate(data["map"]):
            issues += _check_v2_map_entry(entry, f"{where}.map[{index}]")
        return issues

    # v1 文件里出现 v2 保留字段 = 作者想把 v2 语法写进 v1：运行时会整条走错分支。
    # 命中保留字段的条目只报这一条专用错误，不再叠加单键/未知键的通用检查。
    def _has_reserved(entry):
        return isinstance(entry, dict) and bool({"img", "rep", "c"} & set(entry))

    for array in ("start", "map"):
        for index, entry in enumerate(data[array]):
            if _has_reserved(entry):
                issues.append(
                    Issue(
                        "error",
                        f"{where}.{array}[{index}]",
                        "出现了 v2 保留字段（img/rep/c）—— 请在顶层加 \"v\": 2，或改回 v1 写法",
                    )
                )

    for index, entry in enumerate(data["start"]):
        if _has_reserved(entry):
            continue
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
        if _has_reserved(entry):
            continue
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
        if key == "lv999_e" and _is_number(value) and value != 1:
            issues.append(
                Issue(
                    "error",
                    f"{where}.map[{index}].lv999_e",
                    f"只接受 1（银狼 LV.999 设置 + 按E），实际是 {value!r}",
                )
            )
        if key == "lv999_fighting" and _is_number(value) and value != 1:
            issues.append(
                Issue(
                    "error",
                    f"{where}.map[{index}].lv999_fighting",
                    f"只接受 1（与 fighting: 1 相同），实际是 {value!r}",
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


# ---------------------------------------------------------------------------
# v2 条目校验
# ---------------------------------------------------------------------------


def _check_reserved_values(entry, path) -> list:
    """rep / c / delay 的类型约束（img 步和动作步共用）。"""
    issues = []
    if "rep" in entry:
        rep = entry["rep"]
        if not isinstance(rep, int) or isinstance(rep, bool) or rep < 1:
            issues.append(
                Issue("error", f"{path}.rep", f"应为 ≥1 的整数（本步总执行次数），实际是 {rep!r}")
            )
    if "c" in entry and not isinstance(entry["c"], str):
        issues.append(
            Issue("error", f"{path}.c", f"注释应为字符串，实际是 {entry['c']!r}")
        )
    if "delay" in entry and not _is_number(entry["delay"]):
        issues.append(
            Issue("error", f"{path}.delay", f"应为数字（点击后停顿秒数），实际是 {entry['delay']!r}")
        )
    return issues


def _check_v2_start_entry(entry, path) -> list:
    """v2 的 `start` 条目：步骤键（动作键或 img）在前，保留字段与修饰键在后。

    与 v1 的差别：
        * `picture\\...` 键整个不允许 —— v2 文件统一写 `{"img": ...}`
        * img 的 stem 有形状约束；delay 有类型约束
        * 除步骤键/保留字段/修饰键之外的键直接报错（v1 是 warning，
          因为 v1 只有单键步骤无处可挂；v2 的 img 步是结构化条目，
          拼错的修饰键会被静默丢掉，必须拦下）
    """
    if not isinstance(entry, dict):
        return [Issue("error", path, f"步骤必须是对象，实际是 {type(entry).__name__}")]
    if not entry:
        return [Issue("error", path, "空步骤")]

    issues = _check_reserved_values(entry, path)
    first_key = next(iter(entry))

    if isinstance(first_key, str) and first_key.startswith(START_PICTURE_PREFIX):
        issues.append(
            Issue(
                "error",
                f"{path}.{first_key}",
                "v2 文件里图片步骤统一写 {\"img\": \"<stem>\", \"delay\": ...}，"
                "不再用 picture\\ 键",
            )
        )
        return issues

    for key in entry:
        if isinstance(key, str) and key.startswith(START_PICTURE_PREFIX):
            issues.append(
                Issue(
                    "error",
                    f"{path}.{key}",
                    "v2 文件里图片步骤统一写 {\"img\": \"<stem>\", \"delay\": ...}，"
                    "不再用 picture\\ 键",
                )
            )

    if first_key in MODIFIER_KEYS or first_key in ("delay", "rep", "c"):
        issues.append(
            Issue(
                "error",
                f"{path}.{first_key}",
                f"第一个键必须是步骤键（动作键或 img），实际是 {first_key!r}。"
                f"当前条目：{list(entry)}",
            )
        )
        return issues

    if first_key == "img":
        stem = entry["img"]
        if not isinstance(stem, str) or not IMG_STEM.match(stem):
            issues.append(
                Issue(
                    "error",
                    f"{path}.img",
                    f"img 应为图片资源 stem（如 \"transfer\"，无路径无后缀），实际是 {stem!r}",
                )
            )
    elif first_key not in START_KEYS:
        issues.append(Issue("warning", f"{path}.{first_key}", "未知步骤键"))

    for extra in list(entry)[1:]:
        if extra in RESERVED_KEYS or extra in MODIFIER_KEYS:
            if extra == "click_offset":
                issues += _check_click_offset(entry[extra], f"{path}.{extra}")
            continue
        issues.append(
            Issue(
                "error",
                f"{path}.{extra}",
                f"未知键（v2 条目只允许步骤键 + 保留字段 img/delay/rep/c + 修饰键 "
                f"{sorted(MODIFIER_KEYS)}）",
            )
        )
    return issues


def _check_v2_map_entry(entry, path) -> list:
    """v2 的 `map` 条目：一个动作键 + 可选 rep/c。图片与修饰键都不属于 map。

    实测 633 张自有地图 map 数组里没有任何 picture 键，运行时的 map 循环也
    没有图片分派（图片步骤全在 start）—— 所以 v2 明确禁止 img 进 map。
    """
    if not isinstance(entry, dict):
        return [Issue("error", path, f"步骤必须是对象，实际是 {type(entry).__name__}")]
    if not entry:
        return [Issue("error", path, "空步骤")]

    issues = _check_reserved_values(entry, path)
    step_keys = [k for k in entry if k not in RESERVED_KEYS]

    if len(step_keys) != 1:
        issues.append(
            Issue(
                "error",
                path,
                f"v2 的 map 条目应为「一个动作键 + 可选 rep/c」，实际步骤键有 {step_keys}",
            )
        )
        return issues

    key, value = step_keys[0], entry[step_keys[0]]
    if isinstance(key, str) and key.startswith(START_PICTURE_PREFIX):
        issues.append(
            Issue("error", f"{path}.{key}", "map 数组里没有图片步骤，请把这条移到 start 并改写 img")
        )
    if key == "img":
        issues.append(
            Issue("error", f"{path}.img", "map 数组里没有图片步骤（img 只用于 start）")
        )
    if key in MODIFIER_KEYS:
        issues.append(
            Issue("error", f"{path}.{key}", f"修饰键 {key!r} 只用于 start 条目")
        )
    elif key not in MAP_KEYS and key not in MOVEMENT_KEYS:
        issues.append(Issue("warning", f"{path}.{key}", "未知步骤键"))

    if key in NUMERIC_KEYS and not _is_number(value):
        issues.append(
            Issue("error", f"{path}.{key}", f"值应为数字，实际是 {value!r}")
        )
    if key == "fighting" and "rep" in entry:
        issues.append(
            Issue(
                "error",
                f"{path}.rep",
                "fighting 不允许配 rep：fighting_count 按条数统计，合并会漏计",
            )
        )
    if key == "fighting" and value not in (1, 2):
        issues.append(
            Issue(
                "error",
                f"{path}.{key}",
                f"只接受 1（进入战斗）或 2（打障碍物），实际是 {value!r}",
            )
        )
    return issues
