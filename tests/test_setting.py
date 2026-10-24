"""utils/ui/setting.py —— 设置菜单的问题表、地图名解析与交互流程。"""

import json
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


class FakeQuestionary:
    """按顺序吐出预设答案的 questionary 替身。答案用尽后返回 None（= 用户取消）。"""

    def __init__(self, answers):
        self.answers = list(answers)
        self.titles = []
        self.choices = []

    def select(self, title, choices):
        self.titles.append(title)
        self.choices.append(list(choices))
        answer = self.answers.pop(0) if self.answers else None
        return SimpleNamespace(ask=lambda: answer)


def use_questionary(monkeypatch, answers):
    fake = FakeQuestionary(answers)
    monkeypatch.setattr(setting_module, "questionary", fake)
    return fake


def menu_answer(setting, config_key):
    """拼出主菜单里那一项的文本。

    只有 `------` **前面**那段（标题）会被用来反查问题，括号里的当前值只是显示用。
    """
    question = next(
        q for q in setting.get_questions_for_slot("start")
        if q["config_key"] == config_key
    )
    title = question.get("dynamic_title", lambda _: question["title"])(setting.config)
    return f"{title}------(当前值)"


def saved_config(root):
    return json.loads((root / "config.json").read_text(encoding="utf-8"))


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


class TestSetConfigFlow:
    """set_config 的主循环：选一项 → 改 → 存盘。之前整段没有覆盖。"""

    def test_unknown_slot_returns_without_asking(self, setting, monkeypatch):
        fake = use_questionary(monkeypatch, [])
        setting.set_config(slot="没有这个slot")
        assert fake.titles == [], "slot 不认识时不该弹菜单"

    def test_return_saves_nothing(self, setting, monkeypatch, isolated_cwd):
        before = saved_config(isolated_cwd)
        use_questionary(monkeypatch, ["【返回】"])
        setting.set_config()
        assert saved_config(isolated_cwd) == before, "「返回」不该写盘"

    def test_cancel_at_the_main_menu_returns_instead_of_crashing(
        self, setting, monkeypatch, isolated_cwd
    ):
        """用户按 Ctrl-C / Esc 时 questionary 返回 None。

        曾经这里直接 `answer.split("------")`，于是
        `AttributeError: 'NoneType' object has no attribute 'split'` —— 整个设置菜单崩。
        """
        before = saved_config(isolated_cwd)
        use_questionary(monkeypatch, [None])
        setting.set_config()
        assert saved_config(isolated_cwd) == before

    def test_normal_key_is_written_and_saved(self, setting, monkeypatch, isolated_cwd):
        setting.config = dict(saved_config(isolated_cwd))
        use_questionary(
            monkeypatch, [menu_answer(setting, "auto_shutdown"), "关机", "【返回】"]
        )
        setting.set_config()
        assert saved_config(isolated_cwd)["auto_shutdown"] == 1

    def test_cancelling_the_value_prompt_keeps_the_old_value(
        self, setting, monkeypatch, isolated_cwd
    ):
        setting.config = dict(saved_config(isolated_cwd))
        use_questionary(monkeypatch, [menu_answer(setting, "auto_shutdown"), None, "【返回】"])
        setting.set_config()
        assert saved_config(isolated_cwd)["auto_shutdown"] == 0

    def test_special_key_goes_through_the_dedicated_flow(
        self, setting, monkeypatch, isolated_cwd
    ):
        setting.config = {"forbid_map": ["1-1"]}
        fake = use_questionary(
            monkeypatch, [menu_answer(setting, "forbid_map"), "【返回】", "【返回】"]
        )
        setting.set_config()
        assert any("已禁用" in t for t in fake.titles), "特殊项走的是带动态标题的子菜单"


class TestSpecialConfigFlow:
    def test_cancel_breaks_out_instead_of_crashing(
        self, setting, monkeypatch, isolated_cwd
    ):
        """同一个 None：曾经落进 `current_choices[None]` 抛 KeyError。"""
        setting.config = {"forbid_map": ["1-1"]}
        use_questionary(
            monkeypatch, [menu_answer(setting, "forbid_map"), None, "【返回】"]
        )
        setting.set_config()
        # 取消必须什么都不做：既不能崩，也不能顺手增删条目。
        # （set_config 结束时会把重新读到的配置整份存盘，所以这里比的是文件里的原值）
        assert saved_config(isolated_cwd)["forbid_map"] == []

    def test_removing_an_entry_writes_it_through(self, setting, monkeypatch, isolated_cwd):
        setting.config = {"forbid_map": ["1-1", "2-1"]}
        use_questionary(
            monkeypatch,
            [menu_answer(setting, "forbid_map"), "【删除】", "1-1", "【返回】", "【返回】"],
        )
        setting.set_config()
        assert saved_config(isolated_cwd)["forbid_map"] == ["2-1"]

    def test_adding_a_map_appends_its_clean_name(
        self, setting, monkeypatch, isolated_cwd
    ):
        setting.config = {"map_version": "default", "forbid_map": []}
        setting.map_info = SimpleNamespace(
            map_list_map={"1": {"1_0": ["空间站「黑塔」", "1-1 空间站「黑塔」"]}}
        )
        monkeypatch.setattr(
            setting_module.MapInfo, "read_maps", staticmethod(lambda map_version: ([], {}))
        )
        use_questionary(
            monkeypatch,
            [
                menu_answer(setting, "forbid_map"),
                "【新增】",
                "1 黑塔",
                "空间站「黑塔」 (1个子地图)",
                "【返回】",
                "【返回】",
            ],
        )
        setting.set_config()
        assert saved_config(isolated_cwd)["forbid_map"] == ["空间站「黑塔」"]


class TestCleanMapSelection:
    def test_picks_the_clean_name(self, setting, monkeypatch, isolated_cwd):
        setting.config = {"map_version": "default"}
        map_info = SimpleNamespace(
            map_list_map={
                "1": {
                    "1_0": ["空间站「黑塔」", "1-1 空间站「黑塔」"],
                    "2_0": ["收容舱段", "1-2 收容舱段"],
                }
            }
        )
        monkeypatch.setattr(
            setting_module.MapInfo, "read_maps", staticmethod(lambda map_version: ([], {}))
        )
        fake = use_questionary(monkeypatch, ["空间站「黑塔」 (1个子地图)"])

        assert setting._h_select_clean_map(map_info, "1") == "空间站「黑塔」"
        assert set(fake.choices[0]) == {
            "空间站「黑塔」 (1个子地图)",
            "收容舱段 (1个子地图)",
            "返回上级",
        }

    def test_unknown_planet_returns_back(self, setting, monkeypatch):
        monkeypatch.setattr(
            setting_module.MapInfo, "read_maps", staticmethod(lambda map_version: ([], {}))
        )
        assert setting._h_select_clean_map(SimpleNamespace(map_list_map={}), "9") == "back"

    def test_returning_upstairs_returns_back(self, setting, monkeypatch):
        monkeypatch.setattr(
            setting_module.MapInfo, "read_maps", staticmethod(lambda map_version: ([], {}))
        )
        map_info = SimpleNamespace(
            map_list_map={"1": {"1_0": ["空间站「黑塔」", "1-1 空间站「黑塔」"]}}
        )
        use_questionary(monkeypatch, ["返回上级"])
        assert setting._h_select_clean_map(map_info, "1") == "back"
