import os
import time
from datetime import datetime

import cv2
import numpy as np
import pyautogui
from pynput.keyboard import Controller as KeyboardController

from utils.blackscreen import BlackScreen
from utils.config.config import ConfigurationManager
from utils.handle import Handle
from utils.img import Img
from utils.log import log
from utils.mini_asu import ASU
from utils.monthly_pass import MonthlyPass
from utils.mouse_event import MouseEvent
from utils.pause import Pause
from utils.window import Window


class Calculated:
    def __init__(self):
        self.cfg = ConfigurationManager()
        self.window = Window()
        self.img = Img()
        self.monthly_pass = MonthlyPass()
        self.mouse_event = MouseEvent()
        self._config = None
        self._last_updated = None
        self.keyboard = KeyboardController()
        self.handle = Handle()
        self.asu = ASU()
        self.blackscreen = BlackScreen()

        self.hwnd = self.window.hwnd


    def run_mapload_check(self, error_count=0, max_error_count=10, threshold=0.9):
        """
        说明：
            计算地图加载时间
        """
        start_time = time.time()
        target = cv2.imread('./picture/map_load.png')
        time.sleep(1)  # 短暂延迟后开始判定是否为地图加载or黑屏跳转
        while error_count < max_error_count:
            result = self.img.scan_screenshot(target)
            if result and result['max_val'] > 0.95:
                log.info(f"检测到地图加载map_load，匹配度{result['max_val']}")
                if self.img.on_main_interface(check_list=[self.img.main_ui, self.img.finish2_ui, self.img.finish2_1_ui, self.img.finish2_2_ui, self.img.finish3_ui], timeout=10, threshold=threshold):
                    break
            elif self.blackscreen.check_blackscreen():
                self.blackscreen.run_blackscreen_cal_time()
                break
            elif self.img.on_main_interface(check_list=[self.img.main_ui, self.img.finish2_ui, self.img.finish2_1_ui, self.img.finish2_2_ui, self.img.finish3_ui], threshold=threshold):
                time.sleep(1)
                if self.img.on_main_interface(check_list=[self.img.main_ui, self.img.finish2_ui, self.img.finish2_1_ui, self.img.finish2_2_ui, self.img.finish3_ui], threshold=threshold):
                    log.info("连续检测到主界面，地图加载标记为结束")
                    break
            elif self.img.on_interface(check_list=[self.img.finish5_ui], timeout=3, interface_desc='模拟宇宙积分奖励界面'):
                time.sleep(1)
                if self.img.on_interface(check_list=[self.img.finish5_ui], timeout=3, interface_desc='模拟宇宙积分奖励界面'):
                    log.info("连续检测到模拟宇宙积分奖励界面，地图加载标记为结束")
                    break
            else:
                error_count += 1
                time.sleep(1)
                log.info(
                    f'未查询到地图加载状态{error_count}次，加载图片匹配值{result["max_val"]:.3f}')
        else:
            log.info(f'加载地图超时，已重试{error_count}次，强制执行下一步')
        end_time = time.time()
        loading_time = end_time - start_time
        if error_count < max_error_count:
            log.info(f'地图载毕，用时 {loading_time:.1f} 秒')
        time.sleep(1)  # 增加1秒等待防止人物未加载错轴

    def run_dreambuild_check(self, error_count=0, max_error_count=10):
        """
        说明：
            筑梦模块移动模块加载时间
        """
        start_time = time.time()
        target = cv2.imread('./picture/finish_fighting.png')
        time.sleep(3)  # 短暂延迟后开始判定
        while error_count < max_error_count:
            result = self.img.scan_screenshot(target)
            if result["max_val"] > 0.9:
                break
            else:
                error_count += 1
                time.sleep(1)
        end_time = time.time()
        loading_time = end_time - start_time
        if error_count >= max_error_count:
            log.info(
                f'移动模块加载超时，用时 {loading_time:.1f} 秒，识别图片匹配值{result["max_val"]:.3f}')
        else:
            log.info(f'移动模块成功，用时 {loading_time:.1f} 秒')
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
        round_disable = cv2.imread("./picture/round_disable.png")
        if self.img.on_interface(check_list=[round_disable], timeout=5, interface_desc='无法购买', threshold=0.95):
            return False
        else:
            return True

    def first_role_check(self):
        """
        按下'1'，确认队伍中的1号位属于跑图角色
        """
        log.info("开始判断1号位")
        image, *_ = self.img.take_screenshot(offset=(1670, 339, -160, -739))
        image_hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        # 定义HSV颜色范围
        color_ranges = [
            (np.array([28, 49, 253]), np.array([32, 189, 255])),
            (np.array([114, 240, 216]), np.array([116, 246, 226]))
        ]

        # 检查符合条件的像素
        for lower, upper in color_ranges:
            pixels = cv2.inRange(image_hsv, lower, upper)
            if np.any(pixels):
                pyautogui.press('1')
                log.info("设置1号位为跑图角色")
                break
