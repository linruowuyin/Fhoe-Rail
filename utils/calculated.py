import time

import cv2 as cv
import numpy as np
import pyautogui
import win32api
import win32con
import win32gui
import pyautogui
import random
from datetime import datetime
from PIL import ImageGrab
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Listener as MouseListener

from .config import read_json_file, CONFIG_FILE_NAME
from .exceptions import Exception
from .log import log
class Calculated:
    def __init__(self):
        self.CONFIG = read_json_file(CONFIG_FILE_NAME)
        self.keyboard = KeyboardController()

    def on_move(self, x, y):
        pass

    def wait_for_mouse_stop(self, initial_pos):
        current_pos = win32api.GetCursorPos()
        while current_pos != initial_pos:
            time.sleep(0.1)
            initial_pos = current_pos
            current_pos = win32api.GetCursorPos()

    def move_to_and_click(self, x, y):
        initial_pos = win32api.GetCursorPos()
        with MouseListener(on_move=self.on_move) as listener:
            win32api.SetCursorPos((x, y))
            self.wait_for_mouse_stop(initial_pos)
            current_pos = win32api.GetCursorPos()
            if current_pos == (x, y):
                pyautogui.mouseDown(x, y, button='left')
                time.sleep(0.4)
                pyautogui.mouseUp(x, y, button='left')
            else:
                win32api.SetCursorPos((x, y))
                pyautogui.mouseDown(x, y, button='left')
                time.sleep(0.4)
                pyautogui.mouseUp(x, y, button='left')

    def click(self, points):
        x, y = int(points[0]), int(points[1])
        screen_width, screen_height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        x = max(0, min(x, screen_width - 1))
        y = max(0, min(y, screen_height - 1))

        # 确保鼠标点击位置不超出屏幕边界
        self.move_to_and_click(x, y)

    def relative_click(self, points):
        """
        说明：
            点击相对坐标
        参数：
            :param points: 百分比坐标
        """
        hwnd = win32gui.FindWindow("UnityWndClass", "崩坏：星穹铁道")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        real_width = self.CONFIG["real_width"]
        real_height = self.CONFIG["real_height"]
        x, y = int(left + (right - left) / 100 * points[0]), int(
            top + (bottom - top) / 100 * points[1]
        )
        log.info((x, y))
        log.debug((x, y))
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.5)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def take_screenshot(self):
        # 返回RGB图像
        hwnd = win32gui.FindWindow("UnityWndClass", "崩坏：星穹铁道")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        picture = ImageGrab.grab((left, top, right, bottom), all_screens=True)
        screenshot = np.array(picture)
        screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)
        return screenshot, left, top, right, bottom

    def scan_screenshot(self, prepared) -> dict:
        """
        说明：
            比对图片
        参数：
            :param prepared: 比对图片地址
        """
        screenshot, left, top, right, bottom = self.take_screenshot()
        result = cv.matchTemplate(screenshot, prepared, cv.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
        return {
            "screenshot": screenshot,
            "min_val": min_val,
            "max_val": max_val,
            "min_loc": (min_loc[0] + left, min_loc[1] + top),
            "max_loc": (max_loc[0] + left, max_loc[1] + top),
        }

    def calculated(self, result, shape):
        mat_top, mat_left = result["max_loc"]
        prepared_height, prepared_width, prepared_channels = shape

        x = int((mat_top + mat_top + prepared_width) / 2)

        y = int((mat_left + mat_left + prepared_height) / 2)

        return x, y

    # flag为true一定要找到
    def click_target(self, target_path, threshold, flag=True):
        target = cv.imread(target_path)
        while True:
            result = self.scan_screenshot(target)
            if result["max_val"] > threshold:
                points = self.calculated(result, target.shape)
                self.click(points)
                return
            if not flag:
                return

    def fighting(self):
        start_time = time.time()
        attack = cv.imread("./picture/attack.png")
        doubt = cv.imread("./picture/doubt.png")
        warn = cv.imread("./picture/warn.png")
        while True:
            log.info("识别中")
            attack_result = self.scan_screenshot(attack)
            doubt_result = self.scan_screenshot(doubt)
            warn_result = self.scan_screenshot(warn)
            if attack_result["max_val"] > 0.9:
                points = self.calculated(attack_result, attack.shape)
                self.click(points)
                break
            elif doubt_result["max_val"] > 0.9 or warn_result["max_val"] > 0.9:
                log.info("識別到疑問或警告，等待怪物開戰")
                points = self.calculated(attack_result, attack.shape)
                self.click(points)
                time.sleep(5)
                target = cv.imread("./picture/finish_fighting.png")  # 識別是否已進入戰鬥，若已進入則跳出迴圈
                result = self.scan_screenshot(target)
                if result["max_val"] < 0.9:
                    break
            elif time.time() - start_time > 10:  # 如果已经识别了10秒还未找到目标图片，则退出循环
                log.info("识别超时,此处可能无敌人")
                return
        time.sleep(6)
        target = cv.imread("./picture/auto.png")
        start_time = time.time()
        if self.CONFIG["auto_battle_persistence"] != 1:
            while True:
                result = self.scan_screenshot(target)
                if result["max_val"] > 0.9:
                    points = self.calculated(result, target.shape)
                    self.click(points)
                    log.info("开启自动战斗")
                    break
                elif time.time() - start_time > 15:
                    break
        else:
            log.info("不点击自动(沿用配置)")
            time.sleep(5)

        start_time = time.time()  # 开始计算战斗时间
        target = cv.imread("./picture/finish_fighting.png")
        while True:
            result = self.scan_screenshot(target)
            if result["max_val"] > 0.9:
                points = self.calculated(result, target.shape)
                log.debug(points)
                elapsed_time = time.time() - start_time
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.0f}秒"
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                current_system_time = time.localtime()
                colored_message = (f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(colored_message)
                time.sleep(3)
                break


    def fightE(self):
        start_time = time.time()
        attack = cv.imread("./picture/attack.png")
        doubt = cv.imread("./picture/doubt.png")
        warn = cv.imread("./picture/warn.png")
        image_A = cv.imread("./picture/eat.png")  # 修改
        image_B = cv.imread("./picture/cancel.png")  # 修改
        
        while True:
            log.info("识别中")
            attack_result = self.scan_screenshot(attack)
            doubt_result = self.scan_screenshot(doubt)
            warn_result = self.scan_screenshot(warn)
            
            if attack_result["max_val"] > 0.9:
                pyautogui.press('e')
                time.sleep(1)
                start_time_A = time.time()
                result_A = None
                while result_A is None and time.time() - start_time_A < 3:
                    result_A = self.scan_screenshot(image_A)
                    
                if result_A is not None and result_A["max_val"] > 0.9:
                    while True:
                        result_B = self.scan_screenshot(image_B)
                        points_B = self.calculated(result_B, image_B.shape)
                        self.click(points_B)
                        if result_B is None or result_B["max_val"] < 0.9:  # 修改条件判断语句
                           break
                        else:
                            break
                        
                points = self.calculated(attack_result, attack.shape)
                time.sleep(3)
                self.click(points)
                break
            elif doubt_result["max_val"] > 0.9 or warn_result["max_val"] > 0.9:
                log.info("識別到疑問或警告，等待怪物開戰")
                self.click(points)
                time.sleep(3)
                target = cv.imread("./picture/finish_fighting.png")  # 識別是否已進入戰鬥，若已進入則跳出迴圈
                result = self.scan_screenshot(target)
                if result["max_val"] < 0.9:
                    break
            elif time.time() - start_time > 10:  # 如果已经识别了10秒还未找到目标图片，则退出循环
                log.info("识别超时,此处可能无敌人")
                return
        time.sleep(6)
        target = cv.imread("./picture/auto.png")
        start_time = time.time()
        if self.CONFIG["auto_battle_persistence"] != 1:
            while True:
                result = self.scan_screenshot(target)
                if result["max_val"] > 0.9:
                    points = self.calculated(result, target.shape)
                    self.click(points)
                    log.info("开启自动战斗")
                    break
                elif time.time() - start_time > 15:
                    break
        else:
            log.info("不点击自动(沿用配置)")
            time.sleep(5)

        start_time = time.time()  # 开始计算战斗时间
        target = cv.imread("./picture/finish_fighting.png")
        while True:
            result = self.scan_screenshot(target)
            if result["max_val"] > 0.9:
                points = self.calculated(result, target.shape)
                log.debug(points)
                elapsed_time = time.time() - start_time
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.0f}秒"
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                current_system_time = time.localtime()
                colored_message = (f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(colored_message)
                time.sleep(3)
                break

    def auto_map(self, map, old=True):
        map_data = (
            read_json_file(f"map\\old\\{map}.json")
            if old
            else read_json_file(f"map\\{map}.json")
        )
        map_filename = map
        # 开始寻路
        log.info("开始寻路")
        for map_index, map in enumerate(map_data["map"]):
            log.info(f"执行{map_filename}文件:{map_index + 1}/{len(map_data['map'])} {map}")
            key = list(map.keys())[0]
            value = map[key]
            if key == "f":
                # 生成0.3到0.7之间的随机浮点数
                random_interval = random.uniform(0.3, 0.7)
                num_repeats = int(value / random_interval)
                for i in range(num_repeats):
                    self.keyboard.press(key)
                    self.keyboard.release(key)
                    time.sleep(random_interval)  # 使用随机间隔
                remaining_time = value - (num_repeats * random_interval)
                if remaining_time > 0:
                    time.sleep(remaining_time) 
            elif key == "mouse_move":
                self.mouse_move(value)
            elif key == "fighting":
                if value == 1:  # 进战斗
                    self.fighting()
                elif value == 2:  # 障碍物
                    self.click(win32api.GetCursorPos())
                    time.sleep(1)
                else:
                    raise Exception((f"map数据错误, fighting参数异常:{map_filename}", map))
            elif key == "scroll":
                self.scroll(value)
            elif key == "shutdown":
                if self.CONFIG["auto_shutdown"] is True:
                    log.info("下班喽！I'm free!")
                    import os
                    os.system("shutdown /s /f /t 0")
                else:
                    log.info("锄地结束！")
            elif key == "e":
                if value == 1:  # 进战斗
                    self.fightE()
            else:
                self.keyboard.press(key)
                start_time = time.perf_counter()
                while time.perf_counter() - start_time < value:
                    pass
                self.keyboard.release(key)

    def mouse_move(self, x):
        scaling = 1.0
        dx = int(x * scaling)
        i = int(dx / 200)
        last = dx - i * 200

        # 视角移动的步长
        step = 200 if dx > 0 else -200

        for _ in range(abs(i)):
            win32api.mouse_event(1, step, 0)  # 进行视角移动
            time.sleep(0.1)

        if last != 0:
            win32api.mouse_event(1, last, 0)  # 进行视角移动

        time.sleep(0.5)

    def monthly_pass(self):
        """
        说明：
            点击月卡
        """
        start_time = time.time()
        dt = datetime.now().strftime('%Y-%m-%d') + " 04:00:00"
        ts = int(time.mktime(time.strptime(dt, "%Y-%m-%d %H:%M:%S")))
        ns = int(start_time)
        if -60 < ns - ts <= 60:
            log.info("点击月卡")
            pos = self.ocr_click("今日补给")
            time.sleep(0.5)
            self.click(pos)

    def scroll(self, clicks: float):
        """
        说明：
            控制鼠标滚轮滚动
        参数：
            :param clicks 滚动单位，正数为向上滚动
        """
        pyautogui.scroll(clicks)
        time.sleep(0.5)

    def is_blackscreen(self, threshold=25):
        screenshot = cv.cvtColor(self.take_screenshot()[0], cv.COLOR_BGR2GRAY)
        
        if cv.mean(screenshot)[0] > threshold:  # 如果平均像素值大于阈值
            target = cv.imread("./picture/finish_fighting.png")
            while True:
                result = self.scan_screenshot(target)
                if result["max_val"] > 0.9:
                    return False  # 如果匹配度大于0.9，表示不是黑屏，返回False

        return cv.mean(screenshot)[0] < threshold

