import os
import time


from utils.vision.blackscreen import BlackScreen
from utils.config.config import ConfigurationManager
from utils.flows.handle import Handle
from utils.drivers.keyboard_event import KeyboardEvent
from utils.vision import colors as color
from utils.vision.img import Img
from utils.core.log import log
from utils.core.thresholds import (
    DREAM_BUILD,
    MAIN_INTERFACE,
    MAP_LOADING,
    ROUND_DISABLE,
)
from utils.vision.mini_asu import ASU
from utils.flows.monthly_pass import MonthlyPass
from utils.drivers.mouse_event import MouseEvent
from utils.drivers.window import Window


class Calculated:
    def __init__(self):
        self.cfg = ConfigurationManager()
        self.window = Window()
        self.img = Img()
        self.monthly_pass = MonthlyPass()
        self.mouse_event = MouseEvent()
        self._config = None
        self._last_updated = None
        self.handle = Handle()
        self.asu = ASU()
        self.blackscreen = BlackScreen()

        self.hwnd = self.window.hwnd

    def run_mapload_check(self, error_count=0, max_error_count=10, threshold=MAIN_INTERFACE):
        """
        说明：
            计算地图加载时间
        """
        start_time = time.time()
        target = Img.get_img("./picture/map_load.png")
        time.sleep(1)  # 短暂延迟后开始判定是否为地图加载or黑屏跳转
        while error_count < max_error_count:
            result = self.img.scan_screenshot(target)
            if result and result["max_val"] > MAP_LOADING:
                log.info(f"检测到地图加载map_load，匹配度{result['max_val']}")
                if self.img.on_main_interface(
                    check_list=[
                        self.img.main_ui,
                        self.img.finish2_ui,
                        self.img.finish2_1_ui,
                        self.img.finish2_2_ui,
                        self.img.finish3_ui,
                    ],
                    timeout=10,
                    threshold=threshold,
                ):
                    break
            elif self.blackscreen.check_blackscreen():
                self.blackscreen.run_blackscreen_cal_time()
                break
            elif self.img.on_main_interface(
                check_list=[
                    self.img.main_ui,
                    self.img.finish2_ui,
                    self.img.finish2_1_ui,
                    self.img.finish2_2_ui,
                    self.img.finish3_ui,
                ],
                threshold=threshold,
            ):
                time.sleep(1)
                if self.img.on_main_interface(
                    check_list=[
                        self.img.main_ui,
                        self.img.finish2_ui,
                        self.img.finish2_1_ui,
                        self.img.finish2_2_ui,
                        self.img.finish3_ui,
                    ],
                    threshold=threshold,
                ):
                    log.info("连续检测到主界面，地图加载标记为结束")
                    break
            elif self.img.on_interface(
                check_list=[self.img.finish5_ui],
                timeout=3,
                interface_desc="模拟宇宙积分奖励界面",
            ):
                time.sleep(1)
                if self.img.on_interface(
                    check_list=[self.img.finish5_ui],
                    timeout=3,
                    interface_desc="模拟宇宙积分奖励界面",
                ):
                    log.info("连续检测到模拟宇宙积分奖励界面，地图加载标记为结束")
                    break
            else:
                error_count += 1
                time.sleep(1)
                log.info(
                    f"未查询到地图加载状态{error_count}次，加载图片匹配值{result['max_val']:.3f}"
                )
        else:
            log.info(f"加载地图超时，已重试{error_count}次，强制执行下一步")
        end_time = time.time()
        loading_time = end_time - start_time
        if error_count < max_error_count:
            log.info(f"地图载毕，用时 {loading_time:.1f} 秒")
        time.sleep(1)  # 增加1秒等待防止人物未加载错轴

    def run_dreambuild_check(self, error_count=0, max_error_count=10):
        """
        说明：
            筑梦模块移动模块加载时间
        """
        start_time = time.time()
        target = Img.get_img("./picture/finish_fighting.png")
        time.sleep(3)  # 短暂延迟后开始判定
        while error_count < max_error_count:
            result = self.img.scan_screenshot(target)
            if result["max_val"] > DREAM_BUILD:
                break
            else:
                error_count += 1
                time.sleep(1)
        end_time = time.time()
        loading_time = end_time - start_time
        if error_count >= max_error_count:
            log.info(
                f"移动模块加载超时，用时 {loading_time:.1f} 秒，识别图片匹配值{result['max_val']:.3f}"
            )
        else:
            log.info(f"移动模块成功，用时 {loading_time:.1f} 秒")
        time.sleep(0.5)  # 短暂延迟后开始下一步

    def handle_shutdown(self):
        if self.cfg.config_file.get("auto_shutdown", False):
            log.info("下班喽！I'm free!")
            os.system("shutdown /s /f /t 0")
        else:
            log.info("锄地结束！")

    def allow_buy_item(self):
        """
        购买物品检测
        """
        round_disable = Img.get_img("./picture/round_disable.png")
        if self.img.on_interface(
            check_list=[round_disable],
            timeout=5,
            interface_desc="无法购买",
            threshold=ROUND_DISABLE,
        ):
            return False
        else:
            return True

    def first_role_check(self):
        """
        按下'1'，确认队伍中的1号位属于跑图角色
        """
        log.info("开始判断1号位")
        image, *_ = self.img.take_screenshot(offset=(1670, 339, -160, -739))
        if color.any_pixel_in_ranges(image, color.FIRST_ROLE_RANGES):
            KeyboardEvent.keyboard_press("1")
            log.info("设置1号位为跑图角色")
