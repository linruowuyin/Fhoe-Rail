import ctypes
import time

import pyautogui
import win32api
import win32con

from utils.config.config import ConfigurationManager
from utils.core.log import log
from utils.core.singleton import SingletonMeta
from utils.drivers.window import Window


class MouseEvent(metaclass=SingletonMeta):
    def __init__(self):
        self.window = Window()
        self.cfg = ConfigurationManager()

        # 上一次 click_target 超时时，调用方是否允许重试整张地图。
        # 由 vision/matcher.click_target 写入、由 flows/map_operations 读取 ——
        # 读的一方持有 self.mouse_event，所以标志放在这里（见 CLAUDE.md R13）。
        self.last_search_allow_retry = False
        self.multi_num = 1
        try:
            self.scale = ctypes.windll.user32.GetDpiForWindow(self.window.hwnd) / 96.0
            log.debug(f"scale:{self.scale}")
        except Exception:
            self.scale = 1.0
            log.info(f"DPI获取失败，使用默认比例scale:{self.scale}")

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

    def mouse_drag(self, x, y, end_x, end_y, press_time: float = 0):
        """
        说明：
            在窗口内执行鼠标拖拽操作

        参数：
            :param x: 起始点x坐标(相对于窗口)
            :param y: 起始点y坐标(相对于窗口)
            :param end_x: 终点x坐标(相对于窗口)
            :param end_y: 终点y坐标(相对于窗口)
            :param press_time: 鼠标拖动到终点后的停留时间(秒)，默认为0

        返回：
            None

        示例：
            mouse_drag(100, 100, 300, 300)  # 从(100,100)拖拽到(300,300)
            mouse_drag(100, 100, 300, 300, 0.5)  # 拖拽到终点后停留0.5秒
        """
        left, top, right, bottom = self.window.get_rect()
        pyautogui.moveTo(left + x, top + y)
        pyautogui.mouseDown()
        pyautogui.moveTo(left + end_x, top + end_y, duration=0.2)
        if press_time:
            time.sleep(press_time)
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
        try:
            self.mouse_press(x, y, delay)
        finally:
            # 无论点击过程是否异常，都必须释放 ALT，避免键盘卡住
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
            x, y = (
                int(left + (right - left) / 100 * points[0]),
                int(top + (bottom - top) / 100 * points[1]),
            )
            log.info((x, y))
            self.mouse_press_alt(x, y)

    def scroll(self, clicks: float):
        """滚轮。正数为向上。"""
        pyautogui.scroll(clicks)

    def click_at_cursor(self, clicks=1, delay=0.05):
        """在鼠标当前所在位置点击。

        调用方不该自己去拿光标坐标（那是 Win32 的细节），所以把
        GetCursorPos 收在这一层。
        """
        self.click(win32api.GetCursorPos(), clicks=clicks, delay=delay)

    def click_center(self):
        """
        点击游戏窗口中心位置
        """
        if self.window.check_window_visibility():
            left, top, right, bottom = self.window.get_rect()
            x, y = int((left + right) / 2), int((top + bottom) / 2)
            self.mouse_press(x, y)

    def click_target_with_alt(self, matcher, target_path, threshold, flag=True, clicks=1):
        """
        说明：
            按下alt，点击指定图片，释放alt

        ALT 的按下/释放属于本层（输入设备），「找到图就点」属于 vision 层，
        所以搜索器由调用方传入而不是自己持有 —— 否则 drivers 就要反向依赖 vision。

        参数：
            :param matcher: 提供 click_target 的识图对象（通常是 Img 门面）
            :param target_path: 图片地址
            :param threshold: 匹配阈值
            :param flag: True为必须找到图片
            :param clicks: 连续点击次数
        """
        initial_state = win32api.GetKeyState(win32con.VK_MENU)
        log.debug(f"ALT初始状态: {initial_state}")

        try:
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.15)

            matcher.click_target(target_path, threshold, flag, clicks=clicks)

        except Exception as e:
            if flag:
                raise RuntimeError(f"操作执行失败: {str(e)}") from e
        finally:
            current_state = win32api.GetKeyState(win32con.VK_MENU)
            log.debug(f"释放前状态: {current_state}, 正在执行强制释放")
            if win32api.GetKeyState(win32con.VK_MENU) != initial_state:
                win32api.keybd_event(
                    win32con.VK_MENU,
                    0,
                    win32con.KEYEVENTF_KEYUP | win32con.KEYEVENTF_EXTENDEDKEY,
                    0,
                )
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
