"""移动与疾跑 —— 从 Handle 拆出来的第三簇。

`handle_move` 是 handle 里最长的方法（117 行）：按住方向键 value 秒，期间处理
疾跑开关、强制断开、系统卡顿识别。疾跑状态由一条后台线程轮询 `switch_run.png`
的匹配度维持。

与战斗的交叉只有一个：黄泉模式下上一步是 `e` 时，要先确认有没有意外进战斗。
所以注入 `combat` 而不是反向持有 Handle。

:param combat: 战斗簇（见 flows/combat.py），只用它的 technique_points_dialog /
    fight_elapsed / fight_in_map 三样 —— 都是「这一步有没有打起来」。
"""

import asyncio
import threading
import time
from functools import partial

from utils.core.log import log
from utils.drivers.keyboard_event import KeyboardEvent
from utils.core.thresholds import SPRINT_ICON

# 疾跑比走路快这么多倍
SPRINT_SPEED_FACTOR = 1.53

#: 「同方向续走、不打断疾跑」的双键变体 → 实际按下的方向键。
#: JSON 里写 `{"aa": 0.8}`，键盘上仍然只按 `a`；区别在 handle_move 的疾跑分支。
DOUBLE_MOVES = {"ww": "w", "aa": "a", "ss": "s", "dd": "d"}


def sprint_duration(walk_seconds: float) -> float:
    """把「走路走完要多久」换算成「开疾跑走完要多久」。

    疾跑快 `SPRINT_SPEED_FACTOR` 倍，但起步那 1 秒省不掉 —— 先扣 1 秒、除以倍数、
    再加回来。省下的时间 = walk_seconds - 返回值。
    """
    return round((walk_seconds - 1) / SPRINT_SPEED_FACTOR, 4) + 1


def should_toggle_sprint(need_run: bool, is_running: bool) -> bool:
    """当前状态与目标状态不一致时才需要去动 Shift。"""
    return need_run != is_running


class Movement:
    """移动、疾跑检测与卡顿识别。"""

    def __init__(self, cfg, img, mouse_event, combat):
        self.cfg = cfg
        self.img = img
        self.mouse_event = mouse_event
        self.combat = combat

        self.run_fix_time = 0  # 强制断开疾跑时间
        self.run_fixed = False  # 强制断开疾跑标志
        self.last_step_run = False  # 上一次是否是疾跑
        self.tatol_save_time = 0  # 疾跑节约时间
        self.time_error_cnt = 0  # 系统卡顿计数
        self.running = False
        self.held_key = None  # 跨步骤保持按住的方向键（双键续走）
        self.thread_cancel_sprint = None
        self.thread_check_sprint = None


    def handle_move(
        self,
        value,
        key,
        normal_run=False,
        last_key: str = "",
        prev_key: str = "",
        next_key: str = "",
    ):
        """
        移动，并处理疾跑
        使用 try/finally 保证方向键与 Shift 一定会被释放，避免异常时键盘卡住

        :param prev_key: 上一条 map 步骤的原始键（`aa` 也原样传进来），用于判断
            「同方向续走」是否要保住疾跑；和只给 HuangQuan 用的 `last_key` 分开。
        :param next_key: 下一条 map 步骤的原始键。如果它是同方向的双键
            （`ss` 跟在 `s` 后面），这一段结束后**不释放**方向键和 Shift，
            让下一段在同一口气里继续跑，避免「松开再按」造成疾跑中断。
        """
        if normal_run:
            log.info(f"强制关闭疾跑normal_run:{normal_run}")
        if last_key == "e":
            self.combat.technique_points_dialog()
            if not self.img.on_main_interface(timeout=0.2):
                fight_status = self.combat.fight_elapsed()
                if not fight_status:
                    log.info("未进入战斗")
                else:
                    log.info("进入战斗")
                    self.combat.fight_in_map = True

        self.run_fix_time = 0
        base_key = DOUBLE_MOVES.get(key, key)
        allow_run = self.cfg.config_file.get("auto_run_in_map", False)
        # 上一步是不是同一方向的「按住不放」：是的话这段不重新按键
        continuing = getattr(self, "held_key", None) == base_key
        # 下一段是不是同方向双键：是的话这段结束后保持按住
        hold_next = bool(
            next_key in DOUBLE_MOVES
            and DOUBLE_MOVES[next_key] == base_key
            and allow_run
            and not normal_run
        )
        if not continuing:
            KeyboardEvent.press_key(base_key)

        completed = False
        try:
            log.info(f"上一次疾跑状态: {self.last_step_run}")
            # 疾跑相关逻辑回退2025.2.28版本
            # # 固定ctrl两次取消疾跑
            # if self.last_step_run:
            #     self.start_cancel_sprint_task()
            #     self.stop_cancel_sprint_task()

            start_time = time.perf_counter()
            # 双键 + 上一步同方向 + 上一步确实在疾跑 → 这一段不要断疾跑。
            # 只按方向键走完 value 秒；move_run_fix 会检测疾跑图标并按 Shift
            # 把它关掉，所以这条路必须绕开它和两个短步分支。
            keep_sprint = (
                key in DOUBLE_MOVES
                and allow_run
                and not normal_run
                and self.last_step_run
                and prev_key in (base_key, key)
            )
            if keep_sprint:
                self.enable_run()  # 确认疾跑仍在（掉了就重新按一次 Shift）
            add_time = True
            run_in_road = False
            walk_in_road = False
            is_normal_run = False  # 普通跑步状态
            temp_time = 0
            self.run_fixed = False  # 强制断开初始化为否

            value_before = value
            while time.perf_counter() - start_time < value:
                if keep_sprint:
                    # 已在疾跑，保持方向键按住即可；sleep 防止忙等（R2）。
                    # 用 0.02 而不是 0.05：轮询粒度会叠在 value 上，0.05 会让
                    # 0.1 秒级的短双键步骤多跑半格（标定 ss 时长时尤其明显）。
                    time.sleep(0.02)
                    continue
                if (
                    value_before > 2
                    and not run_in_road
                    and allow_run
                    and not normal_run
                ):
                    self.move_run_fix(start_time)
                    if time.perf_counter() - start_time > 1:
                        self.enable_run()
                        self.start_check_sprint_task(need_run=True)
                        run_in_road = True
                        temp_value = value_before
                        value = sprint_duration(value_before)
                        self.tatol_save_time += temp_value - value
                        self.last_step_run = True
                elif (
                    value_before <= 1 and allow_run and add_time and self.last_step_run
                ):
                    value = value_before + 0.07
                    self.move_run_fix(start_time)
                    add_time = False
                    self.last_step_run = False
                elif value_before <= 2 and not walk_in_road:
                    self.move_run_fix(start_time)
                    walk_in_road = True
                    self.last_step_run = False
                else:
                    # 三个分支都不命中（normal_run 走长距离、短步剩下的等待时间等）：
                    # 必须 sleep，否则就是 100% CPU 忙等（R2），既耗电又会跟后台
                    # 截图线程抢 GIL，反过来制造出代码自己检测的「系统卡顿」。
                    time.sleep(0.005)
            temp_time = time.perf_counter() - start_time

            # 系统卡顿识别
            time_error_check = True
            if time_error_check and value >= 0.2:
                extra_time = temp_time - value
                if extra_time > 0.05:
                    log.info(
                        f"警告，此处出现系统卡顿，实际多移动{extra_time:.4f}秒，可能造成路线错误"
                    )
                    self.time_error_cnt += 1

            # 暂不启用
            extra_fix = False
            if extra_fix:
                extra_time = temp_time - value
                extra_time = (
                    extra_time
                    if not run_in_road
                    else round(extra_time * SPRINT_SPEED_FACTOR, 4)
                )
                if extra_time > 0.05:
                    log.info("强制断开疾跑")
                    fix_start_time = time.perf_counter()
                    key_dict = {"w": "s", "s": "w", "a": "d", "d": "a"}
                    if key in key_dict:
                        KeyboardEvent.press_key(key_dict.get(key))
                        while time.perf_counter() - fix_start_time < extra_time:
                            pass
                        KeyboardEvent.release_key(key_dict.get(key))
                        KeyboardEvent.press_key(key)
                        KeyboardEvent.release_key(key)
            completed = True
        finally:
            # 这一段后面还有同方向续走：保持方向键与 Shift 按住，交给下一段接着跑
            hold_keys = completed and hold_next
            try:
                self.stop_check_sprint_task()
            except Exception:
                pass
            if hold_keys:
                self.held_key = base_key
            else:
                self.held_key = None
                try:
                    KeyboardEvent.release_key("shift")
                except Exception:
                    pass
                try:
                    KeyboardEvent.release_key(base_key)
                except Exception:
                    pass
        if allow_run and not (completed and hold_next):
            time.sleep(0.03)

    def release_held(self):
        """释放跨步骤保持按住的键（序列结束 / 异常退出时兜底）。"""
        key = getattr(self, "held_key", None)
        if not key:
            return
        try:
            KeyboardEvent.release_key("shift")
        except Exception:
            pass
        try:
            KeyboardEvent.release_key(key)
        except Exception:
            pass
        self.held_key = None

    def is_running(self):
        """
        判断是否在疾跑状态
        """
        result = self.img.scan_screenshot(self.img.switch_run, (1720, 930, 0, 0))
        return result["max_val"] > SPRINT_ICON

    async def async_check_sprint_status(self, need_run=True, delay=0.12):
        """异步检测疾跑状态
        :param need_run: True=需要开启疾跑, False=需要关闭疾跑
        """
        loop = asyncio.get_event_loop()
        action = "开启" if need_run else "关闭"

        for count in range(2):
            if not self.running:
                break

            await asyncio.sleep(delay)
            is_running = await loop.run_in_executor(None, self.is_running)

            should_act = should_toggle_sprint(need_run, is_running)
            if not should_act:
                log.info(f"当前已{action}疾跑")
                break

            await loop.run_in_executor(
                None, KeyboardEvent.press_key, "shift"
            )
            if not need_run:
                await asyncio.sleep(0.03)
                await loop.run_in_executor(
                    None, KeyboardEvent.release_key, "shift"
                )
            log.info(f"{action}疾跑" + (f"，第{count + 1}次尝试" if count else ""))

        self.running = False

    def start_check_sprint_task(self, need_run=True, delay=0.12):
        """启动检测疾跑任务"""
        if self.thread_check_sprint and self.thread_check_sprint.is_alive():
            log.warning("检测疾跑任务已在运行，跳过启动")
            return
        self.running = True
        self.thread_check_sprint = threading.Thread(
            target=partial(
                self._run_async_check_sprint, need_run=need_run, delay=delay
            ),
            daemon=True,
        )
        self.thread_check_sprint.start()

    def stop_check_sprint_task(self):
        """停止检测疾跑任务"""
        self.running = False
        if self.thread_check_sprint and self.thread_check_sprint.is_alive():
            self.thread_check_sprint.join()
            self.thread_check_sprint = None
        log.info("检测任务已停止")

    def _run_async_check_sprint(self, need_run=True, delay=0.12):
        """运行异步任务，处理检测疾跑的逻辑"""
        asyncio.run(self.async_check_sprint_status(need_run=need_run, delay=delay))

    def enable_run(self):
        """强制开启疾跑"""
        log.info("调用enable_run")
        if not self.is_running():
            KeyboardEvent.press_key("shift")
            log.info("开启疾跑")

    def move_run_fix(self, start_time, time_limit=0.3):
        """
        用于修复2.6更新后连续移动时，疾跑意外打开的情况。

        该方法用于检测当前疾跑状态，并在检测到疾跑意外激活时，模拟按下和释放 Shift 键来强制关闭疾跑。
        为了避免多次触发关闭操作，确保每次循环内只执行一次关闭操作。

        参数:
        - start_time: 循环开始时间。
        - time_limit: 限制检测逻辑的时间窗口，默认为 0.3 秒。
        """
        # 测试
        # return
        # 回退至2025.2.28版本
        if not self.run_fixed:
            current_time = time.perf_counter()
            elapsed_time = current_time - start_time

            # 仅在前 0.3 秒内执行检测逻辑
            if elapsed_time <= time_limit:
                # 检查 run_fix_time 是否为 None 或时间差大于 0.1 秒
                if not self.run_fix_time or (current_time - self.run_fix_time) > 0.1:
                    # for _ in range(4):  # 强制断开检查最多4次，避免误判
                    result_run = self.img.scan_screenshot(
                        self.img.switch_run, (1720, 930, 0, 0)
                    )
                    # log.info(f"疾跑匹配度: {result_run['max_val']}")  # Testlog 用于测试图片匹配度
                    # 如果匹配度超过 0.996，强制断开疾跑
                    if result_run["max_val"] > SPRINT_ICON:
                        log.info(f"疾跑匹配度: {result_run['max_val']}")
                        log.info("强制断开疾跑")
                        KeyboardEvent.press_key("shift")
                        time.sleep(0.05)
                        KeyboardEvent.release_key("shift")
                        self.run_fix_time = current_time  # 更新修复时间
                        self.run_fixed = True
            else:
                self.run_fixed = True
