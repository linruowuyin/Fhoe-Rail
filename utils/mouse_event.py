import ctypes
import time

import cv2
import pyautogui
import win32api
import win32con

from utils.config.config import ConfigurationManager
from utils.img import Img
from utils.log import log
from utils.singleton import SingletonMeta
from utils.window import Window


class MouseEvent(metaclass=SingletonMeta):
    def __init__(self):
        self.img = Img()
        self.window = Window()
        self.cfg = ConfigurationManager()

        self.img_search_val_dict = {}  # 图片匹配值
        self.multi_num = 1
        try:
            self.scale = ctypes.windll.user32.GetDpiForWindow(self.window.hwnd) / 96.0
            log.debug(f"scale:{self.scale}")
        except Exception:
            self.scale = 1.0
            log.info(f'DPI获取失败，使用默认比例scale:{self.scale}')

    def click(self, points, slot=0.0, clicks=1, delay=0.05):
        """
        说明：
            点击指定屏幕坐标
        参数：
            :param points: 坐标
            :param slot: 坐标来源图片匹配值
            :param clicks: 连续点击次数
        """
        x, y = int(points[0]), int(points[1])
        if not slot:
            log.info(f"点击坐标{(x, y)}")
        else:
            log.info(f"点击坐标{(x, y)}，坐标来源图片匹配度{slot:.3f}")
        if clicks > 1:
            log.info(f"将点击 {clicks} 次")
        for _ in range(clicks):
            self.mouse_press(x, y, delay)

    def mouse_press(self, x, y, delay: float = 0.05):
        """
        说明：
            鼠标点击
        参数：
            :param x: 起始点相对坐标x
            :param y: 起始点相对坐标y
            :param delay: 鼠标点击与抬起之间的延迟（秒）
        """
        win32api.SetCursorPos((x, y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(delay)
        time.sleep(0.01)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def mouse_drag(self, x, y, end_x, end_y):
        """
        说明：
            鼠标按下后拖动
        """
        left, top, right, bottom = self.window.get_rect()
        pyautogui.moveTo(left + x, top + y)
        pyautogui.mouseDown()
        pyautogui.moveTo(left + end_x, top + end_y, duration=0.2)
        pyautogui.mouseUp()
        time.sleep(1)

    def mouse_press_alt(self, x, y, delay: float = 0.4):
        """
        说明：
            按下alt同时鼠标点击指定坐标
        参数：
            :param x:相对坐标x
            :param y:相对坐标y
        """
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        self.mouse_press(x, y, delay)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    def relative_click(self, points):
        """
        说明：
            点击相对坐标
        参数：
            :param points: 百分比坐标，100为100%
        """
        if self.window.check_window_visibility():
            left, top, right, bottom = self.window.get_rect()
            # real_width = self.cfg.config_file["real_width"]  # 暂时没用
            # real_height = self.cfg.config_file["real_height"]  # 暂时没用
            x, y = int(left + (right - left) / 100 *
                       points[0]), int(top + (bottom - top) / 100 * points[1])
            log.info((x, y))
            self.mouse_press_alt(x, y)

    def click_center(self):
        """
        点击游戏窗口中心位置
        """
        if self.window.check_window_visibility():
            left, top, right, bottom = self.window.get_rect()
            x, y = int((left + right) / 2), int((top + bottom) / 2)
            self.mouse_press(x, y)

    def click_target_above_threshold(self, target, threshold, offset, clicks=1, delay=0.05):
        """
        尝试点击匹配度大于阈值的目标图像。
        参数:
            :param target: 目标图像
            :param threshold: 匹配阈值
            :param offset: 左、上、右、下，正值为向右或向下偏移
            :param clicks: 连续点击次数
        返回:
            :return: 是否点击成功
        """
        result = self.img.scan_screenshot(target, offset)
        if result["max_val"] > threshold:
            points = self.img.img_center_point(result, target.shape)
            self.click(points, result['max_val'], clicks, delay)
            return True, result['max_val']
        return False, result['max_val']

    def click_target(self, target_path, threshold, flag=True, timeout=30.0, offset=(0, 0, 0, 0), retry_in_map: bool = True, clicks=1, delay=0.05):
        """
        说明：
            点击指定图片
        参数：
            :param target_path:图片地址
            :param threshold:匹配阈值
            :param flag:True为一定要找到图片
            :param timeout: 最大搜索时间（秒）
            :param offset: 左、上、右、下，正值为向右或向下偏移
            :param retry_in_map: 是否允许地图中重试查找
            :param clicks: 连续点击次数
        返回：
            :return 是否点击成功
        """
        # 定义目标图像与颜色反转后的图像
        original_target = cv2.imread(target_path)
        inverted_target = cv2.bitwise_not(original_target)
        start_time = time.time()
        assigned = False

        while time.time() - start_time < timeout:
            click_it, img_search_val = self.click_target_above_threshold(
                original_target, threshold, offset, clicks, delay)
            if click_it:
                return True
            if time.time() - start_time > 1:  # 如果超过1秒，同时匹配原图像和颜色反转后的图像
                click_it, _ = self.click_target_above_threshold(
                    inverted_target, threshold, offset, clicks, delay)
                if click_it:
                    log.info("阴阳变转")
                    return True

            if not assigned:
                if target_path in self.img_search_val_dict:
                    if self.img_search_val_dict[target_path] > img_search_val and img_search_val < 0.99:
                        self.img_search_val_dict[target_path] = img_search_val
                        assigned = True
                else:
                    if img_search_val < 0.99:
                        self.img_search_val_dict[target_path] = img_search_val
                        assigned = True

            if not flag:  # 是否一定要找到
                return False
            time.sleep(0.5)  # 添加短暂延迟避免性能消耗

        log.info(
            f"查找图片超时 {target_path} ，最相似图片匹配值 {img_search_val}，所需匹配值 {threshold}")
        self.img.search_img_allow_retry = retry_in_map
        return False

    def click_target_with_alt(self, target_path, threshold, flag=True, clicks=1):
        """
        说明：
            按下alt，点击指定图片，释放alt
        参数：
            :param target_path: 图片地址
            :param threshold: 匹配阈值
            :param flag: True为必须找到图片
            :param clicks: 连续点击次数
        改进：
            1. 使用成对的按下/释放标志
            2. 增加异常处理确保ALT释放
            3. 优化延时逻辑
            4. 添加键盘状态恢复机制
        """
        initial_state = win32api.GetKeyState(win32con.VK_MENU)
        log.debug(f"ALT初始状态: {initial_state}")

        try:
            win32api.keybd_event(win32con.VK_MENU, 0,
                                 win32con.KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.15)

            self.click_target(target_path, threshold, flag, clicks=clicks)

        except Exception as e:
            if flag:
                raise RuntimeError(f"操作执行失败: {str(e)}") from e
        finally:
            current_state = win32api.GetKeyState(win32con.VK_MENU)
            log.debug(f"释放前状态: {current_state}, 正在执行强制释放")
            if win32api.GetKeyState(win32con.VK_MENU) != initial_state:
                win32api.keybd_event(
                    win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP | win32con.KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.1)

    def mouse_move(self, x, fine=1, align=False):
        """
        说明：
            视角转动x度
        参数：
            :param x: 转动角度
            :param fine: 精细度
            :param align: 是否对齐
        """
        if x > 30 // fine:
            y = 30 // fine
        elif x < -30 // fine:
            y = -30 // fine
        else:
            y = x
        if align:
            dx = int(16.5 * y * 1 * self.scale)
            log.debug(f"dx1:{dx}")
        else:
            self.multi_num = self.get_multi_num()
            dx = int(16.5 * y * self.multi_num * self.scale)
            log.debug(f"dx2:{dx}")
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, 0)  # 进行视角移动
        time.sleep(0.2 * fine)
        if x != y:
            self.mouse_move(x - y, fine, align)

    def get_multi_num(self) -> float:
        """获取视角旋转偏移参数"""
        self.multi_num = float(self.cfg.config_file.get("angle", 1))
        return self.multi_num
