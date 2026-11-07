"""utils/core/schema.py —— 地图 JSON 校验器。"""

import pytest

from utils.core.schema import MODIFIER_KEYS, Issue, validate_map


def make_map(start=None, map_steps=None, **overrides):
    data = {
        "name": "1-1 空间站「黑塔」",
        "author": "tester",
        "start": start if start is not None else [],
        "map": map_steps if map_steps is not None else [],
    }
    data.update(overrides)
    return data


def levels(issues):
    return [i.level for i in issues]


def messages(issues):
    return " / ".join(i.message for i in issues)


class TestTopLevelStructure:
    def test_valid_minimal_map_passes(self):
        assert validate_map(make_map(), "m.json") == []

    @pytest.mark.parametrize("field", ["name", "author", "start", "map"])
    def test_missing_field_is_an_error(self, field):
        data = make_map()
        del data[field]
        issues = validate_map(data, "m.json")
        assert levels(issues) == ["error"]
        assert field in issues[0].path

    @pytest.mark.parametrize("field", ["name", "author"])
    def test_non_string_field_is_an_error(self, field):
        assert "error" in levels(validate_map(make_map(**{field: 123})))

    @pytest.mark.parametrize("field", ["start", "map"])
    def test_non_list_field_is_an_error(self, field):
        assert "error" in levels(validate_map(make_map(**{field: {}})))

    def test_non_dict_top_level_is_an_error(self):
        issues = validate_map([1, 2, 3])
        assert levels(issues) == ["error"]
        assert "顶层" in issues[0].message

    def test_structure_errors_short_circuit(self):
        """顶层结构都不对时不再往下查，避免一堆噪音。"""
        issues = validate_map({"name": "x"})
        assert all(i.level == "error" for i in issues)
        assert len(issues) == 3  # author / start / map


class TestStartEntries:
    def test_known_step_passes(self):
        assert validate_map(make_map(start=[{"map": 1}])) == []

    def test_picture_point_passes(self):
        assert validate_map(make_map(start=[{"picture\\1-1_point_1.png": 1.5}])) == []

    def test_modifier_after_step_passes(self):
        entry = {"picture\\map_4-1_point_7.png": 1.5, "drag": 1.5}
        assert validate_map(make_map(start=[entry])) == []

    def test_unknown_key_is_a_warning(self):
        issues = validate_map(make_map(start=[{"not_a_step": 1}]))
        assert levels(issues) == ["warning"]

    def test_non_numeric_value_is_an_error(self):
        issues = validate_map(make_map(start=[{"await": "两秒"}]))
        assert levels(issues) == ["error"]

    def test_empty_entry_is_an_error(self):
        assert validate_map(make_map(start=[{}]))[0].level == "error"

    def test_non_dict_entry_is_an_error(self):
        assert validate_map(make_map(start=["map"]))[0].level == "error"

    def test_unknown_modifier_is_a_warning(self):
        entry = {"picture\\x.png": 1.0, "typo_modifier": 1}
        issues = validate_map(make_map(start=[entry]))
        assert levels(issues) == ["warning"]
        assert "typo_modifier" in issues[0].path

    @pytest.mark.parametrize("modifier", sorted(MODIFIER_KEYS))
    def test_modifier_as_first_key_is_an_error(self, modifier):
        """键顺序有意义：分发表取 `list(keys())[0]` 当步骤键。

        把修饰键写在第一个位置，分发表会把 "drag" 当成图片路径去查 ——
        不报错，只是静默走错分支。这是校验器存在的核心理由之一。
        """
        issues = validate_map(make_map(start=[{modifier: 1, "picture\\x.png": 1.0}]))
        assert levels(issues) == ["error"]
        assert "修饰键" in issues[0].message


class TestClickOffsetModifier:
    """`click_offset` 是「静态锚点 → 可点热区」的平移量。

    形状错必须在进游戏前拦住：运行时它只是两个下标加法，错了不报错、只会点偏。
    """

    def test_click_offset_is_a_known_modifier(self):
        entry = {"picture\\x.png": 1.5, "click_offset": [60, 0]}
        assert validate_map(make_map(start=[entry])) == []

    @pytest.mark.parametrize("value", [[60], [60, 0, 0], 60, ["60", 0], None])
    def test_malformed_click_offset_is_an_error(self, value):
        entry = {"picture\\x.png": 1.5, "click_offset": value}

        issues = validate_map(make_map(start=[entry]))

        assert levels(issues) == ["error"]
        assert "click_offset" in issues[0].path


class TestFloorStep:
    def test_valid_floor_passes(self):
        assert validate_map(make_map(start=[{"floor": [[0, 1, 2], 1]}])) == []

    def test_floor_with_target_not_in_list_is_an_error(self):
        issues = validate_map(make_map(start=[{"floor": [[0, 1], 99]}]))
        assert levels(issues) == ["error"]
        assert "arr.index" in issues[0].message

    def test_floor_with_wrong_arity_is_an_error(self):
        assert validate_map(make_map(start=[{"floor": [0, 1, 2]}]))[0].level == "error"

    def test_floor_with_non_list_first_element_is_an_error(self):
        assert validate_map(make_map(start=[{"floor": ["abc", "a"]}]))[0].level == "error"


class TestCheckStep:
    def test_start_check_accepts_one_or_weekday_list(self):
        assert validate_map(make_map(start=[{"check": 1}])) == []
        assert validate_map(make_map(start=[{"check": [0, 4]}])) == []

    def test_start_check_rejects_other_values(self):
        assert validate_map(make_map(start=[{"check": "周一"}]))[0].level == "error"

    def test_map_check_accepts_number_or_list(self):
        assert validate_map(make_map(map_steps=[{"check": 1}])) == []
        assert validate_map(make_map(map_steps=[{"check": [0, 4]}])) == []


class TestMapEntries:
    @pytest.mark.parametrize("value", [1, 2])
    def test_fighting_accepts_one_and_two(self, value):
        assert validate_map(make_map(map_steps=[{"fighting": value}])) == []

    @pytest.mark.parametrize("value", [0, 3, "1"])
    def test_fighting_rejects_other_values(self, value):
        issues = validate_map(make_map(map_steps=[{"fighting": value}]))
        assert levels(issues) == ["error"]

    def test_multi_key_map_entry_is_an_error(self):
        """map 条目必须是单键 —— 分发表用 next(iter(items())) 取第一个。"""
        issues = validate_map(make_map(map_steps=[{"fighting": 1, "await": 1}]))
        assert levels(issues) == ["error"]

    def test_lv999_e_accepts_one(self):
        assert validate_map(make_map(map_steps=[{"lv999_e": 1}])) == []

    @pytest.mark.parametrize("value", [0, 2, "1"])
    def test_lv999_e_rejects_other_values(self, value):
        issues = validate_map(make_map(map_steps=[{"lv999_e": value}]))
        assert levels(issues) == ["error"]

    def test_lv999_fighting_accepts_one(self):
        assert validate_map(make_map(map_steps=[{"lv999_fighting": 1}])) == []

    @pytest.mark.parametrize("value", [0, 2, "1"])
    def test_lv999_fighting_rejects_other_values(self, value):
        issues = validate_map(make_map(map_steps=[{"lv999_fighting": value}]))
        assert levels(issues) == ["error"]

    def test_lv999_await_accepts_a_number(self):
        assert validate_map(make_map(map_steps=[{"lv999_await": 2}])) == []

    @pytest.mark.parametrize("value", ["2", None])
    def test_lv999_await_rejects_non_numbers(self, value):
        issues = validate_map(make_map(map_steps=[{"lv999_await": value}]))
        assert levels(issues) == ["error"]

    def test_double_movement_keys_pass(self):
        steps = [{"ww": 1.5}, {"aa": 0.8}, {"ss": 0.5}, {"dd": 2}]
        assert validate_map(make_map(map_steps=steps)) == []

    def test_movement_key_passes(self):
        assert validate_map(make_map(map_steps=[{"w": 1.5}, {"d": 0.5}])) == []


class TestIssue:
    def test_issue_renders_level_and_path(self):
        text = str(Issue("error", "m.json.map[0].fighting", "值不对"))
        assert text == "[error] m.json.map[0].fighting: 值不对"


# ---------------------------------------------------------------------------
# v2 格式（"v": 2）—— img / delay / rep / c
# ---------------------------------------------------------------------------


class TestV2TopLevel:
    def test_valid_v2_map_passes(self):
        data = make_map(
            start=[{"img": "transfer", "delay": 1.5}],
            map_steps=[{"a": 0.2, "rep": 3, "c": "连点"}],
            v=2,
        )
        assert validate_map(data) == []

    @pytest.mark.parametrize("value", [1, "2", 2.0, True, None])
    def test_bad_version_value_is_an_error(self, value):
        issues = validate_map(make_map(v=value))
        assert levels(issues) == ["error"]
        assert issues[0].path.endswith(".v")

    def test_v1_file_with_reserved_keys_is_an_error(self):
        data = make_map(map_steps=[{"a": 0.2, "rep": 2}])
        issues = validate_map(data)
        assert levels(issues) == ["error"]
        assert "v" in issues[0].message

    def test_v1_file_with_img_in_start_is_an_error(self):
        data = make_map(start=[{"img": "transfer", "delay": 1.5}])
        issues = validate_map(data)
        assert levels(issues) == ["error"]

    def test_v1_file_with_c_in_map_is_an_error(self):
        data = make_map(map_steps=[{"e": 1, "c": "注释"}])
        assert levels(validate_map(data)) == ["error"]


class TestV2StartEntries:
    def test_img_step_passes(self):
        data = make_map(start=[{"img": "transfer", "delay": 1.5}], v=2)
        assert validate_map(data) == []

    def test_img_step_without_delay_passes(self):
        data = make_map(start=[{"img": "transfer"}], v=2)
        assert validate_map(data) == []

    def test_img_step_with_modifiers_passes(self):
        data = make_map(
            start=[{"img": "x", "delay": 0.5, "click_offset": [60, 0], "drag": True}],
            v=2,
        )
        assert validate_map(data) == []

    def test_v1_picture_key_in_v2_file_is_an_error(self):
        data = make_map(start=[{"picture\\transfer.png": 1.5}], v=2)
        issues = validate_map(data)
        assert levels(issues) == ["error"]
        assert "img" in issues[0].message

    @pytest.mark.parametrize("stem", ["picture/x.png", "x.png", "a/b", "", " x", "x y"])
    def test_bad_img_stem_is_an_error(self, stem):
        data = make_map(start=[{"img": stem}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_delay_non_number_is_an_error(self):
        data = make_map(start=[{"img": "x", "delay": "0.5"}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_modifier_first_is_still_an_error(self):
        data = make_map(start=[{"delay": 0.5, "img": "x"}], v=2)
        issues = validate_map(data)
        assert levels(issues) == ["error"]
        assert "修饰键" in issues[0].message or "步骤键" in issues[0].message

    def test_unknown_extra_key_is_an_error(self):
        data = make_map(start=[{"img": "x", "whatever": 1}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_action_start_step_keeps_v1_rules(self):
        # v2 文件里的动作步沿用 v1 语义：已知键、check/floor 形状等
        data = make_map(start=[{"await": 1.0}], v=2)
        assert validate_map(data) == []

    def test_rep_bad_value_is_an_error(self):
        for rep in [0, -1, 1.5, "3", True]:
            data = make_map(start=[{"await": 1.0, "rep": rep}], v=2)
            assert levels(validate_map(data)) == ["error"], rep

    def test_c_non_string_is_an_error(self):
        data = make_map(start=[{"await": 1.0, "c": 123}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_img_step_with_rep_passes(self):
        data = make_map(start=[{"img": "x", "rep": 2}], v=2)
        assert validate_map(data) == []


class TestV2MapEntries:
    def test_action_step_with_rep_and_c_passes(self):
        data = make_map(map_steps=[{"a": 0.2, "rep": 3, "c": "连点"}], v=2)
        assert validate_map(data) == []

    def test_img_in_map_is_an_error(self):
        data = make_map(map_steps=[{"img": "x", "delay": 0.5}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_modifier_in_map_is_an_error(self):
        data = make_map(map_steps=[{"a": 0.2, "click_offset": [1, 2]}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_fighting_with_rep_is_an_error(self):
        # fighting_count 按条数统计，rep 合并会漏计
        data = make_map(map_steps=[{"fighting": 1, "rep": 2}], v=2)
        assert levels(validate_map(data)) == ["error"]

    def test_unknown_action_key_warns_as_in_v1(self):
        data = make_map(map_steps=[{"zzz": 1.0}], v=2)
        assert "warning" in levels(validate_map(data))

    def test_fighting_value_rule_still_applies(self):
        data = make_map(map_steps=[{"fighting": 9}], v=2)
        assert levels(validate_map(data)) == ["error"]
