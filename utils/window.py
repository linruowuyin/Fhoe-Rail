import os
import random
import time

import pyautogui
import win32api
import win32con
import win32gui

from utils.exceptions import CustomException
from utils.log import log
from utils.singleton import SingletonMeta


class Window(metaclass=SingletonMeta):

    def __init__(self, max_retries=10):
        """
        初始化窗口对象，确保 hwnd 可用
        :param max_retries: 最大重试次数
        """
        self.title = None
        self.hwnd = None
        self.client = None
        self.winrect = ()  # 截图窗口范围

        # 初始化时先找到窗口或者启动lnk文件
        self.switch_window()

        # 强制初始化 hwnd
        for _ in range(max_retries):
            try:
                self.title = self.get_hwnd_title()
                log.info(f"窗口标题: {self.title}")
                self.hwnd = self.get_hwnd()
                log.info(f"窗口句柄: {self.hwnd}")
                if self.hwnd:
                    self.client = self._get_client(self.title)
                    log.info(f"客户端类型: {self.client}")
                    break
            except Exception as e:
                log.info(f"初始化失败，重试中... 错误: {e}")
                time.sleep(2)
        else:
            raise CustomException("无法初始化窗口对象，已达到最大重试次数")

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
        return not style & win32con.WS_OVERLAPPEDWINDOW

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

        raise CustomException("无法找到窗口，已达到最大重试次数")

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

    def check_window_visibility(self, depth=0) -> bool:
        """
        检查窗口是否可见
        """
        if not self.hwnd:
            self.get_hwnd()
        if self.hwnd and win32gui.IsWindowVisible(self.hwnd):
            return True
        if depth >= 3:
            log.info("尝试次数过多，程序退出。")
            return False
        cnt = 1
        while cnt < 3:
            time.sleep(1)
            log.info(f'窗口不可见或窗口句柄无效，窗口句柄为：{self.hwnd}，尝试重新查找窗口 {cnt} 次')
            self.get_hwnd()
            if self.hwnd:
                self.switch_window()
                return True
            else:
                cnt += 1
        # 等待用户输入回车键继续
        input("未找到星铁窗口，请打开星铁，进入游戏界面后，输入回车键继续")
        time.sleep(1)
        return self.check_window_visibility(depth + 1)

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
        monitor_handle = win32api.MonitorFromPoint(
            (window_center_x, window_center_y), win32con.MONITOR_DEFAULTTONEAREST)
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

        # log.info(f"窗口矩形区域: {rect}")

        # 返回普通窗口的矩形区域
        return rect

    def switch_window(self):
        # 测试用
        # all_titles = [win.title for win in pyautogui.getAllWindows()]
        # print("当前所有窗口标题:", [t for t in all_titles if t.strip()])
        lnk_started = False  # 添加一个标志，用于记录lnk文件是否已经启动

        while True:
            if not lnk_started:  # 如果lnk文件未启动，继续查找窗口
                def is_target_window(w):
                    """智能窗口匹配规则"""
                    # 精确匹配
                    if w.title == '崩坏：星穹铁道':
                        return True
                    # 模糊匹配网页
                    if '云星穹铁道' in w.title.replace(' ', '').replace('·', ''):
                        return True
                    return False

                all_windows = pyautogui.getAllWindows()
                for w in all_windows:
                    if is_target_window(w):
                        log.info(f'激活窗口: {w.title}')
                        # client.Dispatch("WScript.Shell").SendKeys('%')  # 确保窗口可激活
                        try:
                            w.restore()  # 防止最小化状态
                            # w.maximize() # 最大化窗口确保可见
                            w.activate()
                            # 获取窗口的位置和尺寸
                            left, top, width, height = w.left, w.top, w.width, w.height
                            log.info(
                                f'窗口位置和尺寸: {left}, {top}, {width}, {height}')

                            # 计算窗口中心坐标
                            center_x = left + width // 2
                            center_y = top + height // 2

                            # 移动鼠标到窗口中心
                            log.info(f'移动鼠标到窗口中心: {center_x}, {center_y}')
                            pyautogui.moveTo(center_x, center_y)
                            return
                        except Exception as e:
                            log.info(f'窗口激活失败: {e}')
                            continue
                log.debug(f'未找到目标窗口，已扫描{len(all_windows)}个窗口')
                log.debug('当前存在的窗口标题：')
                for w in pyautogui.getAllWindows():
                    if w.title.strip():
                        log.debug(f' - "{w.title}"')

            # 尝试查找并启动lnk文件
            lnk_files = self.find_lnk_files("./map")  # 指定lnk文件所在的目录
            if len(lnk_files) == 1 and not lnk_started:
                self.start_lnk_file(lnk_files[0])
                print("程序启动成功！")
                lnk_started = True  # 设置标志为True
                time.sleep(25)  # 等待25秒

                end_time = time.time() + 30  # 执行点击操作的总时间为30秒
                last_5_seconds = end_time - 5  # 最后5秒

                # 点击位置
                points = (50, 62)
                left, top, right, bottom = self.get_rect()
                x, y = int(left + (right - left) / 100 *
                           points[0]), int(top + (bottom - top) / 100 * points[1])
                log.info((x, y))

                while time.time() < end_time:
                    if time.time() >= last_5_seconds:
                        # 在最后5秒内至少点击5次
                        for _ in range(5):
                            # x, y = (1167, 732)  # 修改点击坐标为(1167, 732)
                            pyautogui.click(x, y)
                            time.sleep(random.uniform(0.1, 5))  # 随机点击频率
                    else:
                        # x, y = (1167, 732)  # 修改点击坐标为(1167, 732)
                        pyautogui.click(x, y)
                        time.sleep(random.uniform(0.1, 5))  # 随机点击频率

            if lnk_started:
                # 如果lnk文件已经启动成功，不再等待用户按下回车键，直接退出
                return

            # 等待用户按下回车键后继续
            input("按下回车键继续查找窗口...")

    def find_lnk_files(self, folder_path):
        lnk_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.lnk'):
                    lnk_files.append(os.path.join(root, file))
        return lnk_files

    def start_lnk_file(self, lnk_path):
        os.system(f'start "" "{lnk_path}"')
