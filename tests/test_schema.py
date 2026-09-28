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

    def test_movement_key_passes(self):
        assert validate_map(make_map(map_steps=[{"w": 1.5}, {"d": 0.5}])) == []


class TestIssue:
    def test_issue_renders_level_and_path(self):
        text = str(Issue("error", "m.json.map[0].fighting", "值不对"))
        assert text == "[error] m.json.map[0].fighting: 值不对"
