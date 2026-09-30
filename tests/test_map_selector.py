"""utils/ui/map_selector.py —— 起始地图选择菜单。

注意：本模块在 import 时就构造了模块级单例 `cfg`，而 modify_json_file 是
「读文件 → 改 → 写文件」，不看内存缓存。所以这里一律改磁盘上的 config.json，
再让 cfg 失效重读。
"""

import json
from types import SimpleNamespace

import pytest

import utils.ui.map_selector as selector_module
from utils.ui.map_selector import (
    _build_main_map_opts,
    _h_allowlist,
    _h_main_map,
    _h_priority,
    _h_side_map,
    choose_map,
    choose_map_debug,
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
    monkeypatch.setattr(selector_module, "questionary", fake)
    return fake


def set_config_file(root, **values):
    path = root / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(values)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    selector_module.cfg._config = None
    selector_module.cfg._last_mtime = None


def read_config_file(root, key):
    return json.loads((root / "config.json").read_text(encoding="utf-8"))[key]


@pytest.fixture(autouse=True)
def fresh_selector(monkeypatch):
    monkeypatch.setattr(
        selector_module.MapInfo, "read_maps", staticmethod(lambda map_version: ([], {}))
    )
    selector_module.cfg._config = None
    selector_module.cfg._last_mtime = None
    yield
    selector_module.cfg._config = None
    selector_module.cfg._last_mtime = None


@pytest.fixture
def map_info():
    return SimpleNamespace(
        map_list_map={
            "1": {
                "1_0": ["1-1 空间站「黑塔」", "1-1 1"],
                "2_0": ["1-2 收容舱段", "1-2 1"],
            },
            "2": {"1_0": ["2-1 残响回廊", "2-1 2"]},
        }
    )


class TestBuildMainMapOpts:
    def test_labels_each_planet(self, map_info):
        assert _build_main_map_opts(map_info) == {"1 黑塔": "1", "2 雅利洛": "2"}

    def test_unknown_planet_gets_a_fallback_label(self):
        info = SimpleNamespace(map_list_map={"9": {}})
        assert _build_main_map_opts(info) == {"9 未知星球": "9"}


class TestChooseMap:
    def test_uses_configured_main_map(self, map_info, isolated_cwd):
        set_config_file(isolated_cwd, map_version="default", main_map="2")

        assert choose_map(map_info) == ("2-1_0", True)

    def test_falls_back_to_smallest_planet_when_unset(self, map_info, isolated_cwd):
        set_config_file(isolated_cwd, main_map=None)

        assert choose_map(map_info) == ("1-1_0", True)

    def test_invalid_main_map_falls_back_without_touching_config(
        self, map_info, isolated_cwd
    ):
        """回退只作用于本次运行，不写回配置。

        写回去等于「用户没改设置，设置却被改了」——切回原来的地图版本跑完整锄大地
        时，起点和顺序都变了，而且很难联想到是上次跑了别的版本造成的。
        """
        set_config_file(isolated_cwd, main_map="42")

        assert choose_map(map_info) == ("1-1_0", True)
        assert read_config_file(isolated_cwd, "main_map") == "42", (
            "回退不该改配置；用户在菜单里主动选「优先星球」的那处写入才该落盘"
        )

    def test_picks_the_first_side_map_of_the_planet(self, map_info, isolated_cwd):
        set_config_file(isolated_cwd, main_map="1")

        main, is_allowlist = choose_map(map_info)

        assert main.startswith("1-")
        assert is_allowlist is True


class TestAllowlistChoice:
    def test_enables_one_shot_allowlist_mode(self, isolated_cwd):
        set_config_file(isolated_cwd, allowlist_map=["1"])

        assert _h_allowlist() == ("1-1_0", False)
        assert read_config_file(isolated_cwd, "allowlist_mode_once") is True

    def test_returns_back_when_allowlist_is_empty(self, isolated_cwd, capsys):
        set_config_file(isolated_cwd, allowlist_map=[])

        assert _h_allowlist() == "back"
        assert "请配置allowlist_map的值" in capsys.readouterr().out


class TestMainMapMenu:
    def test_planet_choice_returns_its_id(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["2 雅利洛"])
        assert _h_main_map(map_info) == "2"

    def test_cancel_returns_none(self, map_info, monkeypatch):
        use_questionary(monkeypatch, [None])
        assert _h_main_map(map_info) is None


class TestPriorityMenu:
    def test_choice_is_written_to_config(self, map_info, monkeypatch, isolated_cwd):
        use_questionary(monkeypatch, ["2 雅利洛"])

        assert _h_priority(map_info) == ("2-1_0", True)
        assert read_config_file(isolated_cwd, "main_map") == "2", (
            "用户主动选「优先星球」这一处才该落盘"
        )

    def test_back_returns_back(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["【返回】"])
        assert _h_priority(map_info) == "back"

    def test_cancel_returns_back(self, map_info, monkeypatch):
        use_questionary(monkeypatch, [None])
        assert _h_priority(map_info) == "back"


class TestSideMapMenu:
    def test_second_then_third_level(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["1-1 1", "1-1 空间站「黑塔」"])
        assert _h_side_map(map_info, "1") == ("1-1_0", False)

    def test_back_at_second_level(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["【返回】"])
        assert _h_side_map(map_info, "1") == "back"

    def test_back_at_third_level(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["1-1 1", "【返回】"])
        assert _h_side_map(map_info, "1") == "back"

    def test_unknown_planet_returns_none_without_asking(self, monkeypatch):
        fake = use_questionary(monkeypatch, [])
        assert _h_side_map(SimpleNamespace(map_list_map={}), "9") is None
        assert fake.titles == []


class TestChooseMapDebug:
    def test_planet_then_side_map(self, map_info, monkeypatch):
        use_questionary(monkeypatch, ["1 黑塔", "1-1 1", "1-1 空间站「黑塔」"])
        assert choose_map_debug(map_info) == ("1-1_0", False)

    def test_back_at_the_side_menu_returns_to_the_planet_menu(self, map_info, monkeypatch):
        use_questionary(
            monkeypatch, ["1 黑塔", "【返回】", "2 雅利洛", "2-1 2", "2-1 残响回廊"]
        )
        assert choose_map_debug(map_info) == ("2-1_0", False)

    def test_priority_short_circuits_with_a_tuple(self, map_info, monkeypatch, isolated_cwd):
        use_questionary(monkeypatch, ["优先星球", "2 雅利洛"])
        assert choose_map_debug(map_info) == ("2-1_0", True)

    def test_settings_entry_returns_to_the_planet_menu(self, map_info, monkeypatch):
        seen = []
        monkeypatch.setattr(
            selector_module,
            "setting",
            SimpleNamespace(set_config=lambda slot: seen.append(slot)),
        )
        use_questionary(
            monkeypatch, ["[设置]", "1 黑塔", "1-1 1", "1-1 空间站「黑塔」"]
        )

        assert choose_map_debug(map_info) == ("1-1_0", False)
        assert seen == ["start_rewrite"], "[设置] 走的是重写配置那个 slot"

    def test_scheduled_entry_returns_immediately(self, map_info, monkeypatch):
        monkeypatch.setattr(
            selector_module.TimeUtils, "wait_and_run", staticmethod(lambda: None)
        )
        use_questionary(monkeypatch, ["[定时]"])
        assert choose_map_debug(map_info) == ("1-1_0", False)
