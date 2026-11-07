"""地图 JSON 步骤的格式归一化 —— v1（键即动作）与 v2（命名字段）双认。

纯逻辑，不碰文件系统、不 import 其它 utils 模块（tests 直接构造输入）。

v2 步骤的四个命名字段（详见 docs/MAP_FORMAT.md）：

    img    图片资源 stem（无路径、无后缀），只出现在 `start` 的图片步骤里
    delay  图片步点击后的停顿秒数（就是 v1 图片键的值；省略 = 0.8）
    rep    本步总执行次数，省略 = 1
    c      注释，运行时剥掉

**双认的核心约定**：运行时规范形永远是 v1 的「单键步骤」。全项目只有
`normalize_step` / `normalize_steps` 一个解析点 —— v2 在进入任何分发表之前就被
展开成 v1，所以分发表、movement、工具脚本都不用知道 v2 的存在。

rep 必须在进入执行循环**之前**展开成 N 份，而不能在循环里原地循环 N 次：
`process_single_map_handle` 依赖 `prev_key` / `next_key`（同方向续走、疾跑保持）
和 `fighting_count`（按条数统计），展开后的序列与等价 v1 逐条一致，这些语义零漂移。
也因此迁移工具不合并 `fighting` 步（tests/test_map_format.py::TestCollapseAdjacent）。
"""

import copy

#: v2 的版本号（顶层 "v" 字段）
V2_VERSION = 2

#: v2 步骤的保留字段。v1 的合法键里没有它们，所以「出现即按 v2 解析」不会歧义。
RESERVED_KEYS = ("img", "delay", "rep", "c")

#: rep 的运行时上限。CI 会拦更大的值；这里兜底手滑写出的天文数字。
MAX_REP = 100

#: 图片步 delay 的缺省值 = v1 运行时的上限（`map_operations` 里 min(value, 0.8)）
DEFAULT_DELAY = 0.8

_PICTURE_PREFIXES = ("picture\\", "picture/")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _rep_count(step: dict) -> int:
    """读 rep 字段，容忍一切脏值：非法/越界都回到 1（CI 负责拦写法）。"""
    value = step.get("rep", 1)
    if not _is_number(value):
        return 1
    count = int(value)
    if count < 1:
        return 1
    return min(count, MAX_REP)


def _picture_v1_key(stem: str) -> str:
    """v1 规范键形：`picture\\\\<stem>.png`。后缀是序列化细节，asset_id 都会剥掉。"""
    return f"picture\\{stem}.png"


def normalize_step(step) -> list:
    """把一条步骤归一化成 **0 或多条 v1 单键/多键步骤** 的列表。

    * v1 步骤：原样透传（同一对象，零拷贝）
    * v2 步骤：img → v1 图片键、rep → 展开 N 份、c → 剥掉、delay → 值
    * 只有注释没有动作的步骤（{"c": "..."}）→ 空列表（纯注释步，跳过）

    返回的 v2 展开结果之间共享的只有「本步内不可变的东西」：修饰键里的列表会做
    深拷贝，改一份不会串到另一份（tests/test_map_format.py 有断言）。
    """
    if not isinstance(step, dict):
        return [step]
    # img 字段存在但不是合法 stem：整体按 v1 透传（schema/CI 会报错，运行时不猜）
    if "img" in step and not (isinstance(step["img"], str) and step["img"]):
        return [step]
    has_img = isinstance(step.get("img"), str) and bool(step.get("img"))
    if not (has_img or "rep" in step or "c" in step):
        return [step]  # v1 快路径：无保留字段，原样透传

    base: dict = {}
    if has_img:
        base[_picture_v1_key(step["img"])] = (
            step["delay"] if _is_number(step.get("delay")) else DEFAULT_DELAY
        )
    for key, value in step.items():
        if key in RESERVED_KEYS:
            continue
        if isinstance(value, list):
            base[copy.deepcopy(key)] = copy.deepcopy(value)
        else:
            base[key] = value
    if not base:
        return []  # 纯注释步 / 空 v2 步

    # 每一份都深拷贝：rep 展开出的 N 份互不共享列表值（tests 有断言）
    return [copy.deepcopy(base) for _ in range(_rep_count(step))]


def normalize_steps(steps) -> list:
    """整个 start/map 数组逐条归一化后摊平。"""
    if not isinstance(steps, list):
        return steps
    out: list = []
    for step in steps:
        out.extend(normalize_step(step))
    return out


def normalize_map_data(data: dict) -> dict:
    """归一化一份地图数据的 start/map 两个数组；不修改输入，返回浅拷贝字典。

    其余顶层键（name/author/...）原样共享。v1 数据走快路径，结果与输入等值。
    """
    if not isinstance(data, dict):
        return data
    out = dict(data)
    out["start"] = normalize_steps(data.get("start"))
    out["map"] = normalize_steps(data.get("map"))
    return out


# ---------------------------------------------------------------------------
# 迁移：v1 → v2（tools/migrate_maps_v2.py 也用）
# ---------------------------------------------------------------------------

#: 相邻合并的黑名单。fighting 的条数有外部语义（fighting_count 按条数统计、
#: current_fighting_index 按它推进），合并会漏计，必须原样保留。
_NO_COLLAPSE_KEYS = {"fighting"}


def collapse_adjacent(steps) -> list:
    """把**相邻且完全相同**的单键步骤合并成 rep=N（仅动作键）。

    严格等价性依据：normalize_steps(合并后) == normalize_steps(合并前) —— rep 在
    运行时展开回 N 份一模一样的步骤，序列逐条一致。多键条目（带修饰键的 start
    步骤）与 fighting 不合并。
    """
    if not isinstance(steps, list):
        return steps
    out: list = []
    for step in steps:
        if (
            isinstance(step, dict)
            and len(step) == 1
            and out
            and isinstance(out[-1], dict)
            and _mergeable_shape(out[-1])
        ):
            key, value = next(iter(step.items()))
            last_key, last_value = next(iter(out[-1].items()))
            if (
                key == last_key
                and key not in _NO_COLLAPSE_KEYS
                and value == last_value
                and not isinstance(value, (list, dict))
            ):
                out[-1] = {key: value, "rep": _last_rep(out[-1], key, value) + 1}
                continue
        out.append(step)
    return out


def _mergeable_shape(entry: dict) -> bool:
    """上一条是否是「可继续累加」的形态：单键步骤，或已合并的 {key, rep}。"""
    if len(entry) == 1:
        return True
    return len(entry) == 2 and "rep" in entry


def _last_rep(last_entry: dict, key, value) -> int:
    """上一条已经带 rep 时继续累加；否则这是第 1 次。"""
    if set(last_entry) == {key, "rep"} and last_entry[key] == value:
        return int(last_entry["rep"])
    return 1


def _picture_key_to_img(step: dict) -> dict:
    """把条目里的 `picture\\\\x.png` 键改写成 img + delay，其余键原样保序。"""
    out: dict = {}
    for key, value in step.items():
        stem = None
        if isinstance(key, str):
            for prefix in _PICTURE_PREFIXES:
                if key.startswith(prefix):
                    raw = key[len(prefix):]
                    stem = raw[:-4] if raw.endswith(".png") else raw
                    break
        if stem is not None:
            out["img"] = stem
            out["delay"] = value if _is_number(value) else DEFAULT_DELAY
        else:
            out[key] = copy.deepcopy(value) if isinstance(value, list) else value
    return out


def migrate_map(data: dict) -> dict:
    """v1 → v2 全量迁移：顶层加 "v": 2、图片键改 img、相邻相同步骤合并 rep。

    输入可以是 v1 也可以是已迁移的 v2（幂等）。不修改输入。
    迁移是否无损由 `verify_migration` 判定（工具脚本会对每个文件断言）。
    """
    out: dict = {}
    for key, value in data.items():
        if key in ("start", "map"):
            continue
        out[key] = value
    # v 排在第一位，剩下的键保持原顺序
    ordered: dict = {"v": V2_VERSION}
    ordered.update(out)
    ordered["start"] = [_picture_key_to_img(s) for s in collapse_adjacent(data.get("start", []))]
    ordered["map"] = [_picture_key_to_img(s) for s in collapse_adjacent(data.get("map", []))]
    return ordered


def verify_migration(original: dict, migrated: dict) -> bool:
    """迁移无损校验：migrated 归一化（展开）后必须与 original 归一化逐条相等。

    这是迁移的安全网 —— rep 合并、img 改写全部要在这一步被证明语义等价，
    任何一个文件过不了就不许写盘（tools/migrate_maps_v2.py 会拒绝并报出来）。
    """
    try:
        before = normalize_map_data(original)
        after = normalize_map_data(migrated)
    except Exception:  # noqa: BLE001 —— 数据脏到归一化不了，视为不等价
        return False
    return before["start"] == after["start"] and before["map"] == after["map"]
