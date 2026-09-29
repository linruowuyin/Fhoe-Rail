"""utils/flows/handle.py —— 战斗判定、F 键分支、移动循环、疾跑线程。"""

import time
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest
import win32api
import win32con
from pynput.keyboard import Key as KeyboardKey

import utils.flows.combat as combat_module
import utils.flows.movement as movement_module
import utils.flows.orientation as orientation_module
import utils.vision.arrow as arrow_module
import utils.flows.handle as handle_module
from utils.core.exceptions import CustomException
from utils.flows.combat import Combat
from utils.flows.movement import Movement
from utils.flows.orientation import Orientation
from utils.flows.handle import Handle
from utils.vision.img import Img
from utils.vision.matcher import Matcher


class TickingTime:
    """每次读时间就前进 1 秒，让带超时的循环能确定性地退出。"""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        self.now += 1.0
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)

    def perf_counter(self):
        self.now += 1.0
        return self.now


class StubController:
    """pynput 键盘控制器的替身。"""

    def __init__(self, released=None, pressed=None):
        self.released = released if released is not None else []
        self.pressed = pressed if pressed is not None else []

    def press(self, key):
        self.pressed.append(key)

    def release(self, key):
        self.released.append(key)

    def tap(self, key):
        self.pressed.append(key)


@pytest.fixture
def handle(make_instance, monkeypatch):
    """一个不依赖游戏窗口的 Handle。"""
    keyboard = SimpleNamespace(pressed=[], released=[])
    keyboard.keyboard_press = lambda key, delay=0: keyboard.pressed.append(key)
    monkeypatch.setattr(handle_module, "KeyboardEvent", keyboard)
    instance = make_instance(
        Handle,
        cfg=SimpleNamespace(config_file={"auto_run_in_map": False}),
        img=SimpleNamespace(
            switch_run="switch_run.png",
            scan_screenshot=lambda *a, **k: {"max_val": 0.0},
        ),
        thread_check_sprint=None,
        running=False,
        run_fix_time=0,
        run_fixed=False,
        last_step_run=False,
        tatol_save_time=0,
        time_error_cnt=0,
        error_fight_cnt=0,
        error_fight_threshold=3,
    )
    instance.keyboard = keyboard
    return instance


@pytest.fixture
def movement(make_instance, monkeypatch):
    """一个不依赖游戏窗口的 Movement。"""
    keyboard = SimpleNamespace(pressed=[], released=[])
    keyboard.press_key = keyboard.pressed.append
    keyboard.release_key = keyboard.released.append
    keyboard.keyboard_press = lambda key, delay=0: keyboard.pressed.append(key)
    monkeypatch.setattr(movement_module, "KeyboardEvent", keyboard)
    instance = make_instance(
        Movement,
        cfg=SimpleNamespace(config_file={"auto_run_in_map": False}),
        img=SimpleNamespace(
            switch_run="switch_run.png",
            scan_screenshot=lambda *a, **k: {"max_val": 0.0},
        ),
        combat=SimpleNamespace(
            fight_in_map=False,
            technique_points_dialog=lambda: None,
            fight_elapsed=lambda: True,
        ),
        thread_check_sprint=None,
        running=False,
        run_fix_time=0,
        run_fixed=False,
        last_step_run=False,
        tatol_save_time=0,
        time_error_cnt=0,
    )
    instance.stop_check_sprint_task = lambda: None
    instance.keyboard = keyboard
    return instance


class TestAnalyzeFoundImages:
    """_analyze_found_images 是一张纯决策表，是 handle 里最值得覆盖的部分。"""

    @pytest.mark.parametrize(
        "found,expected",
        [
            ({}, (True, 15, False)),
            ({"target": 0.99}, (True, 15, True)),
            ({"target": 0.99, "dream_pop": 0.99}, (True, 3, True)),
            ({"target": 0.99, "teleport": 0.99}, (False, 0, True)),
            ({"target": 0.99, "space_anchor": 0.99}, (False, 0, False)),
            ({"target": 0.99, "dream_module": 0.99}, (True, 4, True)),
            ({"target": 0.99, "listen": 0.99}, (False, 0, False)),
            ({"target": 0.99, "dream_scape": 0.99}, (True, 5, True)),
            ({"target": 0.99, "go_to": 0.99}, (False, 0, True)),
            ({"dream_pop": 0.99}, (True, 15, False)),
        ],
    )
    def test_decision_table(self, handle, found, expected):
        assert handle._analyze_found_images(found, 15) == expected

    def test_keeps_default_delay_for_plain_target(self, handle):
        assert handle._analyze_found_images({"target": 0.99}, 8)[1] == 8

    def test_earlier_branch_wins(self, handle):
        """elif 顺序决定优先级：dream_pop 排在 teleport 之前。"""
        both = {"target": 0.99, "dream_pop": 0.99, "teleport": 0.99}
        assert handle._analyze_found_images(both, 15) == (True, 3, True)


class TestCheckFImg:
    @pytest.fixture
    def f_handle(self, make_instance, monkeypatch):
        monkeypatch.setattr(
            Img, "get_img", staticmethod(lambda path: np.zeros((4, 4, 3), np.uint8))
        )
        instance = make_instance(Handle)
        instance.img = SimpleNamespace(
            scan_screenshot=lambda *a, **k: {"max_val": 0.0},
            scan_temp_screenshot=lambda *a, **k: {"max_val": 0.0},
        )
        monkeypatch.setattr(handle_module, "time", TickingTime())
        return instance

    def test_nothing_found_forbids_pressing_f(self, f_handle):
        assert f_handle._check_f_img(15, timeout=2) == (True, 15, False)

    def test_target_found_allows_pressing_f(self, f_handle):
        f_handle.img = SimpleNamespace(
            scan_screenshot=lambda *a, **k: {"max_val": 0.99},
            scan_temp_screenshot=lambda *a, **k: {"max_val": 0.0},
        )
        use_absolute, delay, allow = f_handle._check_f_img(15, timeout=2)
        assert (use_absolute, delay, allow) == (True, 15, True)

    def test_stops_early_once_target_plus_two_seconds(self, f_handle):
        """找到 target 后最多再等 2 秒就停，不会耗满整个 timeout。"""
        scans = []

        def scan(*args, **kwargs):
            scans.append(1)
            return {"max_val": 0.99}

        f_handle.img = SimpleNamespace(
            scan_screenshot=scan, scan_temp_screenshot=scan
        )
        f_handle._check_f_img(15, timeout=30)
        assert len(scans) == 8, "一轮扫描 8 张图后即满足退出条件"


class TestHandleF:
    def test_skips_and_flags_error_when_not_allowed(self, make_instance):
        instance = make_instance(Handle)
        instance._check_f_img = lambda value, timeout=5: (True, 15, False)

        instance.handle_f(10, allow_skip=True)

        assert instance.f_key_error is True

    def test_continues_when_skip_disallowed(self, make_instance):
        instance = make_instance(Handle)
        instance._check_f_img = lambda value, timeout=5: (True, 15, False)

        instance.handle_f(10, allow_skip=False)

        assert instance.f_key_error is False

    def test_presses_f_with_absolute_delay(self, make_instance, monkeypatch):
        pressed = []
        monkeypatch.setattr(
            handle_module,
            "KeyboardEvent",
            SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)),
        )
        monkeypatch.setattr(handle_module, "time", TickingTime())
        instance = make_instance(Handle)
        instance._check_f_img = lambda value, timeout=5: (True, 3, True)

        instance.handle_f(10)

        assert pressed == ["f"]

    def test_waits_for_main_interface_when_delay_is_zero(
        self, make_instance, monkeypatch
    ):
        monkeypatch.setattr(
            handle_module,
            "KeyboardEvent",
            SimpleNamespace(keyboard_press=lambda key, delay=0: None),
        )
        monkeypatch.setattr(handle_module, "time", TickingTime())
        detected = []
        instance = make_instance(Handle)
        instance._check_f_img = lambda value, timeout=5: (False, 0, True)
        instance.img = SimpleNamespace(on_main_interface=lambda *a, **k: detected.append(1))

        instance.handle_f(10)

        assert detected == [1]

    def test_allow_skip_helper_passes_through(self, make_instance):
        instance = make_instance(Handle)
        seen = []
        instance.handle_f = lambda value, allow_skip=True: seen.append((value, allow_skip))

        instance.handle_allow_skip_f(7)

        assert seen == [(7, False)]


class TestHandleCheck:
    def test_none_means_skip(self, make_instance):
        assert make_instance(Handle).handle_check(None, "周一") is False

    def test_value_one_means_every_day(self, make_instance):
        assert make_instance(Handle).handle_check(1, "周一") is True

    def test_today_matches(self, make_instance):
        today = datetime.now().weekday()
        assert make_instance(Handle).handle_check([today], "今天") is True

    def test_other_day_does_not_match(self, make_instance):
        tomorrow = (datetime.now().weekday() + 1) % 7
        assert make_instance(Handle).handle_check([tomorrow], "明天") is False

    def test_empty_list_means_skip(self, make_instance):
        assert make_instance(Handle).handle_check([], "无") is False


class TestHandleEsc:
    def test_rejects_other_values(self, make_instance):
        with pytest.raises(CustomException):
            make_instance(Handle).handle_esc(2)

    def test_sends_key_down_and_key_up(self, make_instance, monkeypatch):
        flags = []
        monkeypatch.setattr(
            win32api, "keybd_event", lambda vk, scan, value, extra: flags.append(value)
        )
        monkeypatch.setattr(handle_module, "time", TickingTime())

        make_instance(Handle).handle_esc(1)

        assert flags == [0, win32con.KEYEVENTF_KEYUP]


class TestHandleAwait:
    def test_uses_absolute_value(self, make_instance, monkeypatch):
        fake = TickingTime()
        monkeypatch.setattr(handle_module, "time", fake)

        make_instance(Handle).handle_await(-1.5)

        assert fake.slept == [1.5]


class TestHandleR:
    def test_repeats_press_at_random_interval(self, make_instance, monkeypatch):
        pressed = []
        monkeypatch.setattr(
            handle_module,
            "KeyboardEvent",
            SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)),
        )
        fake = TickingTime()
        monkeypatch.setattr(handle_module, "time", fake)
        monkeypatch.setattr(handle_module.random, "uniform", lambda low, high: 0.5)

        make_instance(Handle).handle_r(1.0, "r")

        assert len(pressed) == 2
        assert fake.slept == [0.5, 0.5]

    def test_sleeps_remainder_when_not_divisible(self, make_instance, monkeypatch):
        monkeypatch.setattr(
            handle_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda *a, **k: None)
        )
        fake = TickingTime()
        monkeypatch.setattr(handle_module, "time", fake)
        monkeypatch.setattr(handle_module.random, "uniform", lambda low, high: 0.3)

        make_instance(Handle).handle_r(1.0, "r")

        # int(1.0/0.3) == 3 次按下，剩 0.1 秒补睡
        assert fake.slept == [0.3, 0.3, 0.3, pytest.approx(0.1)]


class TestHandleBAndScroll:
    def test_handle_b_presses_b(self, make_instance, monkeypatch):
        pressed = []
        monkeypatch.setattr(
            handle_module,
            "KeyboardEvent",
            SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)),
        )
        monkeypatch.setattr(handle_module, "time", TickingTime())

        make_instance(Handle).handle_b()

        assert pressed == ["b"]

    def test_scroll_delegates_to_the_mouse_driver(self, make_instance, monkeypatch):
        """滚轮属鼠标设备，经 MouseEvent 转给 drivers。"""
        scrolled = []
        monkeypatch.setattr(handle_module, "time", TickingTime())
        instance = make_instance(
            Handle, mouse_event=SimpleNamespace(scroll=lambda clicks: scrolled.append(clicks))
        )

        instance.scroll(-3)

        assert scrolled == [-3]


class TestHandleClickFloor:
    def test_maps_index_to_relative_percentage(self, make_instance):
        instance = make_instance(Handle)
        clicks = []
        instance.mouse_event = SimpleNamespace(
            relative_click=lambda points: clicks.append(points)
        )

        instance.handle_click_floor(0)
        instance.handle_click_floor(1)

        assert clicks[0] == (3.4, pytest.approx(970 / 1080 * 100))
        assert clicks[1] == (3.4, pytest.approx((970 - 86) / 1080 * 100))


class TestViewHelpers:
    def test_handle_view_set_stores_reference_arrow(self, make_instance, monkeypatch):
        monkeypatch.setattr(orientation_module.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(orientation_module.arrow, "take_arrow", lambda img: "ARROW")
        instance = make_instance(Orientation, img=None, arrow_begin=None)

        instance.handle_view_set(0.1)

        assert instance.arrow_begin == "ARROW"


class TestCalAng:
    def test_identical_arrow_is_zero_degrees(self, make_instance):
        """同一张图旋转 0 度时归一化相关为 1，应判定为 0 度。"""
        # cal_ang 用 Img 门面做旋转，所以这里给一个真的 Matcher
        img = make_instance(Matcher, screen=None, ui_images={}, _mouse=object())
        shape = np.zeros((25, 25, 3), dtype=np.uint8)
        shape[8:17, 11:14] = 255

        assert arrow_module.cal_ang(img, shape, shape) == 0


class TestIsRunning:
    def test_threshold_is_high(self, make_instance):
        instance = make_instance(Movement)
        instance.img = SimpleNamespace(
            switch_run="img", scan_screenshot=lambda *a, **k: {"max_val": 0.997}
        )
        assert instance.is_running() is True

        instance.img = SimpleNamespace(
            switch_run="img", scan_screenshot=lambda *a, **k: {"max_val": 0.99}
        )
        assert instance.is_running() is False


class TestSprintTaskLifecycle:
    def test_start_skips_when_thread_already_alive(self, make_instance, log_records):
        class Alive:
            def is_alive(self):
                return True

        instance = make_instance(Movement, thread_check_sprint=Alive(), running=False)

        instance.start_check_sprint_task()

        assert instance.running is False, "不应重复置位"
        assert any("已在运行" in r["message"] for r in log_records)

    def test_stop_joins_and_clears_thread(self, make_instance):
        joined = []

        class Thread:
            def is_alive(self):
                return True

            def join(self):
                joined.append(1)

        instance = make_instance(Movement, thread_check_sprint=Thread(), running=True)

        instance.stop_check_sprint_task()

        assert instance.running is False
        assert joined == [1]
        assert instance.thread_check_sprint is None

    def test_enable_run_presses_shift_only_when_needed(self, make_instance, monkeypatch):
        keyboard = SimpleNamespace(pressed=[])
        keyboard.press_key = keyboard.pressed.append
        monkeypatch.setattr(movement_module, "KeyboardEvent", keyboard)
        instance = make_instance(Movement)

        instance.is_running = lambda: True
        instance.enable_run()
        assert keyboard.pressed == [], "已经在疾跑时不应重复按 Shift"

        instance.is_running = lambda: False
        instance.enable_run()
        assert keyboard.pressed == ["shift"]


class TestHandleMove:
    def test_releases_direction_and_shift_keys_on_error(self, movement, monkeypatch):
        """移动循环里抛异常时，方向键与 Shift 必须被释放，否则键盘会卡住。"""

        def boom(*args, **kwargs):
            raise RuntimeError("循环中失败")

        monkeypatch.setattr(movement, "move_run_fix", boom)

        with pytest.raises(RuntimeError):
            movement.handle_move(0.5, "w")

        assert "w" in movement.keyboard.released
        assert "shift" in movement.keyboard.released

    def test_releases_keys_on_normal_completion(self, movement):
        movement.handle_move(0.1, "w")
        assert "w" in movement.keyboard.released
        assert "shift" in movement.keyboard.released

    def test_presses_the_requested_key(self, movement):
        movement.handle_move(0.1, "a")
        assert "a" in movement.keyboard.pressed

    @pytest.mark.xfail(
        strict=True,
        reason="计时循环体内没有任何 time.sleep：疾跑分支触发后（或关闭疾跑时），"
        "三个 elif 条件全部为假，剩余的等待时间变成 100% CPU 忙等",
    )
    def test_does_not_burn_cpu_while_waiting(self, movement):
        cpu_before = time.process_time()
        movement.handle_move(0.4, "w")
        cpu_used = time.process_time() - cpu_before
        assert cpu_used < 0.15


# ---------------------------------------------------------------------------
# 战斗簇 —— Handle 里最大的一块（约 300 行），也是拆分的第一刀
# ---------------------------------------------------------------------------


class CombatImg:
    """战斗路径用到的 img 替身，可按用例调整匹配值。"""

    def __init__(self, main_ui=0.5, doubt=0.0, on_main=True, on_interface=True):
        # 必须是 ndarray：fight_elapsed 会取 self.img.main_ui.shape
        self.main_ui = np.zeros((4, 4, 3), np.uint8)
        self.doubt_ui = np.zeros((4, 4, 3), np.uint8)
        self._main_ui_val = main_ui
        self._doubt_val = doubt
        self._on_main = on_main
        self._on_interface = on_interface
        self.scans = []

    def scan_screenshot(self, prepared, offset=(0, 0, 0, 0)):
        self.scans.append(prepared)
        return {"max_val": self._main_ui_val, "max_loc": (0, 0)}

    def scan_temp_screenshot(self, prepared):
        return {"max_val": self._doubt_val, "max_loc": (0, 0)}

    def on_main_interface(self, *args, **kwargs):
        return self._on_main

    def on_interface(self, *args, **kwargs):
        return self._on_interface

    def take_screenshot(self, *args, **kwargs):
        return ("frame", 0, 0, 10, 10)

    def img_center_point(self, result, shape):
        return (5, 6)

    def click_target(self, *args, **kwargs):
        return True


class CombatMouse:
    def __init__(self):
        self.centers = []
        self.clicks = []
        self.cursor_clicks = 0

    def click(self, points, *args, **kwargs):
        self.clicks.append(points)

    def click_at_cursor(self, *args, **kwargs):
        self.cursor_clicks += 1

    def click_center(self):
        self.centers.append(1)

    def mouse_drag(self, *args, **kwargs):
        pass


@pytest.fixture
def combat(make_instance, monkeypatch):
    """一个只关心战斗逻辑的 Combat，不碰窗口、不碰键鼠。"""
    monkeypatch.setattr(combat_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        combat_module, "KeyboardEvent", SimpleNamespace(keyboard_press=lambda *a, **k: None)
    )
    monkeypatch.setattr(
        combat_module.Img, "get_img", staticmethod(lambda path: np.zeros((4, 4, 3), np.uint8))
    )
    image = CombatImg()
    mouse = CombatMouse()
    instance = make_instance(
        Combat,
        cfg=SimpleNamespace(
            config_file={
                "auto_final_fight_e": False,
                "auto_final_fight_e_cnt": 0,
                "detect_fight_status_time": 0,
                "allow_fight_e_buy_prop": False,
            }
        ),
        img=image,
        mouse_event=mouse,
        current_fighting_index=0,
        fighting_count=0,
        auto_final_fight_e_cnt=0,
        attack_once=False,
        total_fight_cnt=0,
        total_no_fight_cnt=0,
        total_fight_time=0,
        fight_in_map=False,
        error_fight_cnt=0,
        error_fight_threshold=3,
        snack_used=0,
    )
    instance.image = image
    instance.mouse = mouse
    return instance


class TestHandleFighting:
    def test_rejects_unknown_value(self, combat):
        with pytest.raises(CustomException):
            combat.handle_fighting(3)

    def test_value_two_clicks_at_cursor(self, combat):
        combat.handle_fighting(2)
        assert combat.mouse.cursor_clicks == 1, "打障碍物 = 在当前位置点一下"

    def test_last_fight_switches_to_e_when_enabled(self, combat):
        combat.cfg = SimpleNamespace(
            config_file={"auto_final_fight_e": True, "auto_final_fight_e_cnt": 3}
        )
        combat.fighting_count = 1
        used = []
        combat.handle_e = lambda value: used.append("e")
        combat.fighting = lambda: used.append("fight")

        combat.handle_fighting(1)

        assert used == ["e"]
        assert combat.current_fighting_index == 1
        assert combat.auto_final_fight_e_cnt == 1

    def test_non_last_fight_uses_normal_attack(self, combat):
        combat.cfg = SimpleNamespace(
            config_file={"auto_final_fight_e": True, "auto_final_fight_e_cnt": 3}
        )
        combat.fighting_count = 2
        used = []
        combat.handle_e = lambda value: used.append("e")
        combat.fighting = lambda: used.append("fight")

        combat.handle_fighting(1)

        assert used == ["fight"]

    def test_e_budget_is_capped(self, combat):
        combat.cfg = SimpleNamespace(
            config_file={"auto_final_fight_e": True, "auto_final_fight_e_cnt": 1}
        )
        combat.fighting_count = 1
        combat.auto_final_fight_e_cnt = 1
        used = []
        combat.handle_e = lambda value: used.append("e")
        combat.fighting = lambda: used.append("fight")

        combat.handle_fighting(1)

        assert used == ["fight"]


class TestFightE:
    def test_value_one_enters_combat_check(self, combat):
        calls = []
        combat.technique_points_dialog = lambda: calls.append("dialog")
        combat.fight_elapsed = lambda: calls.append("elapsed") or True

        combat.fight_e(1)

        assert calls == ["dialog", "elapsed"]
        assert combat.mouse.centers == [1], "使用 E 后应点击屏幕中心"

    def test_value_two_skips_the_combat_check(self, combat):
        calls = []
        combat.technique_points_dialog = lambda: calls.append("dialog")
        combat.fight_elapsed = lambda: calls.append("elapsed") or True

        combat.fight_e(2)

        assert calls == ["dialog"], "value=2 是地图内补 E，不该进入战斗判定"


class TestTechniquePointsDialog:
    def test_noop_when_on_main_interface(self, combat):
        combat.image._on_main = True
        combat.technique_points_dialog()
        assert combat.image.scans == [], "在主界面时不该做任何识图"

    def test_noop_when_dialog_not_detected(self, combat):
        combat.image._on_main = False
        combat.image._main_ui_val = 0.10  # eat.png 匹配不上
        combat.technique_points_dialog()
        assert combat.mouse.clicks == []

    def test_cancels_when_buying_is_disabled(self, combat):
        combat.image._on_main = False
        combat.image._main_ui_val = 0.99  # 命中秘技点不足对话框
        combat.image.click_target = lambda *a, **k: combat.mouse.clicks.append(a[0])

        combat.technique_points_dialog()

        assert combat.mouse.clicks == ["./picture/cancel.png"]

    def test_taps_e_again_after_buying(self, combat, monkeypatch):
        combat.cfg = SimpleNamespace(config_file={"allow_fight_e_buy_prop": True})
        combat.image._on_main = False
        combat.image._main_ui_val = 0.99
        # 「无法购买」那一问要答 False，否则会走 pass 分支跳过购买
        combat.image.on_interface = (
            lambda *a, **k: k.get("interface_desc") != "无法购买"
        )
        combat.image.click_target = lambda *a, **k: True
        pressed = []
        monkeypatch.setattr(
            combat_module,
            "KeyboardEvent",
            SimpleNamespace(keyboard_press=lambda key, delay=0: pressed.append(key)),
        )

        combat.technique_points_dialog()
        # 购买流程里的最后一步是补 E
        assert pressed, "购买成功后应补按一次 E"


class TestFightDetection:
    def test_no_in_fight_status_true_when_round_icon_visible(self, combat):
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.99}
        assert combat.no_in_fight_status() is True

    def test_no_in_fight_status_false_when_round_icon_absent(self, combat):
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.5}
        assert combat.no_in_fight_status() is False

    def test_detect_returns_false_when_definitely_out_of_combat(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "no_in_fight_status", lambda: True)
        assert combat.detect_fight_status(timeout=1) is False

    def test_detect_returns_true_when_main_ui_disappears(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "no_in_fight_status", lambda: False)
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.1}
        assert combat.detect_fight_status(timeout=5) is True

    def test_detect_clicks_when_doubt_bubble_shows(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "no_in_fight_status", lambda: False)
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.95}
        combat.image.scan_temp_screenshot = lambda *a, **k: {"max_val": 0.99}
        acted = []
        combat.click_action = lambda is_warning: acted.append(is_warning) or True

        assert combat.detect_fight_status(timeout=5) is True
        assert acted == [False]

    def test_click_action_sleeps_then_attacks(self, combat):
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.1}

        assert combat.click_action(is_warning=False) is True
        assert combat.mouse.centers == [1]

    def test_click_action_uses_one_attack(self, combat):
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.1}

        combat.click_action(is_warning=False)
        combat.click_action(is_warning=False)

        assert combat.mouse.centers == [1], "attack_once 保证一轮判定里只点一次"

    def test_fight_error_cnt_counts_only_short_fights(self, combat):
        combat.fight_error_cnt(2)
        combat.fight_error_cnt(3)
        combat.fight_error_cnt(30)
        assert combat.error_fight_cnt == 1


class TestFightElapsed:
    def test_returns_false_when_no_enemy_detected(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "detect_fight_status", lambda timeout: False)
        assert combat.fight_elapsed() is False

    def test_counts_a_completed_fight(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "detect_fight_status", lambda timeout: True)
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.99}
        combat.image._on_main = True

        assert combat.fight_elapsed() is True
        assert combat.total_fight_cnt == 1
        assert combat.total_fight_time >= 0

    def test_short_fight_is_counted_as_error(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "detect_fight_status", lambda timeout: True)
        combat.image.scan_screenshot = lambda *a, **k: {"max_val": 0.99}
        combat.image._on_main = True
        combat.error_fight_threshold = 999  # 任何用时都算"异常短"

        combat.fight_elapsed()

        assert combat.error_fight_cnt == 1


class TestFighting:
    def test_not_entering_combat_increments_counter(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "fight_elapsed", lambda: False)

        combat.fighting()

        assert combat.mouse.centers == [1]
        assert combat.total_no_fight_cnt == 1

    def test_entering_combat_does_not_increment_no_fight(self, combat, monkeypatch):
        monkeypatch.setattr(combat, "fight_elapsed", lambda: True)

        combat.fighting()

        assert combat.total_no_fight_cnt == 0


class TestBackToMain:
    """`back_to_main` —— 它曾经崩在实机上：

        AttributeError: 'Handle' object has no attribute 'fight_elapsed'

    `fight_elapsed` 在「拆 Handle 第一簇（战斗）」时挪进了 `Combat`，这个调用点
    漏改了（同一次拆分里另一个调用点后来被修掉，只剩它一个）。触发条件是
    「ESC 打开的是战斗界面」那条分支，此前没有任何测试覆盖它，所以潜伏了很久。
    """

    @pytest.fixture
    def subject(self, make_instance, monkeypatch):
        fake = TickingTime()
        monkeypatch.setattr(handle_module, "time", fake)
        keyboard = SimpleNamespace(pressed=[])
        keyboard.keyboard_press = lambda key, delay=0: keyboard.pressed.append(key)
        monkeypatch.setattr(handle_module, "KeyboardEvent", keyboard)
        # 第一次不在主界面（走进循环），第二次在（退出循环）
        on_main = iter([False, True])
        img = SimpleNamespace(
            battle_esc_check="battle_esc_check.png",
            on_main_interface=lambda timeout=2: next(on_main, True),
            on_interface=lambda **kwargs: True,  # 命中「ESC 打开的是战斗界面」
        )
        fought = []
        instance = make_instance(
            Handle,
            img=img,
            combat=SimpleNamespace(fight_elapsed=lambda: fought.append(1)),
        )
        return instance, fought, keyboard, fake

    def test_battle_esc_branch_goes_through_combat(self, subject):
        instance, fought, keyboard, fake = subject

        instance.back_to_main()

        assert fought == [1], "命中战斗界面时必须走 combat.fight_elapsed()"
        assert keyboard.pressed == ["esc", "esc"]
        assert fake.slept == [2.0, 2]

    def test_already_on_main_interface_does_nothing(self, subject):
        """已经在主界面时不该按任何键 —— 免得把正常的界面踩乱。"""
        instance, fought, keyboard, fake = subject
        instance.img.on_main_interface = lambda timeout=2: True

        instance.back_to_main()

        assert keyboard.pressed == []
        assert fought == []
        assert fake.slept == []
