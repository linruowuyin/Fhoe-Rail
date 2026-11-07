"""utils/core/map_format.py 的纯逻辑测试 —— v1/v2 双认与迁移不变量。

v2 地图格式（docs/MAP_FORMAT.md）：
    * 顶层加 "v": 2；没有 v 字段 = v1
    * start 图片步骤 {"img": "transfer", "delay": 1.5}（stem + 点击后停顿秒数）
    * rep：本步总执行次数，省略 = 1
    * c：注释，运行时剥掉

核心不变量：normalize（v2 → v1 展开）之后，运行时看到的步骤序列与等价的 v1 完全一致。
"""

from utils.core import map_format as mf


# ---------------------------------------------------------------------------
# normalize_step：v1 原样透传
# ---------------------------------------------------------------------------


class TestV1PassThrough:
    def test_action_step_unchanged(self):
        step = {"a": 0.2}
        assert mf.normalize_step(step) == [step]

    def test_movement_variant_unchanged(self):
        assert mf.normalize_step({"ww": 5.0}) == [{"ww": 5.0}]

    def test_multi_key_start_entry_unchanged(self):
        step = {"picture\\x.png": 0.5, "click_offset": [60, 0], "drag": True}
        assert mf.normalize_step(step) == [step]

    def test_input_not_mutated(self):
        step = {"a": 0.2, "rep": 3}
        mf.normalize_step(step)
        assert step == {"a": 0.2, "rep": 3}

    def test_fighting_unchanged(self):
        assert mf.normalize_step({"fighting": 1}) == [{"fighting": 1}]


# ---------------------------------------------------------------------------
# normalize_step：v2 → v1 展开
# ---------------------------------------------------------------------------


class TestV2Expansion:
    def test_rep_expands_to_n_copies(self):
        assert mf.normalize_step({"a": 0.2, "rep": 3}) == [{"a": 0.2}] * 3

    def test_rep_default_is_1(self):
        assert mf.normalize_step({"a": 0.2}) == [{"a": 0.2}]

    def test_comment_stripped(self):
        assert mf.normalize_step({"a": 0.2, "c": "连点对话"}) == [{"a": 0.2}]

    def test_rep_and_comment_together(self):
        assert mf.normalize_step({"await": 2.0, "rep": 2, "c": "动画"}) == [
            {"await": 2.0}
        ] * 2

    def test_picture_img_to_v1_key(self):
        assert mf.normalize_step({"img": "transfer", "delay": 1.5}) == [
            {"picture\\transfer.png": 1.5}
        ]

    def test_picture_delay_defaults_to_0_8(self):
        assert mf.normalize_step({"img": "transfer"}) == [
            {"picture\\transfer.png": 0.8}
        ]

    def test_picture_modifiers_keep_position_after_step_key(self):
        # 修饰键必须在步骤键之后（分发表取第一个键）；img 转 picture 键后仍排第一
        assert mf.normalize_step(
            {"img": "x", "delay": 0.5, "click_offset": [60, 0], "drag": True}
        ) == [{"picture\\x.png": 0.5, "click_offset": [60, 0], "drag": True}]

    def test_picture_with_rep(self):
        assert mf.normalize_step({"img": "x", "delay": 0.3, "rep": 2}) == [
            {"picture\\x.png": 0.3}
        ] * 2

    def test_picture_rep_with_modifiers_copies_entry(self):
        out = mf.normalize_step({"img": "x", "rep": 2, "click_offset": [1, 2]})
        assert out == [
            {"picture\\x.png": 0.8, "click_offset": [1, 2]},
            {"picture\\x.png": 0.8, "click_offset": [1, 2]},
        ]
        # 两份是独立对象，改一份不影响另一份
        out[0]["click_offset"].append(9)
        assert out[1]["click_offset"] == [1, 2]

    def test_rep_1_normalizes_to_single(self):
        assert mf.normalize_step({"a": 0.2, "rep": 1, "c": "x"}) == [{"a": 0.2}]

    def test_fighting_rep_still_expands(self):
        # 运行时容错地展开（CI 会拦 fighting+rep 的写法）；
        # 展开后 fighting_count 在归一化结果上统计，不会漏计
        assert mf.normalize_step({"fighting": 1, "rep": 2}) == [
            {"fighting": 1}
        ] * 2

    def test_floor_value_list_preserved(self):
        assert mf.normalize_step({"floor": [[1, 2, 3], 2]}) == [
            {"floor": [[1, 2, 3], 2]}
        ]


# ---------------------------------------------------------------------------
# normalize_steps / normalize_map_data
# ---------------------------------------------------------------------------


class TestNormalizeStepsAndMapData:
    def test_flatten_mixed_list(self):
        steps = [{"a": 0.2}, {"img": "x", "rep": 2}, {"b": 1}]
        assert mf.normalize_steps(steps) == [{"a": 0.2}, {"picture\\x.png": 0.8}, {"picture\\x.png": 0.8}, {"b": 1}]

    def test_normalize_map_data_both_arrays(self):
        data = {
            "v": 2,
            "name": "区域-1",
            "author": "a",
            "start": [{"img": "transfer", "delay": 1.5}],
            "map": [{"a": 0.2, "rep": 2}],
        }
        out = mf.normalize_map_data(data)
        assert out["start"] == [{"picture\\transfer.png": 1.5}]
        assert out["map"] == [{"a": 0.2}, {"a": 0.2}]
        # 其它顶层字段原样保留
        assert out["name"] == "区域-1"
        # 输入不被修改
        assert data["start"] == [{"img": "transfer", "delay": 1.5}]
        assert data["map"] == [{"a": 0.2, "rep": 2}]

    def test_normalize_map_data_v1_identity(self):
        data = {"name": "n", "author": "a", "start": [{"b": 1}], "map": [{"w": 2.0}]}
        assert mf.normalize_map_data(data) == data


# ---------------------------------------------------------------------------
# collapse_adjacent：迁移用的相邻合并（严格等价于展开）
# ---------------------------------------------------------------------------


class TestCollapseAdjacent:
    def test_adjacent_identical_merged(self):
        assert mf.collapse_adjacent([{"a": 0.2}] * 3) == [{"a": 0.2, "rep": 3}]

    def test_different_value_not_merged(self):
        steps = [{"a": 0.2}, {"a": 0.3}]
        assert mf.collapse_adjacent(steps) == steps

    def test_non_adjacent_not_merged(self):
        steps = [{"a": 0.2}, {"b": 1}, {"a": 0.2}]
        assert mf.collapse_adjacent(steps) == steps

    def test_fighting_never_collapsed(self):
        # fighting_count 按条数统计，合并会漏计
        assert mf.collapse_adjacent([{"fighting": 1}] * 2) == [{"fighting": 1}, {"fighting": 1}]

    def test_multi_key_entry_not_collapsed(self):
        steps = [
            {"picture\\x.png": 0.5, "click_offset": [1, 2]},
            {"picture\\x.png": 0.5, "click_offset": [1, 2]},
        ]
        assert mf.collapse_adjacent(steps) == steps

    def test_plain_picture_step_collapsed(self):
        assert mf.collapse_adjacent([{"picture\\x.png": 0.5}] * 2) == [
            {"picture\\x.png": 0.5, "rep": 2}
        ]

    def test_collapse_then_expand_round_trip(self):
        steps = [{"a": 0.2}] * 3 + [{"w": 1.0}, {"w": 1.0}] + [{"s": 0.5}]
        assert mf.normalize_steps(mf.collapse_adjacent(steps)) == mf.normalize_steps(steps)

    def test_single_step_unchanged(self):
        assert mf.collapse_adjacent([{"e": 1}]) == [{"e": 1}]

    def test_empty_list(self):
        assert mf.collapse_adjacent([]) == []


# ---------------------------------------------------------------------------
# migrate_map：v1 → v2 全量迁移 + 往返校验
# ---------------------------------------------------------------------------


class TestMigrateMap:
    def test_basic_migration(self):
        data = {
            "name": "区域-1",
            "author": "领航员",
            "start": [
                {"check": 1},
                {"picture\\transfer.png": 1.5},
                {"picture\\map_4-3_point_5.png": 0.8, "click_offset": [60, 0]},
            ],
            "map": [{"a": 0.2}, {"a": 0.2}, {"a": 0.2}, {"w": 2.0}],
        }
        out = mf.migrate_map(data)
        assert list(out) == ["v", "name", "author", "start", "map"]  # v 排第一
        assert out["v"] == 2
        assert out["start"][1] == {"img": "transfer", "delay": 1.5}
        assert out["start"][2] == {
            "img": "map_4-3_point_5",
            "delay": 0.8,
            "click_offset": [60, 0],
        }
        assert out["map"] == [{"a": 0.2, "rep": 3}, {"w": 2.0}]
        # 原数据不被修改
        assert data["map"] == [{"a": 0.2}, {"a": 0.2}, {"a": 0.2}, {"w": 2.0}]

    def test_fighting_not_merged(self):
        data = {
            "name": "n",
            "author": "a",
            "start": [],
            "map": [{"fighting": 1}, {"fighting": 1}, {"e": 1}],
        }
        out = mf.migrate_map(data)
        assert out["map"] == [{"fighting": 1}, {"fighting": 1}, {"e": 1}]

    def test_forward_slash_picture_key_normalized(self):
        # 历史数据里混过 "picture/x.png" 正斜杠写法（asset_id 都能认）
        data = {
            "name": "n",
            "author": "a",
            "start": [{"picture/x.png": 0.8}],
            "map": [],
        }
        out = mf.migrate_map(data)
        assert out["start"] == [{"img": "x", "delay": 0.8}]

    def test_round_trip_verify_ok(self):
        data = {
            "name": "n",
            "author": "a",
            "start": [{"picture\\transfer.png": 1.5}],
            "map": [{"a": 0.2}] * 3,
        }
        out = mf.migrate_map(data)
        assert mf.verify_migration(data, out) is True

    def test_round_trip_verify_detects_tampering(self):
        data = {
            "name": "n",
            "author": "a",
            "start": [],
            "map": [{"a": 0.2}, {"a": 0.2}],
        }
        out = mf.migrate_map(data)
        out["map"][0]["rep"] = 5  # 篡改重复次数
        assert mf.verify_migration(data, out) is False

    def test_migration_idempotent(self):
        data = {
            "name": "n",
            "author": "a",
            "start": [{"picture\\transfer.png": 1.5}],
            "map": [{"a": 0.2}] * 3,
        }
        once = mf.migrate_map(data)
        twice = mf.migrate_map(once)
        assert twice == once

    def test_migrate_deep_copies_modifiers(self):
        data = {
            "name": "n",
            "author": "a",
            "start": [{"picture\\x.png": 0.5, "click_offset": [1, 2]}],
            "map": [],
        }
        out = mf.migrate_map(data)
        assert out["start"][0]["click_offset"] == [1, 2]
        out["start"][0]["click_offset"].append(3)
        assert data["start"][0]["click_offset"] == [1, 2]

    def test_unknown_top_level_keys_kept(self):
        data = {
            "name": "n",
            "author": "a",
            "extra_note": "hi",
            "start": [],
            "map": [],
        }
        out = mf.migrate_map(data)
        assert out["extra_note"] == "hi"


# ---------------------------------------------------------------------------
# 防御性输入
# ---------------------------------------------------------------------------


class TestDefensive:
    def test_rep_zero_treated_as_one(self):
        # CI 拦 rep<1，但运行时不能因此炸
        assert mf.normalize_step({"a": 0.2, "rep": 0}) == [{"a": 0.2}]

    def test_rep_float_truncated_to_int(self):
        assert mf.normalize_step({"a": 0.2, "rep": 2.0}) == [{"a": 0.2}] * 2

    def test_rep_bool_ignored(self):
        assert mf.normalize_step({"a": 0.2, "rep": True}) == [{"a": 0.2}]

    def test_rep_string_ignored(self):
        assert mf.normalize_step({"a": 0.2, "rep": "3"}) == [{"a": 0.2}]

    def test_negative_rep_treated_as_one(self):
        assert mf.normalize_step({"a": 0.2, "rep": -1}) == [{"a": 0.2}]

    def test_huge_rep_capped(self):
        # 手滑写个天文数字，保护运行时（CI 会拦 > 上限）
        assert len(mf.normalize_step({"a": 0.2, "rep": 10**9})) == mf.MAX_REP

    def test_delay_non_number_falls_back(self):
        assert mf.normalize_step({"img": "x", "delay": "0.5"}) == [
            {"picture\\x.png": 0.8}
        ]

    def test_img_non_string_ignored(self):
        # img 不是字符串时整体按 v1 透传，交给 CI 报错
        assert mf.normalize_step({"img": 3, "delay": 0.5}) == [{"img": 3, "delay": 0.5}]

    def test_comment_non_string_still_stripped(self):
        assert mf.normalize_step({"a": 0.2, "c": 123}) == [{"a": 0.2}]

    def test_v1_step_with_c_only(self):
        # 只有 c 没有动作键：没有可执行内容，剥掉后是空对象 → 返回空列表跳过
        assert mf.normalize_step({"c": "纯注释"}) == []


class TestWaitPassthrough:
    """v2 可选字段 wait：normalize 原样透传、migrate 往返保真。

    解析层对它零逻辑（当作普通修饰键），只钉行为防止将来改动悄悄丢字段；
    语义与校验见 utils/core/schema.py 与 docs/MAP_FORMAT.md。
    """

    def test_normalize_img_step_keeps_wait(self):
        assert mf.normalize_step({"img": "transfer", "delay": 1.5, "wait": 2}) == [
            {"picture\\transfer.png": 1.5, "wait": 2}
        ]

    def test_normalize_wait_with_default_delay(self):
        assert mf.normalize_step({"img": "x", "wait": 3}) == [
            {"picture\\x.png": 0.8, "wait": 3}
        ]

    def test_rep_expansion_keeps_wait_in_each_copy(self):
        assert mf.normalize_step(
            {"img": "x", "delay": 0.5, "wait": 2, "rep": 2}
        ) == [
            {"picture\\x.png": 0.5, "wait": 2},
            {"picture\\x.png": 0.5, "wait": 2},
        ]

    def test_collapse_does_not_merge_wait_entries(self):
        steps = [
            {"picture\\x.png": 1.5, "wait": 2},
            {"picture\\x.png": 1.5, "wait": 2},
        ]
        assert mf.collapse_adjacent(steps) == steps

    def test_migrate_map_preserves_wait_and_is_idempotent(self):
        v1 = {
            "name": "n",
            "author": "a",
            "start": [{"picture\\x.png": 1.5, "wait": 2}],
            "map": [],
        }
        v2 = mf.migrate_map(v1)
        assert v2["start"] == [{"img": "x", "delay": 1.5, "wait": 2}]
        assert mf.migrate_map(v2) == v2
        assert mf.verify_migration(v1, v2)
