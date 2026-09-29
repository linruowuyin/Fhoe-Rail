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
        self.thread_cancel_sprint = None
        self.thread_check_sprint = None


    def handle_move(self, value, key, normal_run=False, last_key: str = ""):
        """
        移动，并处理疾跑
        使用 try/finally 保证方向键与 Shift 一定会被释放，避免异常时键盘卡住
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
        KeyboardEvent.press_key(key)

        try:
            log.info(f"上一次疾跑状态: {self.last_step_run}")
            # 疾跑相关逻辑回退2025.2.28版本
            # # 固定ctrl两次取消疾跑
            # if self.last_step_run:
            #     self.start_cancel_sprint_task()
            #     self.stop_cancel_sprint_task()

            start_time = time.perf_counter()
            allow_run = self.cfg.config_file.get("auto_run_in_map", False)
            add_time = True
            run_in_road = False
            walk_in_road = False
            is_normal_run = False  # 普通跑步状态
            temp_time = 0
            self.run_fixed = False  # 强制断开初始化为否

            value_before = value
            while time.perf_counter() - start_time < value:
                # if not is_normal_run and self.last_step_run:
                #     # self.start_check_sprint_task(need_run=False, delay=0.03)
                #     self.disable_run()
                #     is_normal_run = True
                # else:
                #     is_normal_run = True
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
                        value = round((value_before - 1) / 1.53, 4) + 1
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
                    extra_time if not run_in_road else round(extra_time * 1.53, 4)
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
        finally:
            # 无论移动过程是否异常，都必须释放疾跑键与方向键
            try:
                self.stop_check_sprint_task()
            except Exception:
                pass
            try:
                KeyboardEvent.release_key("shift")
            except Exception:
                pass
            try:
                KeyboardEvent.release_key(key)
            except Exception:
                pass
        if allow_run:
            time.sleep(0.03)

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

            should_act = (need_run and not is_running) or (not need_run and is_running)
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
