"""utils/flows/map.py —— 地图拖动、传送点查找与开关解析。"""

from types import SimpleNamespace

import pytest

import utils.flows.map as map_module
from utils.config.config import ConfigurationManager
from utils.core.map_move import MAP_MOVE_NAV_DATA
from utils.flows.map import Map


@pytest.fixture
def game_map(make_instance, monkeypatch):
    monkeypatch.setattr(map_module.time, "sleep", lambda seconds: None)
    return make_instance(
        Map,
        cfg=ConfigurationManager(),
        map_info=SimpleNamespace(map_list=[]),
        mouse_event=SimpleNamespace(mouse_drag=lambda *a, **k: None),
        img=SimpleNamespace(),
        handle=SimpleNamespace(),
        monthly_pass=SimpleNamespace(monthly_pass_check=lambda: None),
        planet_png_lst=["picture\\orientation_2.png"],
        planet=None,
        map_statu_minimize=False,
        allowlist_mode=False,
        # 替身也要有闸门（真实 Map.__init__ 里默认为 no-op）：返回「被暂停的秒数」
        pause_gate=lambda: 0.0,
        click_offset=(0, 0),
    )


class TestDirections:
    def test_reads_the_16_9_table(self, game_map):
        assert game_map._directions() == MAP_MOVE_NAV_DATA["16:9"]["directions"]

    def test_table_has_all_five_directions(self):
        assert set(MAP_MOVE_NAV_DATA["16:9"]["directions"]) == {
            "down",
            "left",
            "up",
            "right",
            "up_left",
        }


class TestGetMapList:
    @pytest.fixture
    def ordered(self, game_map):
        game_map.map_info = SimpleNamespace(
            map_list=["map_1-1_0.json", "map_2-1_0.json", "map_3-1_0.json"]
        )
        return game_map

    def test_slices_from_the_start_map(self, ordered):
        assert ordered.get_map_list("2-1_0") == [
            "map_2-1_0.json",
            "map_3-1_0.json",
        ]

    def test_start_in_mid_wraps_around(self, ordered):
        assert ordered.get_map_list("3-1_0", start_in_mid=True) == [
            "map_3-1_0.json",
            "map_1-1_0.json",
            "map_2-1_0.json",
        ]

    def test_unknown_start_raises(self, ordered):
        with pytest.raises(ValueError):
            ordered.get_map_list("9-9_9")


class TestAllowFlags:
    def test_map_drag_defaults_to_disabled(self, game_map):
        game_map.allow_map_drag({})
        assert game_map.allow_drap_map_switch is False
        assert game_map.drag_exact is None
        assert game_map.drag_offset is None

    def test_map_drag_exact_and_offset_are_loaded(self, game_map):
        game_map.allow_map_drag(
            {"drag": True, "drag_exact": [1, 2, 3], "drag_offset": [0, 1, 0, 1]}
        )
        assert game_map.allow_drap_map_switch is True
        assert game_map.drag_exact == [1, 2, 3]
        assert game_map.drag_offset == [0, 1, 0, 1]

    def test_drag_exact_ignored_when_drag_disabled(self, game_map):
        game_map.allow_map_drag({"drag_exact": [1, 2, 3]})
        assert game_map.drag_exact is None

    def test_scene_drag_defaults_to_disabled(self, game_map):
        game_map.allow_scene_drag({})
        assert game_map.allow_scene_drag_switch is False

    def test_scene_drag_can_be_enabled(self, game_map):
        game_map.allow_scene_drag({"scene": True})
        assert game_map.allow_scene_drag_switch is True

    def test_multi_click_defaults_to_single(self, game_map):
        game_map.allow_multi_click({})
        assert (game_map.multi_click, game_map.allow_multi_click_switch) == (1, False)

    def test_multi_click_count_is_loaded(self, game_map):
        game_map.allow_multi_click({"clicks": 3})
        assert (game_map.multi_click, game_map.allow_multi_click_switch) == (3, True)

    def test_retry_in_map_defaults_to_allowed(self, game_map):
        game_map.allow_retry_in_map({})
        assert game_map.allow_retry_in_map_switch is True

    def test_forbid_retry_disables_it(self, game_map):
        game_map.allow_retry_in_map({"forbid_retry": True})
        assert game_map.allow_retry_in_map_switch is False

    def test_click_offset_defaults_to_no_shift(self, game_map):
        game_map.allow_click_offset({})
        assert game_map.click_offset == (0, 0)

    def test_click_offset_is_loaded(self, game_map):
        """静态锚点与可点热区不重合时声明这个键（例如向右 60 像素）。"""
        game_map.allow_click_offset(
            {"picture\\orientation_7.png": 1.5, "click_offset": [60, 0]}
        )
        assert game_map.click_offset == (60, 0)

    def test_click_offset_resets_on_the_next_step(self, game_map):
        """上一条步骤的偏移不能带到下一条 —— 否则后面所有点击都会整体偏掉。"""
        game_map.allow_click_offset({"click_offset": [60, 0]})
        game_map.allow_click_offset({"picture\\x.png": 1.5})
        assert game_map.click_offset == (0, 0)


class TestSkipChecks:
    def test_forbidden_map_is_skipped(self, game_map, set_config):
        set_config(game_map.cfg, forbid_map=["1"])
        assert game_map.check_forbidden_maps("1-1 空间站「黑塔」") is True

    def test_allowed_map_is_not_skipped(self, game_map, set_config):
        set_config(game_map.cfg, forbid_map=["2"])
        assert game_map.check_forbidden_maps("1-1 空间站「黑塔」") is False

    def test_non_string_entries_are_rejected(self, game_map, set_config, log_records):
        set_config(game_map.cfg, forbid_map=[1, 2])
        assert game_map.check_forbidden_maps("1-1 空间站") is False
        assert any("应只包含字符串" in r["message"] for r in log_records)

    def test_allowlist_mode_skips_maps_outside_the_list(self, game_map, set_config):
        set_config(game_map.cfg, allowlist_mode=True, allowlist_map=["2"])
        assert game_map.check_allowlist_maps("1-1 空间站") is True

    def test_allowlist_mode_keeps_listed_maps(self, game_map, set_config):
        set_config(game_map.cfg, allowlist_mode=True, allowlist_map=["1"])
        assert game_map.check_allowlist_maps("1-1 空间站") is False

    def test_allowlist_mode_off_keeps_everything(self, game_map, set_config):
        set_config(game_map.cfg, allowlist_mode=False)
        assert game_map.check_allowlist_maps("1-1 空间站") is False

    def test_allowlist_once_consumes_the_flag(self, game_map, set_config, isolated_cwd):
        import json

        set_config(game_map.cfg, allowlist_mode_once=True, allowlist_map=["1"])

        game_map.check_allowlist_maps("1-1 空间站")

        assert game_map.allowlist_mode is True
        saved = json.loads((isolated_cwd / "config.json").read_text(encoding="utf-8"))
        assert saved["allowlist_mode_once"] is False, "一次性白名单开关应立即落盘关闭"


class TestCheckPlanet:
    def test_same_planet_is_skipped(self, game_map):
        game_map.planet = "1"
        assert game_map.check_planet("1") is True

    def test_different_planet_is_not_skipped(self, game_map):
        game_map.planet = "1"
        assert game_map.check_planet("2") is False


class TestResetRoundCount:
    def test_zeroes_per_round_handle_counters(self, game_map):
        reset_calls = []
        game_map.handle = SimpleNamespace(
            movement=SimpleNamespace(tatol_save_time=99),
            combat=SimpleNamespace(reset=lambda: reset_calls.append(1)),
        )

        game_map.reset_round_count()

        assert reset_calls == [1], "战斗计数由 combat 自己重置"
        assert game_map.handle.movement.tatol_save_time == 0


class TestDragSequences:
    @pytest.fixture
    def dragging(self, game_map):
        drags = []
        game_map.mouse_event = SimpleNamespace(
            mouse_drag=lambda *args, **kwargs: drags.append(args)
        )
        return game_map, drags

    def test_offset_drags_in_left_up_right_down_order(self, dragging):
        game_map, drags = dragging
        directions = MAP_MOVE_NAV_DATA["16:9"]["directions"]

        game_map._move_with_offset((1, 2, 3, 4))

        assert drags == [
            directions["left"],
            directions["up"],
            directions["up"],
            directions["right"],
            directions["right"],
            directions["right"],
            directions["down"],
            directions["down"],
            directions["down"],
            directions["down"],
        ]

    def test_exact_drags_in_up_left_right_down_order(self, dragging):
        game_map, drags = dragging
        directions = MAP_MOVE_NAV_DATA["16:9"]["directions"]

        game_map._move_with_exact((2, 1, 3))

        assert drags == [
            directions["up_left"],
            directions["up_left"],
            directions["right"],
            directions["down"],
            directions["down"],
            directions["down"],
        ]

    def test_zero_offset_drags_nothing(self, dragging):
        game_map, drags = dragging
        game_map._move_with_offset((0, 0, 0, 0))
        assert drags == []


class TestFindTransferPoint:
    def test_returns_as_soon_as_target_is_found(self, game_map, monkeypatch):
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        game_map.img = SimpleNamespace(have_screenshot=lambda *a, **k: True)
        moved = []
        game_map._move_default = lambda target, threshold: moved.append(threshold)

        game_map.find_transfer_point("key.png")

        assert moved == [], "找到目标后不应再拖动地图"

    def test_lowers_threshold_each_round_until_timeout(self, game_map, monkeypatch):
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        thresholds = []
        game_map.img = SimpleNamespace(
            have_screenshot=lambda targets, offset, threshold: (
                thresholds.append(threshold) or False
            )
        )
        clock = SimpleNamespace(now=0.0)

        def fake_time():
            clock.now += 10.0
            return clock.now

        monkeypatch.setattr(map_module.time, "time", fake_time)
        game_map._move_default = lambda target, threshold: None

        game_map.find_transfer_point(
            "key.png", threshold=0.99, min_threshold=0.93, timeout=60
        )

        assert thresholds == pytest.approx([0.99, 0.98, 0.97, 0.96, 0.95])
        assert thresholds[-1] >= 0.93

    def test_threshold_never_drops_below_minimum(self, game_map, monkeypatch):
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        thresholds = []
        game_map.img = SimpleNamespace(
            have_screenshot=lambda targets, offset, threshold: (
                thresholds.append(threshold) or False
            )
        )
        clock = SimpleNamespace(now=0.0)

        def fake_time():
            clock.now += 10.0
            return clock.now

        monkeypatch.setattr(map_module.time, "time", fake_time)
        game_map._move_default = lambda target, threshold: None

        game_map.find_transfer_point(
            "key.png", threshold=0.95, min_threshold=0.94, timeout=100
        )

        assert set(thresholds) <= {0.95, 0.94}


class TestPauseGate:
    """拖地图找点位那类循环里的暂停闸门。

    闸门是 `Map.pause_gate`，由 MapOperations 在跑图前接到 `Pause.wait_if_paused`。
    两个要点：**能停**，以及**暂停的秒数必须从墙钟死线里扣掉**。
    """

    @staticmethod
    def _transfer_point_rounds(game_map, monkeypatch, gate):
        """跑一次 find_transfer_point，返回循环轮数（每轮会调一次 _move_default）。"""
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        game_map.img = SimpleNamespace(have_screenshot=lambda *a, **k: False)
        rounds = []
        game_map._move_default = lambda target, threshold: rounds.append(threshold)
        game_map.pause_gate = gate

        clock = SimpleNamespace(now=0.0)

        def fake_time():
            clock.now += 10.0  # 每读一次时间就前进 10 秒
            return clock.now

        monkeypatch.setattr(map_module.time, "time", fake_time)
        game_map.find_transfer_point("key.png", timeout=60)
        return len(rounds)

    def test_deadline_is_extended_by_the_paused_seconds(self, game_map, monkeypatch):
        """闸门报的暂停秒数要加回 start_time。

        不补偿的症状：一暂停，恢复后立刻超时、报「传送点查找失败」，地图开始漏点 ——
        而且只在暂停过的路径上出现，人工测极难归因到暂停功能。
        """
        without_pause = self._transfer_point_rounds(game_map, monkeypatch, lambda: 0.0)
        with_pause = self._transfer_point_rounds(game_map, monkeypatch, lambda: 8.0)

        assert without_pause == 5, "每轮净消耗 10 秒，60 秒预算正好 5 轮"
        assert with_pause > without_pause * 3, (
            f"扣掉暂停的 8 秒后每轮净消耗 2 秒，轮数应远多于 {without_pause} 轮，"
            f"实际 {with_pause} 轮"
        )

    def test_gate_runs_once_per_drag_attempt(self, game_map, monkeypatch):
        """闸门要插在最内层（每次拖拽之前），而不是只在外层 while。

        只放外层 while 的话，按一次键要等完两个方向 × 3 次拖拽（十几秒）；
        断言闸门次数与拖拽次数相等，等于把「最内层」钉住。
        """
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        monkeypatch.setattr(map_module.Img, "invert", staticmethod(lambda image: "INV"))
        game_map.img = SimpleNamespace(have_screenshot=lambda *a, **k: False)
        drags = []
        game_map.mouse_event = SimpleNamespace(
            mouse_drag=lambda *a, **k: drags.append(a)
        )
        gates = []
        game_map.pause_gate = lambda: (gates.append(1), 0.0)[1]

        clock = SimpleNamespace(now=0.0)

        def fake_time():
            clock.now += 35.0  # 只够跑完一圈外层（2 个方向 × 3 次拖拽）
            return clock.now

        monkeypatch.setattr(map_module.time, "time", fake_time)
        game_map.find_scene("key.png", timeout=60)

        assert len(drags) == 6, "一圈外层 = 2 个方向 × 3 次拖拽"
        assert len(gates) == 7, (
            "构成为「外层 while 的补偿闸门 1 次 + 最内层每次拖拽前 1 次」；"
            "若闸门只插在外层 while，这里只会是 1 次"
        )


class TestHandlePlanetClickOffset:
    """修饰键 → handle_planet → click_target 的完整链路。

    场景：星球节点的**静态部分**可识别，但可点热区在它右边 60 像素
    （动态的那块才是热区）。
    """

    @staticmethod
    def _prepare(game_map, monkeypatch, interface_answers=()):
        monkeypatch.setattr(map_module.Img, "get_img", staticmethod(lambda path: "IMG"))
        game_map.allow_click_offset(
            {"picture\\orientation_7.png": 1.5, "click_offset": [60, 0]}
        )
        game_map.check_planet = lambda key: False
        game_map.find_transfer_point = lambda *a, **k: None
        game_map.blackscreen = SimpleNamespace(check_blackscreen=lambda: False)
        # 这两个由 allow_map_drag 设置，start 循环里每条步骤都会先调它
        game_map.drag_offset = None
        game_map.drag_exact = None
        answers = iter(interface_answers)
        clicks = []

        def click_target(*args, **kwargs):
            clicks.append(kwargs)
            return True

        game_map.img = SimpleNamespace(
            click_target=click_target,
            on_interface=lambda **kwargs: next(answers, True),
        )
        return clicks

    def test_declared_offset_reaches_click_target(self, game_map, monkeypatch):
        clicks = self._prepare(game_map, monkeypatch)

        game_map.handle_planet("picture\\orientation_7.png")

        assert clicks[0]["click_offset"] == (60, 0)
        assert game_map.planet == "picture\\orientation_7.png"

    def test_retry_click_also_carries_the_offset(self, game_map, monkeypatch):
        """重试那一击同样要带偏移 —— 只改第一击的话，重试会落回锚点，白点 7 次
        （日志里那次连点 7 次全失败就是这个形状）。"""
        clicks = self._prepare(game_map, monkeypatch, interface_answers=[False])

        game_map.handle_planet("picture\\orientation_7.png")

        assert [call["click_offset"] for call in clicks] == [(60, 0), (60, 0)]
