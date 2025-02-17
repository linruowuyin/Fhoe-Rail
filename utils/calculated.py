import os
import time
from datetime import datetime

import cv2
import numpy as np
import pyautogui
from pynput.keyboard import Controller as KeyboardController

from utils.blackscreen import BlackScreen
from utils.config import ConfigurationManager
from utils.handle import Handle
from utils.img import Img
from utils.log import log
from utils.mini_asu import ASU
from utils.monthly_pass import MonthlyPass
from utils.mouse_event import MouseEvent
from utils.pause import Pause
from utils.switch_window import switch_window
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

        self.need_rotate = False



    def auto_map(self, map_name, normal_run=False, rotate=False, dev=False, last_point=''):
        self.pause = Pause(dev=dev)
        map_version = self.cfg.config_file.get("map_version", "default")
        # self.asu.screen = self.img.take_screenshot()[0]
        # self.ang = self.asu.get_now_direc()
        self.need_rotate = rotate
        now = datetime.now()
        today_weekday_str = now.strftime('%A')
        map_data = self.cfg.read_json_file(
            f"map/{map_version}/{map_name}.json")
        map_filename = map_name
        self.handle.fighting_count = sum(
            1 for map in map_data["map"] if "fighting" in map and map["fighting"] == 1)
        self.handle.current_fighting_index = 0
        total_map_count = len(map_data['map'])
        self.first_role_check()  # 1号位为跑图角色
        dev_restart = True  # 初始化开发者重开
        self.handle.handle_view_set(0.1)
        # 开发群657378574，密码hoe2333
        while dev_restart:
            dev_restart = False  # 不进行重开
            last_key = ""
            self.handle.last_step_run = False  # 初始化上一次为走路
            for map_index, map_value in enumerate(map_data["map"]):
                press_key = self.pause.check_pause(
                    dev=dev, last_point=last_point)
                if press_key:
                    if press_key == 'F7':
                        pass
                    else:
                        dev_restart = True  # 检测到需要重开
                        switch_window()
                        time.sleep(1)
                        if press_key == 'F9':
                            self.mouse_event.click_target(
                                "picture\\transfer.png", 0.93)
                            self.run_mapload_check()
                        if press_key == 'F10':
                            pass
                        map_data = self.cfg.read_json_file(
                            f"map/{map_version}/{map_name}.json")  # 重新读取最新地图文件
                        break
                log.info(
                    f"执行{map_filename}文件:{map_index + 1}/{total_map_count} {map_value}")

                key, value = next(iter(map_value.items()))
                self.monthly_pass.monthly_pass_check()  # 行进前识别是否接近月卡时间
                if key == "space":
                    self.handle.handle_space(value, key)
                elif key == "caps":
                    self.handle.handle_caps(value)
                elif key == "r":
                    self.handle.handle_r(value, key)
                elif key == "f":
                    self.handle.handle_f(value)
                elif key == "check":
                    self.handle.handle_check(value, today_weekday_str)
                elif key == "mouse_move":
                    self.handle.mouse_move(value)
                elif key == "fighting":
                    self.handle.handle_fighting(value)
                elif key == "scroll":
                    self.handle.scroll(value)
                elif key == "shutdown":
                    self.handle.handle_shutdown()
                elif key == "e":
                    self.handle.handle_e(value)  # 用E进入战斗
                elif key == "esc":
                    self.handle.handle_esc(value)
                elif key in ['1', '2', '3', '4', '5']:
                    self.handle.handle_num(value, key)
                elif key == "main":
                    self.handle.handle_main(value)
                elif key == "view_set":
                    self.handle.handle_view_set(value)
                elif key == "view_reset":
                    self.handle.handle_view_reset(value)
                elif key == "view_rotate":
                    self.handle.handle_view_rotate(value)
                elif key == "await":
                    time.sleep(value)
                else:
                    self.handle.handle_move(value, key, normal_run, last_key)

                if map_version == "HuangQuan":
                    last_key = key

            if map_version == "HuangQuan":
                doubt_result = self.img.scan_screenshot(
                    self.img.doubt_ui, offset=(0, 0, -1630, -800))
                if doubt_result["max_val"] > 0.92:
                    log.info("检测到警告，有可能漏怪，进入黄泉乱砍模式")
                    start_time = time.time()
                    while time.time() - start_time < 60 and doubt_result["max_val"] > 0.92:
                        directions = ["w", "a", "s", "d"]
                        for index, direction in enumerate(directions):
                            log.info(f"开砍，{directions[index]}")
                            for i in range(3):
                                self.handle.handle_move(
                                    0.1, direction, False, "")
                                self.handle.fight_e(value=2)
                            doubt_result = self.img.scan_screenshot(
                                self.img.doubt_ui, offset=(0, 0, -1630, -800))

            if map_version == "HuangQuan" and last_key == "e":
                if not self.img.on_main_interface(timeout=0.2):
                    fight_status = self.handle.fight_elapsed()
                    if not fight_status:
                        log.info('未进入战斗')

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
