"""utils/flows/movement.py —— 移动循环、疾跑时长换算、疾跑检测线程。

疾跑那部分原本散在 tests/test_handle.py 里（代码是从 handle.py 拆出来的，测试没跟着走）。
这里按仓库约定收成 test_movement.py。

取像素的部分（`scan_screenshot`）一律给替身；`handle_move` 的分支选择另用假时钟驱动。
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

import utils.flows.movement as movement_module
from utils.flows.movement import (
    Movement,
    should_toggle_sprint,
    sprint_duration,
)


class ScriptedClock:
    """按脚本前进的假时钟。

    脚本读完之后停在最后一个刻度上（循环收尾还会再读一两次）。若因此导致循环退不出去，
    说明刻度写错了 —— 宁可抛异常，也不要让整个测试挂死。
    """

    def __init__(self, ticks, allowance=2):
        self.ticks = list(ticks)
        self.cur = 0.0
        self.slept = []
        self.allowance = allowance

    def perf_counter(self):
        if self.ticks:
            self.cur = self.ticks.pop(0)
        else:
            self.allowance -= 1
            if self.allowance < 0:
                raise AssertionError("假时钟的刻度用尽了，循环还没退出 —— 脚本写错了")
        return self.cur

    def sleep(self, seconds):
        self.slept.append(seconds)


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
            on_main_interface=lambda **k: False,
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


@pytest.fixture
def running_movement(movement, monkeypatch):
    """开了疾跑、且把会起线程/碰真实时间的调用换成记录器的 Movement。"""
    movement.cfg.config_file = {"auto_run_in_map": True}
    calls = SimpleNamespace(fix=[], sprint=[], enable=[])
    monkeypatch.setattr(
        movement, "move_run_fix", lambda start_time, time_limit=0.3: calls.fix.append(1)
    )
    monkeypatch.setattr(movement, "enable_run", lambda: calls.enable.append(1))
    monkeypatch.setattr(
        movement,
        "start_check_sprint_task",
        lambda need_run=True, delay=0.12: calls.sprint.append(need_run),
    )
    return movement, calls


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


class TestSprintDuration:
    def test_shortens_by_the_sprint_factor_but_keeps_the_startup_second(self):
        # 3 秒的走路：起步 1 秒省不掉，剩下 2 秒按 1.53 倍压缩
        assert sprint_duration(3.0) == pytest.approx(round(2 / 1.53, 4) + 1)

    def test_saving_is_the_difference(self):
        assert 3.0 - sprint_duration(3.0) == pytest.approx(0.6928, abs=1e-4)

    def test_a_one_second_move_gains_nothing(self):
        assert sprint_duration(1.0) == 1.0


class TestShouldToggleSprint:
    @pytest.mark.parametrize(
        "need_run,is_running,expected",
        [
            (True, False, True),  # 想跑，没跑 → 要按
            (True, True, False),  # 想跑，已在跑 → 不用动
            (False, True, True),  # 想停，在跑 → 要按
            (False, False, False),  # 想停，已停 → 不用动
        ],
    )
    def test_only_fires_on_a_mismatch(self, need_run, is_running, expected):
        assert should_toggle_sprint(need_run, is_running) is expected


# ---------------------------------------------------------------------------
# 取像素那半
# ---------------------------------------------------------------------------


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


class TestMoveRunFix:
    """`move_run_fix` 的守卫条件。匹配度那一下走替身。"""

    def _freeze_clock(self, monkeypatch, now):
        slept = []
        monkeypatch.setattr(
            movement_module,
            "time",
            SimpleNamespace(perf_counter=lambda: now, sleep=slept.append),
        )
        return slept

    def test_forces_sprint_off_when_the_icon_is_still_there(self, movement, monkeypatch):
        slept = self._freeze_clock(monkeypatch, now=1.0)
        movement.img.scan_screenshot = lambda *a, **k: {"max_val": 0.999}

        movement.move_run_fix(start_time=0.9)

        assert "shift" in movement.keyboard.pressed
        assert "shift" in movement.keyboard.released
        assert slept == [0.05]
        assert movement.run_fixed is True
        assert movement.run_fix_time == 1.0

    def test_does_nothing_when_the_icon_is_gone(self, movement, monkeypatch):
        self._freeze_clock(monkeypatch, now=1.0)
        movement.img.scan_screenshot = lambda *a, **k: {"max_val": 0.5}

        movement.move_run_fix(start_time=0.9)

        assert movement.keyboard.pressed == []
        assert movement.run_fixed is False

    def test_gives_up_after_the_time_window(self, movement, monkeypatch):
        self._freeze_clock(monkeypatch, now=5.0)
        movement.img.scan_screenshot = lambda *a, **k: {"max_val": 0.999}

        movement.move_run_fix(start_time=1.0)  # 已过 4 秒，超出 0.3 秒窗口

        assert movement.keyboard.pressed == []
        assert movement.run_fixed is True, "超出窗口也要标记，免得每轮都去截图"

    def test_debounces_repeated_fixes(self, movement, monkeypatch):
        self._freeze_clock(monkeypatch, now=1.0)
        movement.img.scan_screenshot = lambda *a, **k: {"max_val": 0.999}
        movement.run_fix_time = 0.95  # 距 now 只有 0.05 秒，不足 0.1

        movement.move_run_fix(start_time=0.9)

        assert movement.keyboard.pressed == []

    def test_skips_when_already_fixed_this_round(self, movement, monkeypatch):
        self._freeze_clock(monkeypatch, now=1.0)
        movement.run_fixed = True

        movement.move_run_fix(start_time=0.9)

        assert movement.keyboard.pressed == []


# ---------------------------------------------------------------------------
# 移动循环
# ---------------------------------------------------------------------------


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

    def test_cleanup_swallows_its_own_errors(self, movement):
        """收尾时释放按键出错，不该把异常抛给调用方 —— 那时方向上已经跑完了。"""

        def boom(*args, **kwargs):
            raise RuntimeError("释放失败")

        movement.stop_check_sprint_task = boom
        movement.keyboard.release_key = boom

        movement.handle_move(0.1, "w")  # 不该抛

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


class TestHandleMoveBranches:
    """三个二分叉各自什么时候命中。用脚本时钟把循环驱动到确定的圈数。"""

    def test_long_move_turns_sprinting_on(self, running_movement, monkeypatch):
        movement, calls = running_movement
        # 0.0 起点 → 0.1 进循环 → 2.0 判定「已经跑了 1 秒以上」→ 2.31 退出
        monkeypatch.setattr(
            movement_module, "time", ScriptedClock([0.0, 0.1, 2.0, 2.31])
        )

        movement.handle_move(3.0, "w")

        assert calls.enable == [1], "开疾跑"
        assert calls.sprint == [True], "并启动疾跑状态检测线程"
        assert movement.last_step_run is True
        assert movement.tatol_save_time == pytest.approx(3.0 - sprint_duration(3.0))
        assert movement.time_error_cnt == 0, "实际耗时与换算值相符，不算卡顿"

    def test_slow_frame_beyond_the_estimate_is_counted(self, running_movement, monkeypatch):
        movement, _ = running_movement
        # 同样的剧本，但这轮实际拖到 5 秒
        monkeypatch.setattr(
            movement_module, "time", ScriptedClock([0.0, 0.1, 2.0, 5.0])
        )

        movement.handle_move(3.0, "w")

        assert movement.time_error_cnt == 1

    def test_short_move_extends_the_wait_when_already_running(
        self, running_movement, monkeypatch
    ):
        movement, calls = running_movement
        movement.last_step_run = True
        # 0.0 起点 → 0.1 进循环 → 1.08 退出。时长被加长到 1.07 之后，
        # 1.08 才大于它；否则 1.08 仍小于 1.07 会一直转。
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1, 1.08]))

        movement.handle_move(1.0, "w")

        assert calls.fix == [1]
        assert movement.last_step_run is False
        # 时长被加长到 1.07：实际 1.08 只多出 0.01，不该记成卡顿。
        # 若没有加长（仍是 1.0），1.08-1.0 会超过 0.05 的阈值而被记一次。
        assert movement.time_error_cnt == 0

    def test_short_move_without_sprint_just_walks(self, movement, monkeypatch):
        calls = []
        monkeypatch.setattr(
            movement, "move_run_fix", lambda *a, **k: calls.append(1)
        )
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1, 2.5]))

        movement.handle_move(2.0, "w")

        assert len(calls) == 1
        assert movement.last_step_run is False

    def test_double_move_keeps_sprint_when_previous_is_same_direction(
        self, running_movement, monkeypatch
    ):
        movement, calls = running_movement
        movement.last_step_run = True
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1, 0.9]))

        movement.handle_move(0.8, "aa", prev_key="a")

        assert calls.enable == [1], "先确认疾跑还开着"
        assert calls.fix == [], "保疾跑时不能调用 move_run_fix（它会按 Shift 关掉）"
        assert movement.last_step_run is True
        assert "a" in movement.keyboard.pressed, "双键只按基准方向 a"
        assert "aa" not in movement.keyboard.pressed, "不能把 aa 当按键名交给 pynput"

    def test_double_move_does_not_keep_sprint_across_another_direction(
        self, running_movement, monkeypatch
    ):
        movement, calls = running_movement
        movement.last_step_run = True
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1, 0.9]))

        movement.handle_move(0.8, "aa", prev_key="w")

        assert calls.fix == [1], "上一步不是 a，按普通短步处理"
        assert movement.last_step_run is False

    def test_double_move_without_previous_sprint_just_walks(
        self, running_movement, monkeypatch
    ):
        movement, calls = running_movement
        movement.last_step_run = False
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1, 0.9]))

        movement.handle_move(0.8, "aa", prev_key="a")

        assert calls.fix == [1]
        assert movement.last_step_run is False

    def test_normal_run_says_so(self, movement, monkeypatch, log_records):
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1]))

        movement.handle_move(0.05, "w", normal_run=True)

        assert any("强制关闭疾跑" in r["message"] for r in log_records)

    def test_checks_for_an_accidental_fight_after_e(self, movement, monkeypatch):
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1]))

        movement.handle_move(0.05, "w", last_key="e")

        assert movement.combat.fight_in_map is True

    def test_no_fight_after_e_leaves_the_flag_alone(self, movement, monkeypatch):
        movement.combat.fight_elapsed = lambda: False
        monkeypatch.setattr(movement_module, "time", ScriptedClock([0.0, 0.1]))

        movement.handle_move(0.05, "w", last_key="e")

        assert movement.combat.fight_in_map is False


# ---------------------------------------------------------------------------
# 疾跑检测线程
# ---------------------------------------------------------------------------


class TestSprintTaskLifecycle:
    def test_start_skips_when_thread_already_alive(self, make_instance, log_records):
        class Alive:
            def is_alive(self):
                return True

        instance = make_instance(Movement, thread_check_sprint=Alive(), running=False)

        instance.start_check_sprint_task()

        assert instance.running is False, "不应重复置位"
        assert any("已在运行" in r["message"] for r in log_records)

    def test_start_spawns_a_daemon_thread(self, movement, monkeypatch):
        started = []

        class Thread:
            def __init__(self, target=None, daemon=None):
                self.daemon = daemon

            def start(self):
                started.append(self.daemon)

        monkeypatch.setattr(movement_module.threading, "Thread", Thread)

        movement.start_check_sprint_task(need_run=True, delay=0)

        assert movement.running is True
        assert started == [True], "检测线程必须是 daemon，否则主程序退不掉"

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

    def test_async_runner_delegates_to_the_status_check(self, movement, monkeypatch):
        seen = []

        async def fake_status(need_run=True, delay=0.12):
            seen.append((need_run, delay))

        monkeypatch.setattr(movement, "async_check_sprint_status", fake_status)

        movement._run_async_check_sprint(need_run=False, delay=0)

        assert seen == [(False, 0)]


class TestAsyncCheckSprintStatus:
    def test_stops_when_already_in_the_desired_state(self, movement):
        movement.running = True
        movement.is_running = lambda: True

        asyncio.run(movement.async_check_sprint_status(need_run=True, delay=0))

        assert movement.keyboard.pressed == []
        assert movement.running is False, "跑完要把 running 归位"

    def test_retries_pressing_shift_until_the_state_matches(self, movement):
        movement.running = True
        movement.is_running = lambda: False

        asyncio.run(movement.async_check_sprint_status(need_run=True, delay=0))

        assert movement.keyboard.pressed == ["shift", "shift"], "最多试两次"

    def test_turning_sprint_off_presses_and_releases(self, movement):
        movement.running = True
        states = iter([True, False])  # 松开之后再测，已经是「没在跑」了
        movement.is_running = lambda: next(states, False)

        asyncio.run(movement.async_check_sprint_status(need_run=False, delay=0))

        assert movement.keyboard.pressed == ["shift"]
        assert movement.keyboard.released == ["shift"], "关疾跑要按一下再松开"
        assert movement.keyboard.pressed == ["shift"], "状态对上之后不该再试第二次"

    def test_gives_up_after_two_attempts(self, movement):
        movement.running = True
        movement.is_running = lambda: True  # 怎么按都没变

        asyncio.run(movement.async_check_sprint_status(need_run=False, delay=0))

        assert movement.keyboard.pressed == ["shift", "shift"], "上限就是两次"

    def test_exits_immediately_when_not_running(self, movement):
        movement.running = False

        asyncio.run(movement.async_check_sprint_status(need_run=True, delay=0))

        assert movement.keyboard.pressed == []
