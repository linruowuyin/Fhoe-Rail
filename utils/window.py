import time
import win32gui
import win32con
import win32api
import pyautogui
from .log import log
from .switch_window import switch_window


class Window:
    def __init__(self, max_retries=3):
        """
        初始化窗口对象，确保 hwnd 可用
        :param max_retries: 最大重试次数
        """
        self.title = None
        self.hwnd = None
        self.client = None
        self.winrect = ()  # 截图窗口范围

        # 强制初始化 hwnd
        for _ in range(max_retries):
            try:
                self.title = self.get_hwnd_title()
                self.hwnd = self.get_hwnd()
                if self.hwnd:
                    self.client = self._get_client(self.title)
                    break
            except Exception as e:
                log.info(f"初始化失败，重试中... 错误: {e}")
                time.sleep(2)
        else:
            raise Exception("无法初始化窗口对象，已达到最大重试次数")

    @staticmethod
    def is_target_window(window):
        """窗口匹配规则"""
        title = window.title.replace(' ', '').replace('·', '')
        # 精确匹配桌
        if title == '崩坏：星穹铁道':
            return True
        # 模糊匹配网页版
        if '云星穹铁道' in title:
            return True
        return False

    @staticmethod
    def get_hwnd_by_title(title):
        """根据窗口标题获取窗口句柄"""
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
                hwnds.append(hwnd)
            return True

        hwnds = []
        win32gui.EnumWindows(callback, hwnds)
        return hwnds[0] if hwnds else None

    @staticmethod
    def is_fullscreen(hwnd):
        """检测窗口是否处于全屏状态"""
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        return not (style & win32con.WS_OVERLAPPEDWINDOW)

    def get_hwnd_title(self, hwnd_max_retries=10) -> str:
        """获取窗口标题"""
        all_windows = pyautogui.getAllWindows()
        for _ in range(hwnd_max_retries):
            try:
                for w in all_windows:
                    if self.is_target_window(w):
                        log.info(f'找到目标窗口: {w.title}')
                        return w.title
                time.sleep(2)
            except Exception as e:
                log.info(f'查找窗口失败，{e}')
                time.sleep(2)

        raise Exception("无法找到窗口，已达到最大重试次数")

    def get_hwnd(self) -> str:
        """获取窗口句柄"""
        if self.title is None:
            self.title = self.get_hwnd_title()
        self.hwnd = self.get_hwnd_by_title(self.title)
        return self.hwnd

    def _get_client(self, title: str) -> str:
        """
        根据窗口标题获取客户端类型
        :param title: 窗口标题
        :return: 客户端类型（"客户端" 或 "云游戏"）
        """
        return "客户端" if "崩坏：星穹铁道" in title else "云游戏"

    def _check_window_visibility(self, depth=0):
        """
        检查窗口是否可见
        """
        if not self.hwnd:
            self.get_hwnd()
        if self.hwnd and win32gui.IsWindowVisible(self.hwnd):
            return True
        else:
            if depth >= 3:
                log.info("尝试次数过多，程序退出。")
                return False
            cnt = 1
            while cnt < 3:
                time.sleep(1)
                log.info(f'窗口不可见或窗口句柄无效，窗口句柄为：{self.hwnd}，尝试重新查找窗口 {cnt} 次')
                self.get_hwnd()
                if self.hwnd:
                    switch_window()
                    return True
                else:
                    cnt += 1
            else:
                # 等待用户输入回车键继续
                input("未找到星铁窗口，请打开星铁，进入游戏界面后，输入回车键继续")
                time.sleep(1)
                return self._check_window_visibility(depth + 1)

    def get_rect(self, hwnd=None):
        """
        获取窗口截图的范围
        """
        if not hwnd:
            if self.hwnd is None:
                self.get_hwnd()
            hwnd = self.hwnd
        
        if self.client == "云游戏":
            # 全屏模式特殊处理
            self.winrect = self._get_fullscreen_rect(hwnd)
        else:
            self.winrect = self._get_window_rect(hwnd)

        return self.winrect

    def _get_fullscreen_rect(self, hwnd):
        """获取全屏模式的窗口矩形区域"""
        # 直接获取显示器分辨率
        # 获取窗口的位置
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        window_center_x = (left + right) // 2
        window_center_y = (top + bottom) // 2
        
        # 获取窗口所在的显示器
        monitor_handle = win32api.MonitorFromPoint((window_center_x, window_center_y), win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor_handle)
        
        # 获取显示器的全屏大小
        monitor_rect = monitor_info["Monitor"]
        # log.info(f"窗口所在显示器的全屏大小: {monitor_rect}")
        # screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        # screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        # log.info(f"(0, 0, {screen_w}, {screen_h})")
        # return (0, 0, screen_w, screen_h)
        # 返回全屏模式的窗口矩形区域
        return monitor_rect

    def _get_window_rect(self, hwnd):
        """获取普通窗口的矩形区域"""
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (left, top))
        rect = (pt[0], pt[1], pt[0] + (right - left), pt[1] + (bottom - top))
        log.info(f"窗口矩形区域: {rect}")
        
        # 返回普通窗口的矩形区域
        return rect