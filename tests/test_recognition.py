"""utils/vision/recognition.py —— 图片识别参数覆盖层的校验与安全网。

覆盖层的价值在于「每个资产只有一条记录」且「无记录回退默认」。本文件钉住两点：
1. 表里的 key 必须是**真实存在的图片 stem**（拼错 ID 会静默失效，这里拦下）；
2. 字段取值合法（mode 在白名单、阈值在 (0,1)）；
3. 查询 API 的「覆盖优先 / 无覆盖回退默认」行为正确。
"""

import pytest

from utils.vision import assets
from utils.vision import recognition


def _plain_stem(index):
    """从图片索引里挑一个「未被覆盖层登记」的 stem，供回退类测试用。"""
    return next(s for s in index if s not in recognition.RECOGNITION_OVERRIDES)


#: 合法匹配策略白名单（与 `assets` 定义保持一致）。
ALLOWED_MODES = {
    assets.MATCH_COLOR,
    assets.MATCH_SHAPE,
    assets.MATCH_COLOR_CCOEFF,
}


def _picture_index():
    """复用 assets 的 stem 索引，避免各测试重复扫目录。"""
    index, _ = assets.scan_picture_files()
    return index


def test_override_keys_are_real_picture_stems(repo_root):
    """覆盖表里的每个 key 都必须对应磁盘上真实存在的图片。

    拼错 ID（如 `map_6-5_point_2` 写成 `map_6_5_point_2`）不会报错、只是永远命中
    不了，等于白写一条。这里在测试阶段就拦下来。
    """
    index = _picture_index()
    for stem in recognition.RECOGNITION_OVERRIDES:
        assert stem in index, f"覆盖表里的 {stem!r} 不是真实图片 stem（磁盘上找不到对应图）"


def test_override_fields_are_valid():
    """mode 必须在白名单内；阈值必须在 (0, 1) 开区间。"""
    for stem, entry in recognition.RECOGNITION_OVERRIDES.items():
        if entry.mode is not None:
            assert entry.mode in ALLOWED_MODES, f"{stem} 的 mode={entry.mode!r} 非法"
        for field_name in ("threshold", "click_threshold", "min_threshold"):
            value = getattr(entry, field_name)
            if value is not None:
                assert 0 < value < 1, f"{stem} 的 {field_name}={value} 不在 (0, 1)"


def test_mode_of_path_returns_override_for_dream_machine():
    """check_4-1_point_1 在覆盖层登记了 shape，应优先返回 shape。"""
    path = assets.path("check_4-1_point_1")
    assert recognition.mode_of_path(path) == assets.MATCH_SHAPE


def test_mode_of_path_falls_back_to_color_for_plain_point(repo_root):
    """未覆盖的普通点位图应回退到默认 color（不走任何特殊策略）。"""
    index = _picture_index()
    plain = _plain_stem(index)
    assert recognition.mode_of_path(index[plain]) == assets.MATCH_COLOR


def test_thresholds_of_returns_defaults_when_no_override(repo_root):
    """无覆盖时原样返回步骤上下文默认，不影响绝大多数图片。"""
    index = _picture_index()
    plain = _plain_stem(index)
    search, click, min_t = recognition.thresholds_of(
        plain, search_default=0.975, click_default=0.93)
    assert (search, click) == (0.975, 0.93)
    assert min_t is None


def test_map_6_5_points_use_shape_and_point_threshold(repo_root):
    """map_6-5_point_1/2/3 应全部为轮廓识别，查找阈值等于 _MAP_6_5_POINT_THRESHOLD。

    这是对「单独控制某批图的模式与阈值」的端到端校验：模式经 `mode_of_path`、
    运行时查找阈值经 `thresholds_of`、探针阈值经 `threshold_override_of_path` 三处
    都该一致地生效。阈值是实机实测的 0.85，低于 find_transfer_point 默认下限，
    故覆盖层同时写了查找 / 点击 / 下限（避免被默认下限抬回 0.93）。
    """
    expected = recognition._MAP_6_5_POINT_THRESHOLD
    index = _picture_index()
    for stem in ("map_6-5_point_1", "map_6-5_point_2", "map_6-5_point_3"):
        path = index[stem]
        # 模式：轮廓识别
        assert recognition.mode_of_path(path) == assets.MATCH_SHAPE
        # 运行时查找阈值 = 0.85（点击 / 下限同样被覆盖）
        search, click, min_t = recognition.thresholds_of(
            stem, search_default=0.975, click_default=0.93)
        assert search == pytest.approx(expected)
        assert click == pytest.approx(expected)
        assert min_t == pytest.approx(expected)
        # 探针侧可见同一阈值（WebUI meta / CLI 默认）
        assert recognition.threshold_override_of_path(path) == pytest.approx(expected)


def test_thresholds_of_mode_only_override_keeps_threshold_defaults():
    """只覆盖 mode 的条目（如筑梦三张）不应扰动阈值：无阈值字段时回退默认。

    这条防的是「覆盖层只设了 mode，却意外改到阈值」—— 阈值单一来源仍在
    `thresholds.py`，覆盖层只管 mode。
    """
    search, click, min_t = recognition.thresholds_of(
        "check_4-1_point_1",
        search_default=0.975,
        click_default=0.93,
        min_default=0.93,
    )
    assert (search, click, min_t) == (0.975, 0.93, 0.93)


def test_thresholds_of_click_threshold_override_falls_back_search(monkeypatch):
    """覆盖层只写 click_threshold 时，click 取覆盖值、search 回退默认。"""
    monkeypatch.setattr(
        recognition, "RECOGNITION_OVERRIDES",
        {"map_6-5_point_2": recognition.RecognitionEntry("shape", click_threshold=0.88)},
    )
    search, click, min_t = recognition.thresholds_of(
        "map_6-5_point_2", search_default=0.975, click_default=0.93)
    assert search == pytest.approx(0.975)   # 未覆盖 → 默认
    assert click == pytest.approx(0.88)      # 覆盖 → 生效
    assert min_t is None                     # 未覆盖 → 默认(None)


def test_thresholds_of_threshold_override_is_used(monkeypatch):
    """覆盖层写了 threshold 时，运行时（thresholds_of）真的用新值，而非默认。

    这是「覆盖层对运行时生效」的关键路径：单独控制某张图的阈值后，thresholds_of
    必须返回它，而不是悄悄回退到步骤默认。
    """
    monkeypatch.setattr(
        recognition, "RECOGNITION_OVERRIDES",
        {"map_6-5_point_2": recognition.RecognitionEntry(
            "shape", threshold=0.88, click_threshold=0.88)},
    )
    search, click, min_t = recognition.thresholds_of(
        "map_6-5_point_2", search_default=0.975, click_default=0.93,
        min_default=0.93)
    assert search == pytest.approx(0.88)     # 覆盖 → 生效
    assert click == pytest.approx(0.88)      # 覆盖 → 生效
    assert min_t == pytest.approx(0.93)      # 未覆盖 min → 默认


def test_threshold_override_of_path(monkeypatch):
    """threshold_override_of_path 只认覆盖层显式 threshold；无则返回 None。

    探针（WebUI meta / CLI 默认）靠它把覆盖层阈值合并进 `assets.threshold_for_path`。
    """
    monkeypatch.setattr(
        recognition, "RECOGNITION_OVERRIDES",
        {"map_6-5_point_2": recognition.RecognitionEntry(
            "shape", threshold=0.88, click_threshold=0.88)},
    )
    # check_4-1_point_1 覆盖层只设 mode → 无显式 threshold → None
    assert recognition.threshold_override_of_path(
        assets.path("check_4-1_point_1")) is None
    # map_6-5_point_2 显式写了 threshold → 返回它
    assert recognition.threshold_override_of_path(
        "./picture/map_points/6/map_6-5_point_2.webp") == pytest.approx(0.88)
