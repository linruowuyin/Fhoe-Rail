"""图片识别参数覆盖层 —— 每张图片识别参数的「单一真相源」（稀疏）。

为什么存在
    本项目有两处「图片识别参数」的家：`core/thresholds.py` 管**语义/全局阈值**
    （按概念命名，几十个，稳定），`vision/assets.py` 管**代码引用的图片资产**
    （路径/分类/搜索区域/匹配策略）。但地图点位图有几百张，绝大多数用默认就够
    —— 默认模式 `MATCH_COLOR`、默认阈值按步骤类型取 `POINT_SEARCH` 等 ——
    **不该逐张登记**，否则会膨胀成几千行的常量表。本模块只收「偏离默认的那几张」，
    保持稀疏。

    它定位为**覆盖层**：叠在 `assets` 之上。同一张图若在本表登记了参数，以本表
    为准；否则回退到「步骤上下文默认」或 `assets` 登记（代码引用图）。

设计要点（与成熟项目实践一致）
    * 单一真相源：每个需要定制的资产在全项目**只有这一条记录**。
    * 稀疏覆盖：无记录 → 走默认（见 `mode_of_path` / `thresholds_of` 的回退逻辑）。
    * 单一查询 API：调用点只问本模块，绝不硬编码字面量或散落判断。
    * 类型化：用 `RecognitionEntry` 约束字段；合法性校验见 `tests/test_recognition.py`。

归属
    这份数据是**视觉标定**数据（由探针实测决定，CLAUDE.md §1.2），属开发侧，
    与 `thresholds.py` / `assets.py` 同构，故放在 `utils/vision/`。地图 JSON 是
    地图作者数据，不应混进来 —— 这里只管「怎么认出这张图」，不管「点到哪、等几秒」。

字段语义
    mode            匹配策略：`assets.MATCH_COLOR` / `MATCH_SHAPE` / `MATCH_COLOR_CCOEFF`。
                    默认 color（底色固定、整图 CCORR）。
    threshold       查找（find）阈值；None 表示用步骤上下文默认。
    click_threshold 点击阈值；None 表示用步骤上下文默认。
    min_threshold   查找阈值逐轮下降的下限；None 表示用步骤上下文默认。
"""

import os
from dataclasses import dataclass
from typing import Optional

from utils.vision import assets


@dataclass(frozen=True)
class RecognitionEntry:
    """单张图片的识别参数覆盖项。

    所有字段均可空：空字段回退到「步骤上下文默认」或「全局默认」，
    这样表里只需写真正偏离默认的项，保持稀疏。
    """

    mode: Optional[str] = None
    threshold: Optional[float] = None
    click_threshold: Optional[float] = None
    min_threshold: Optional[float] = None


#: 稀疏覆盖表 —— 只登记「偏离默认」的图片识别参数。键是资源 ID（文件名去后缀、
#: 小写，与 `assets.asset_id` 同口径）。新增一条请同步 `tests/test_recognition.py`。
#:
#: 设计原则（R11 单一来源）：表里**只写真正偏离默认的项**，其余字段留空回退默认。
#: 不要在这里抄 `core/thresholds.py` 的数字 —— 阈值该在哪维护就在哪维护。例如
#: 筑梦三张图只覆盖 `mode`（轮廓识别），查找 / 点击 / 下限阈值全部回退到调用点传入
#: 的默认（运行时即 `thresholds.DREAM_MACHINE`，探针即 `assets.threshold_for_path`），
#: 数字只在 `thresholds.py` 那一处。哪天重新标定 DREAM_MACHINE，这里**不用动**。
#: 6-5 地图点位图的实测匹配阈值（轮廓识别，底色随场景变化）。0.85 低于
#: `find_transfer_point` 默认下限 `TRANSFER_POINT_MIN`(0.93)，故查找 / 点击 /
#: 下限三处都用它（详见下方三条记录的注释），避免被默认下限抬回 0.93。
_MAP_6_5_POINT_THRESHOLD = 0.85


RECOGNITION_OVERRIDES: dict[str, RecognitionEntry] = {
    # 筑梦边境机关检查：底色随游戏内模糊背景变化，用轮廓识别（梯度幅值 + CCOEFF，
    # 见 `vision/matcher.py::Matcher.shape_features`）。只覆盖 mode；阈值（含下限）
    # 由调用点按 DREAM_MACHINE 默认传入（单一来源在 `thresholds.py`）。
    # 复核方式：`tools/match_probe.py check_4-1_point_1`（主策略显示「轮廓识别」）。
    "check_4-1_point_1": RecognitionEntry("shape"),
    "check_4-1_point_2": RecognitionEntry("shape"),
    "check_4-1_point_3": RecognitionEntry("shape"),
    # 6-5 地图点位：底色随场景变化，整图颜色匹配易漏，故用轮廓识别（shape）。
    # 阈值 0.85 为实机实测值（2026-10-30）。查找 / 点击 / 下限三者同为 0.85 ——
    # 因为 `find_transfer_point` 默认下限 `TRANSFER_POINT_MIN`(0.93) 会把阈值抬回
    # 0.93（见其 `max(min, 阈值-0.01)`），下限不跟着设就会「设了 0.85 实际按 0.93 跑」。
    # 复核方式：`tools/match_probe.py map_6-5_point_1`（主策略显示「轮廓识别」，阈值 0.85）。
    "map_6-5_point_1": RecognitionEntry("shape", _MAP_6_5_POINT_THRESHOLD,
                                        click_threshold=_MAP_6_5_POINT_THRESHOLD,
                                        min_threshold=_MAP_6_5_POINT_THRESHOLD),
    "map_6-5_point_2": RecognitionEntry("shape", _MAP_6_5_POINT_THRESHOLD,
                                        click_threshold=_MAP_6_5_POINT_THRESHOLD,
                                        min_threshold=_MAP_6_5_POINT_THRESHOLD),
    "map_6-5_point_3": RecognitionEntry("shape", _MAP_6_5_POINT_THRESHOLD,
                                        click_threshold=_MAP_6_5_POINT_THRESHOLD,
                                        min_threshold=_MAP_6_5_POINT_THRESHOLD),
}


def _stem_of_path(path: Optional[str]) -> str:
    """文件路径 → 资源 ID（去后缀、小写），与 `assets.asset_id` 同口径。

    空路径（反色/旋转造的临时数组查不回）返回空串，调用方据此回退默认。
    """
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    base = normalized.rsplit("/", 1)[-1]
    return os.path.splitext(base)[0].lower()


def mode_of_path(path: str) -> str:
    """图片路径 → 匹配策略（覆盖优先于 assets 登记，再回退默认 color）。

    把「覆盖层」叠在 `assets.strategy_for_path` 之上：同一张图若在本表登记了
    `mode`，以本表为准；否则沿用 assets 的登记（代码引用图）或默认 color。
    这是全项目查询某图识别模式的**唯一入口**（`images.strategy_of` 改走这里）。
    """
    entry = RECOGNITION_OVERRIDES.get(_stem_of_path(path))
    if entry is not None and entry.mode is not None:
        return entry.mode
    return assets.strategy_for_path(path)


def threshold_override_of_path(path: str) -> Optional[float]:
    """图片路径 → 覆盖层里「显式写的查找阈值」（若设了）；否则 None。

    供 `assets.threshold_for_path` 合并使用：覆盖层的显式阈值优先于登记表阈值，
    让「单独控制某张图阈值」也对探针可见（WebUI meta / CLI 默认都走那里）。
    只认 `threshold` 字段；mode 与阈值通过不同通道生效，互不干扰。
    """
    entry = RECOGNITION_OVERRIDES.get(_stem_of_path(path))
    return entry.threshold if entry is not None else None


def thresholds_of(
    stem: str,
    *,
    search_default: float,
    click_default: float,
    min_default: Optional[float] = None,
):
    """图片资源 ID → (查找阈值, 点击阈值, 下限阈值)。

    未覆盖的字段回退到入参的「步骤上下文默认」，让绝大多数图片无需登记也能
    拿到正确阈值。返回三元组 (search, click, min)；`min` 为 None 表示调用点
    沿用其自身默认（如 `find_transfer_point` 的 `TRANSFER_POINT_MIN`）。

    `stem` 内部做小写归一化，与 `mode_of_path` / `assets.asset_id` 同口径，
    调用点传大写或混写也不会落空。
    """
    entry = RECOGNITION_OVERRIDES.get(stem.lower())
    if entry is None:
        return search_default, click_default, min_default
    return (
        entry.threshold if entry.threshold is not None else search_default,
        entry.click_threshold if entry.click_threshold is not None else click_default,
        entry.min_threshold if entry.min_threshold is not None else min_default,
    )
