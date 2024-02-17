import time
import os
import cv2 as cv
import numpy as np
import pyautogui
import win32api
import win32con
import win32gui
import random
from datetime import datetime
from PIL import ImageGrab
from pynput.keyboard import Controller as KeyboardController

from .config import read_json_file, CONFIG_FILE_NAME
from .exceptions import Exception
from .log import log
from .mini_asu import ASU


class Calculated:
    def __init__(self):
        self.CONFIG = read_json_file(CONFIG_FILE_NAME)
        self.keyboard = KeyboardController()
        self.ASU = ASU()
        self.game_hwnd = self.get_game_window_handle()

    def get_game_window_handle(self):
        return win32gui.FindWindow("UnityWndClass", "崩坏：星穹铁道")

    def click(self, points):
        x, y = int(points[0]), int(points[1])
        log.debug((x, y))
        self.move_and_click(x, y)

    def relative_click(self, points):
        x, y = self.calculate_relative_position(points)
        log.info((x, y))
        log.debug((x, y))
        self.press_alt_and_click(x, y)

    def click_center(self):
            left, top, right, bottom = win32gui.GetWindowRect(self.game_hwnd)
            x = int((left + right) / 2)
            y = int((top + bottom) / 2)
            win32api.SetCursorPos((x, y))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            time.sleep(random.uniform(0.1, 0.15))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def calculate_relative_position(self, points):
        left, top, right, bottom = win32gui.GetWindowRect(self.game_hwnd)
        width = right - left
        height = bottom - top
        x = int(left + width * points[0] / 100)
        y = int(top + height * points[1] / 100)
        return x, y

    def move_and_click(self, x, y):
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(random.uniform(0.09, 0.15))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def press_alt_and_click(self, x, y):
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        self.move_and_click(x, y)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    def take_screenshot(self):
        left, top, right, bottom = win32gui.GetWindowRect(self.game_hwnd)
        screenshot_left, screenshot_top, screenshot_right, screenshot_bottom = self.adjust_screenshot_area(left, top, right, bottom)
        picture = ImageGrab.grab((screenshot_left, screenshot_top, screenshot_right, screenshot_bottom), all_screens=True)
        screenshot = np.array(picture)
        screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)
        return screenshot, screenshot_left, screenshot_top, screenshot_right, screenshot_bottom

    def adjust_screenshot_area(self, left, top, right, bottom):
        screenshot_left = left
        screenshot_top = top
        screenshot_right = min(right, left + 1920)
        screenshot_bottom = min(bottom, top + 1080)

        if bottom > 1080:
            screenshot_top = max(top, bottom - 1080)

        return screenshot_left, screenshot_top, screenshot_right, screenshot_bottom

    def scan_screenshot(self, prepared) -> dict:
        screenshot, left, top, _, _ = self.take_screenshot()
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

    def click_target(self, target_path, threshold, flag=True):
        original_target = cv.imread(target_path)
        start_time = time.time()

        while True:
            elapsed_time = time.time() - start_time

            result = self.scan_screenshot(original_target)
            if result["max_val"] > threshold:
                points = self.calculated(result, original_target.shape)
                self.click(points)
                return

            if elapsed_time > 8:
                inverted_target = cv.bitwise_not(original_target)
                result = self.scan_screenshot(inverted_target)
                if result["max_val"] > threshold:
                    points = self.calculated(result, inverted_target.shape)
                    self.click(points)
                    log.info("阴阳变转")
                    return

            if not flag:
                return

            if elapsed_time > 30:
                return

    def click_target_with_alt(self, target_path, threshold, flag=True):
        self.press_alt()
        self.click_target(target_path, threshold, flag)
        self.release_alt()

    def press_alt(self):
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)

    def release_alt(self):
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    def fighting(self):
            # 初始化开始时间
            start_time = time.time()

            # 读取游戏内不同状态的图片资源
            attack, doubt, warn, finish_fighting, auto = map(lambda img_path: cv.imread(img_path), [
                "./picture/attack.png",
                "./picture/doubt.png",
                "./picture/warn.png",
                "./picture/finish_fighting.png",
                "./picture/auto.png"
            ])

            # 主循环：寻找攻击、疑问或警告标志
            while True:
                log.info("识别中")

                # 扫描并识别截图中的指定图像
                scan_results = {
                    "attack": self.scan_screenshot(attack),
                    "doubt": self.scan_screenshot(doubt),
                    "warn": self.scan_screenshot(warn)
                }

                # 检查识别结果
                if scan_results["attack"]["max_val"] > 0.9:
                    points = self.calculated(scan_results["attack"], attack.shape)
                    self.click_center()
                    break

                elif (scan_results["doubt"]["max_val"] > 0.9 or scan_results["warn"]["max_val"] > 0.9):
                    log.info("识别到疑問或警告，等待怪物开戰")
                    points = self.calculated(scan_results["attack"], attack.shape)
                    self.click_center()
                    time.sleep(5)

                    # 检查是否进入战斗状态
                    in_battle = self.scan_screenshot(finish_fighting)["max_val"] < 0.9
                    if in_battle:
                        break

                elif time.time() - start_time > 10:
                    log.info("识别超时,此处可能无敌人")
                    return

            # 等待并开启自动战斗（根据配置）
            time.sleep(5)
            if self.CONFIG["auto_battle_persistence"] != 1:
                start_time = time.time()
                while True:
                    result = self.scan_screenshot(auto)
                    if result["max_val"] > 0.9:
                        points = self.calculated(result, auto.shape)
                        self.click(points)
                        log.info("开启自动战斗")
                        break
                    elif time.time() - start_time > 15:
                        break
            else:
                log.info("不点击自动(沿用配置)")
                time.sleep(5)

            # 计算战斗时间
            start_time = time.time()
            while True:
                result = self.scan_screenshot(finish_fighting)
                if result["max_val"] > 0.92:
                    points = self.calculated(result, finish_fighting.shape)
                    elapsed_time = time.time() - start_time
                    formatted_time = f"{elapsed_time // 60}分钟{elapsed_time % 60:.2f}秒"
                    log.info(f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                    log.info(f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})")

                    self.rotate()
                    time.sleep(3)
                    break

                # 超时处理及尝试恢复游戏状态
                elapsed_time = time.time() - start_time
                if elapsed_time > 90:
                    for img_path, threshold in (
                        ("./picture/auto.png", 0.98),
                        ("./picture/continue_fighting.png", 0.98),
                        ("./picture/defeat.png", 0.98),
                        ("./picture/map_4-2_point_3.png", 0.98),
                        ("./picture/orientation_close.png", 0.98)
                    ):
                        self.click_target(img_path, threshold, False)

                    if elapsed_time > 900:
                        log.info("战斗超时")
                        break
                    time.sleep(0.5)

    def fightE(self):
        # 初始化开始时间
        start_time = time.time()

        # 读取游戏内不同状态的图片资源
        images = {
            "attack": cv.imread("./picture/attack.png"),
            "doubt": cv.imread("./picture/doubt.png"),
            "warn": cv.imread("./picture/warn.png"),
            "eat": cv.imread("./picture/eat.png"),
            "confirm": cv.imread("./picture/confirm.png"),
            "cancel": cv.imread("./picture/cancel.png"),
            "finish_fighting": cv.imread("./picture/finish_fighting.png"),
            "auto": cv.imread("./picture/auto.png")
        }

        while True:
            log.info("识别中")

            # 获取识别结果
            scan_results = {
                "attack": self.scan_screenshot(images["attack"]),
                "doubt": self.scan_screenshot(images["doubt"]),
                "warn": self.scan_screenshot(images["warn"])
            }

            if scan_results["attack"]["max_val"] > 0.9:
                pyautogui.press('e')
                time.sleep(1)
                self.click_center()

                # 处理吃药环节
                start_time_eat = time.time()
                result_eat = None
                while result_eat is None and time.time() - start_time_eat < 3:
                    result_eat = self.scan_screenshot(images["eat"])

                if result_eat is not None and result_eat["max_val"] > 0.9:
                    while True:
                        confirm_result = self.scan_screenshot(images["confirm"])
                        cancel_result = self.scan_screenshot(images["cancel"])
                        confirm_points = self.calculated(confirm_result, images["confirm"].shape)
                        cancel_points = self.calculated(cancel_result, images["cancel"].shape)
                        time.sleep(0.5)
                        self.click(confirm_points)
                        time.sleep(0.5)
                        self.click(cancel_points)
                        time.sleep(0.5)

                        # 判断是否跳出循环
                        if cancel_result is None or cancel_result["max_val"] < 0.99:
                            break
                        pyautogui.press('e')
                        time.sleep(1)
                        self.click_center()
                        time.sleep(0.5)
                        self.click_center()
                        break
                
                break

            elif (scan_results["doubt"]["max_val"] > 0.9 or scan_results["warn"]["max_val"] > 0.9):
                log.info("识別到疑問或警告，等待怪物开戰")
                self.click_center()
                time.sleep(3)

                # 检查是否进入战斗状态
                in_battle = self.scan_screenshot(images["finish_fighting"])["max_val"] < 0.9
                if in_battle:
                    break

            elif time.time() - start_time > 10:
                log.info("识别超时,此处可能无敌人")
                return

        # 等待并开启自动战斗（根据配置）
        time.sleep(6)
        if self.CONFIG["auto_battle_persistence"] != 1:
            start_time = time.time()
            while True:
                result = self.scan_screenshot(images["auto"])
                if result["max_val"] > 0.9:
                    points = self.calculated(result, images["auto"].shape)
                    self.click(points)
                    log.info("开启自动战斗")
                    break
                elif time.time() - start_time > 15:
                    break
        else:
            log.info("不点击自动(沿用配置)")
            time.sleep(5)

        # 计算战斗时间
        start_time = time.time()
        while True:
            result = self.scan_screenshot(images["finish_fighting"])
            if result["max_val"] > 0.92:
                points = self.calculated(result, images["finish_fighting"].shape)
                elapsed_time = time.time() - start_time
                formatted_time = f"{elapsed_time // 60}分钟{elapsed_time % 60:.2f}秒"
                log.info(f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})")

                self.rotate()
                time.sleep(3)
                break
            
    def rotate(self):
        if self.need_rotate:
            self.keyboard.press('w')
            self.keyboard.release('w')
            time.sleep(0.7)
            self.ASU.screen = self.take_screenshot()[0]
            ang = self.ang - self.ASU.get_now_direc()
            ang = (ang + 900) % 360 - 180
            self.mouse_move(ang * 10.2)

    def click_fir(self, threshold=0.9):
        self.click_target_with_alt(target_path="./picture/fir.png", threshold=threshold)
        time.sleep(10)

    def click_rec(self, threshold=0.9):
        self.click_target_with_alt(target_path="./picture/rec.png", threshold=threshold)
        time.sleep(10)

    def auto_map(self, map, old=True, rotate=False):
        self.ASU.screen = self.take_screenshot()[0]
        self.ang = self.ASU.get_now_direc()
        self.need_rotate = rotate
        now = datetime.now()
        today_weekday_str = now.strftime('%A')
        map_data = (
            read_json_file(f"map\\old\\{map}.json")
            if old
            else read_json_file(f"map\\{map}.json")
        )
        map_filename = map
        for map_index, map in enumerate(map_data["map"]):
            log.info(f"执行{map_filename}文件:{map_index + 1}/{len(map_data['map'])} {map}")
            key = list(map.keys())[0]
            value = map[key]
            if key == "e" or key == "space" or key == "r": 
                # 生成0.1到0.3之间的随机浮点数
                random_interval = random.uniform(0.3, 0.7)
                num_repeats = int(value / random_interval)
                for i in range(num_repeats):
                    self.keyboard.press(key)
                    self.keyboard.release(key)
                    time.sleep(random_interval)  # 使用随机间隔
                remaining_time = value - (num_repeats * random_interval)
                if remaining_time > 0:
                    time.sleep(remaining_time)
            if key == "check" and value == 1:
            # 判断是否为周二或周日
                today_weekday_num = now.weekday()
                if today_weekday_num  in [1, 4, 6]:  # 1代表周二，6代表周日
                    log.info(f"{today_weekday_str}，周二五日，尝试购买")
                else:
                    log.info(f"{today_weekday_str}，非周二五日，跳过")
                    return
            elif key == "mouse_move":
                self.mouse_move(value)
            elif key == "fir":
                self.click_fir()
            elif key == "rec":
                self.click_rec()
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
            elif key == "f":
                if value == 1:  # 进战斗
                    self.fightE()
            elif key == "esc":
                if value == 1:  # 执行一次esc键的按下和释放操作
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0) 
                    time.sleep(random.uniform(0.09, 0.15)) 
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
                else:
                    raise Exception((f"map数据错误, esc参数只能为1:{map_filename}", map))
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
        screenshot_gray = cv.cvtColor(self.take_screenshot()[0], cv.COLOR_BGR2GRAY)
        avg_pixel = cv.mean(screenshot_gray)[0]

        if avg_pixel > threshold:  # 如果平均像素值大于阈值
            image_folder = "./picture/"
            finish_fighting_images = [f for f in os.listdir(image_folder) if f.startswith("finish_fighting")]

            for _ in range(3):  # 尝试3次
                for image_name in finish_fighting_images:
                    target = cv.imread(os.path.join(image_folder, image_name))
                    result = self.scan_screenshot(target)
                    
                    if result and result["max_val"] > 0.9:
                        return False  # 匹配成功且匹配度大于0.9，返回False

                time.sleep(2)  # 每尝试完一轮图片后等待2秒

        return True  # 如果经过3轮尝试仍未找到匹配成功的图片，则返回True
