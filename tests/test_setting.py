"""utils/ui/setting.py —— 设置菜单的问题表与地图名解析。"""

from types import SimpleNamespace

import pytest

import utils.ui.setting as setting_module
from utils.config.config import ConfigurationManager
from utils.ui.setting import Setting


@pytest.fixture
def setting(make_instance, isolated_cwd):
    (isolated_cwd / "map" / "default").mkdir(parents=True)
    return make_instance(
        Setting, cfg=ConfigurationManager(), config={}, map_info=None
    )


class TestGetPureMapName:
    """输入形如 format_map_data_first_name 的产出："1-1 空间站「黑塔」"。"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1-1 空间站「黑塔」", "空间站「黑塔」"),
            ("2-3 雅利洛-Ⅵ 大矿区", "雅利洛"),
            ("5-1 翁法罗斯", "翁法罗斯"),
            ("6-2 二相乐园—派系", "二相乐园"),
            ("3-4 罗浮-丹鼎司", "罗浮"),
        ],
    )
    def test_extracts_the_map_name(self, setting, raw, expected):
        assert setting.get_pure_map_name(raw) == expected

    def test_keeps_spaces_inside_the_name(self, setting):
        assert setting.get_pure_map_name("4-1 匹诺康尼 梦境-白日梦酒店") == "匹诺康尼 梦境"

    def test_name_without_prefix_is_unchanged(self, setting):
        assert setting.get_pure_map_name("翁法罗斯") == "翁法罗斯"

    def test_empty_string_is_handled(self, setting):
        assert setting.get_pure_map_name("") == ""


class TestGetQuestionsForSlot:
    def test_start_slot_has_questions(self, setting):
        assert setting.get_questions_for_slot("start")

    def test_start_rewrite_mirrors_start(self, setting):
        """两个 slot 共用同一份定义，但每次调用都会重建闭包，只能比较结构。"""
        start = setting.get_questions_for_slot("start")
        rewrite = setting.get_questions_for_slot("start_rewrite")
        assert [q["title"] for q in rewrite] == [q["title"] for q in start]
        assert [q["config_key"] for q in rewrite] == [q["config_key"] for q in start]

    def test_unknown_slot_returns_empty(self, setting):
        assert setting.get_questions_for_slot("not_a_slot") == []

    def test_every_question_has_required_fields(self, setting):
        for question in setting.get_questions_for_slot("start"):
            assert {"title", "choices", "config_key"} <= set(question)

    def test_titles_are_unique(self, setting):
        questions = setting.get_questions_for_slot("start")
        titles = [q["title"] for q in questions]
        assert len(set(titles)) == len(titles), "重复标题会让菜单项无法区分"

    @pytest.mark.xfail(
        strict=True,
        reason="菜单里的 auto_use_technique_consumable 不在 ConfigurationManager.config_keys() 中，"
        "因此它既不在默认配置里，也不会被 ensure_config_complete 补齐（config_fix 却会写它）",
    )
    def test_every_config_key_exists_in_defaults(self, setting):
        keys = {q["config_key"] for q in setting.get_questions_for_slot("start")}
        assert keys <= set(ConfigurationManager.config_keys())

    def test_choice_values_are_hashable(self, setting):
        for question in setting.get_questions_for_slot("start"):
            choices = question["choices"]
            if callable(choices):
                continue
            for label, value in choices.items():
                assert isinstance(label, str)
                assert hash(value) is not None


class TestGetMainMapChoices:
    def test_maps_planet_ids_to_names(self, setting, monkeypatch):
        monkeypatch.setattr(
            setting_module.MapInfo,
            "read_maps",
            staticmethod(lambda version: ([], {"1": {}, "3": {}})),
        )

        choices = setting.get_main_map_choices({"map_version": "default"}, None)

        assert choices == {"黑塔": "1", "罗浮": "3"}

    def test_unknown_planet_id_is_labelled(self, setting, monkeypatch):
        monkeypatch.setattr(
            setting_module.MapInfo,
            "read_maps",
            staticmethod(lambda version: ([], {"9": {}})),
        )

        assert setting.get_main_map_choices({}, None) == {"未知星球9": "9"}

    def test_planet_ids_are_sorted_numerically(self, setting, monkeypatch):
        monkeypatch.setattr(
            setting_module.MapInfo,
            "read_maps",
            staticmethod(lambda version: ([], {"10": {}, "2": {}})),
        )

        assert list(setting.get_main_map_choices({}, None)) == ["雅利洛", "未知星球10"]


class TestPlanetSelection:
    def test_selected_label_maps_back_to_planet_id(self, setting, monkeypatch):
        captured = {}

        class FakeQuestionary:
            @staticmethod
            def select(title, choices):
                captured["choices"] = choices
                return SimpleNamespace(ask=lambda: "3 罗浮")

        monkeypatch.setattr(setting_module, "questionary", FakeQuestionary)

        assert setting._h_select_planet() == "3"
        assert "1 黑塔" in captured["choices"]

    def test_cancel_returns_none(self, setting, monkeypatch):
        class FakeQuestionary:
            @staticmethod
            def select(title, choices):
                return SimpleNamespace(ask=lambda: None)

        monkeypatch.setattr(setting_module, "questionary", FakeQuestionary)

        assert setting._h_select_planet() is None
