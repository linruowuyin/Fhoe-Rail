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

import time

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

    def click(self, points):
        """
        说明：
            点击坐标
        参数：
            :param points: 坐标
        """
        x, y = int(points[0]), int(points[1])
        log.debug((x, y))
        
        # 移动鼠标并点击
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

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
        
        # Press Alt key
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    def click_center(self):
        """
        点击游戏窗口中心位置
        """
        hwnd = win32gui.FindWindow("UnityWndClass", "崩坏：星穹铁道")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        x = int((left + right) / 2)
        y = int((top + bottom) / 2)
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def take_screenshot(self):
        """
        获取游戏窗口的屏幕截图
        """
        hwnd = win32gui.FindWindow("UnityWndClass", "崩坏：星穹铁道")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        # 计算截图范围
        screenshot_left = left
        screenshot_top = top
        screenshot_right = min(right, left + 1920)
        screenshot_bottom = min(bottom, top + 1080)

        # 如果游戏窗口的底部坐标高于 1080，则调整截图范围
        if bottom > 1080:
            screenshot_top = max(top, bottom - 1080)

        # 获取游戏窗口截图
        picture = ImageGrab.grab((screenshot_left, screenshot_top, screenshot_right, screenshot_bottom), all_screens=True)
        screenshot = np.array(picture)
        screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)
        return screenshot, screenshot_left, screenshot_top, screenshot_right, screenshot_bottom

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
        original_target = cv.imread(target_path)
        start_time = time.time()
        
        while True:
            elapsed_time = time.time() - start_time
            
            # 匹配预定义目标图像
            result = self.scan_screenshot(original_target)
            if result["max_val"] > threshold:
                points = self.calculated(result, original_target.shape)
                self.click(points)
                return

            # 如果超过3秒，同时匹配原图像和颜色反转后的图像
            if elapsed_time > 3:
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
        # 按下Alt键
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        
        # 调用click_target方法
        self.click_target(target_path, threshold, flag)
        
        # 释放Alt键
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

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
                self.click_center()
                break
            elif doubt_result["max_val"] > 0.9 or warn_result["max_val"] > 0.9:
                log.info("識別到疑問或警告，等待怪物開戰")
                points = self.calculated(attack_result, attack.shape)
                self.click_center()
                time.sleep(5)
                target = cv.imread("./picture/finish_fighting.png")  # 識別是否已進入戰鬥，若已進入則跳出迴圈
                result = self.scan_screenshot(target)
                if result["max_val"] < 0.9:
                    break
            elif time.time() - start_time > 10:  # 如果已经识别了10秒还未找到目标图片，则退出循环
                log.info("识别超时,此处可能无敌人")
                return
        time.sleep(5)
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
            if result["max_val"] > 0.92:
                points = self.calculated(result, target.shape)
                log.debug(points)
                elapsed_time = time.time() - start_time
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                current_system_time = time.localtime()
                colored_message = (f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(colored_message)
                match_details = f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})"
                log.info(match_details)

                self.rotate()
                time.sleep(3)
                break
            
            elapsed_time = time.time() - start_time
            if elapsed_time > 90:
                self.click_target("./picture/auto.png", 0.98, False)  #超时尝试开启自动战斗
                self.click_target("./picture/continue_fighting.png", 0.98, False)  #战斗暂停界面点击继续战斗
                self.click_target("./picture/defeat.png", 0.98, False)  #战斗失败
                self.click_target("./picture/map_4-2_point_3.png", 0.98, False)  #3D地图返回
                self.click_target("./picture/orientation_close.png", 0.98, False)  #退出地图界面
                if elapsed_time > 900:
                    log.info("战斗超时")
                    break
                time.sleep(0.5)


    def fightE(self):
        start_time = time.time()
        attack = cv.imread("./picture/attack.png")
        doubt = cv.imread("./picture/doubt.png")
        warn = cv.imread("./picture/warn.png")
        eat = cv.imread("./picture/eat.png")  
        cancel = cv.imread("./picture/cancel.png") 

        while True:
            log.info("识别中")
            attack_result = self.scan_screenshot(attack)
            doubt_result = self.scan_screenshot(doubt)
            warn_result = self.scan_screenshot(warn)

            if attack_result["max_val"] > 0.9:
                pyautogui.press('e')
                time.sleep(0.6)
                start_time_eat = time.time()
                result_eat = None
                while result_eat is None and time.time() - start_time_eat < 3:
                    result_eat = self.scan_screenshot(eat) 

                if result_eat is not None and result_eat["max_val"] > 0.9:
                    while True:
                        result_cancel = self.scan_screenshot(cancel)  
                        points_cancel = self.calculated(result_cancel, cancel.shape)
                        self.click(points_cancel)
                        if result_cancel is None or result_cancel["max_val"] < 0.9: 
                            break
                        else:
                            break
                time.sleep(0.5)
                self.click_center()
                break
            elif doubt_result["max_val"] > 0.9 or warn_result["max_val"] > 0.9:
                log.info("识別到疑問或警告，等待怪物开戰")
                self.click_center()
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
            if result["max_val"] > 0.92:
                points = self.calculated(result, target.shape)
                log.debug(points)
                elapsed_time = time.time() - start_time
                elapsed_minutes = int(elapsed_time // 60)
                elapsed_seconds = elapsed_time % 60
                formatted_time = f"{elapsed_minutes}分钟{elapsed_seconds:.2f}秒"
                current_system_time = time.localtime()
                colored_message = (f"战斗完成,单场用时\033[1;92m『{formatted_time}』\033[0m")
                log.info(colored_message)
                match_details = f"匹配度: {result['max_val']:.2f} ({points[0]}, {points[1]})"
                log.info(match_details)

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
            if key == "f" or key == "space" or key == "r": 
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
            elif key == "esc":
                if value == 1:  # 执行一次esc键的按下和释放操作
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0) 
                    time.sleep(0.1)  
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
        screenshot = cv.cvtColor(self.take_screenshot()[0], cv.COLOR_BGR2GRAY)

        if cv.mean(screenshot)[0] > threshold:  # 如果平均像素值大于阈值
            image_folder = "./picture/"
            finish_fighting_images = [f for f in os.listdir(image_folder) if f.startswith("finish_fighting")]
            attempts = 0
            max_attempts_ff1 = 3
            while attempts < max_attempts_ff1:
                for image_name in finish_fighting_images:
                    target = cv.imread(os.path.join(image_folder, image_name))
                    result = self.scan_screenshot(target)
                    if result and result["max_val"] > 0.9:
                        return False  # 如果匹配度大于0.9，表示不是黑屏，返回False
                attempts += 1
                time.sleep(2)  # 等待2秒再尝试匹配

        return True  # 如果未匹配到指定的图像，返回True
