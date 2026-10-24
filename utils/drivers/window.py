import os
import random
import time

import pyautogui
import win32api
import win32con
import win32gui
import win32process

from utils.core.exceptions import CustomException
from utils.core.log import log
from utils.core.singleton import SingletonMeta

#: 崩铁客户端进程的可执行文件名（小写比较）。云游戏是浏览器进程，认不出来，
#: 所以 `find_window_hwnd` 在它之后还留了按标题找的那条兜底。
#: 这个名字取自上游同源项目 March7thAssistant 的 `game_path` 配置（`StarRail.exe`）。
GAME_PROCESS_NAMES = ("starrail.exe",)

#: `OpenProcess` 的权限位：Vista 起拿进程映像路径只要这个，不必更高权限
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: `NtQuerySystemInformation` 的信息类：系统进程信息（含每个进程的会话号）
SYSTEM_PROCESS_INFORMATION_CLASS = 57

#: `NtQuerySystemInformation` 的「缓冲区不够」返回码
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004


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
    def find_window_hwnd(process_names=GAME_PROCESS_NAMES):
        """找一个游戏窗口的句柄，找不到返回 None。

        **先按进程可执行文件名找，再退回按标题找**：标题会随语言 / 版本 / 窗口状态变
        （`is_target_window` 里那几个是硬编码的中文串），进程名不会 —— 用
        `StarRail.exe` 认才是稳的。云游戏是浏览器进程，进程名认不出来，靠标题那条兜。

        只做查找：不激活窗口、不启动游戏、不动鼠标。这正是它与构造 `Window()` 的区别
        —— 那条路走 `switch_window()`，会把鼠标挪到窗口中心，找不到还会启动游戏连点
        30 秒。
        """
        hwnd = Window.find_window_hwnd_by_process(process_names)
        if hwnd:
            return hwnd
        for window in pyautogui.getAllWindows():
            if Window.is_target_window(window):
                return window._hWnd
        return None

    @staticmethod
    def find_window_hwnd_by_process(names=GAME_PROCESS_NAMES):
        """按进程可执行文件名（不区分大小写）找可见窗口，找不到返回 None。"""
        wanted = {name.lower() for name in names}
        found = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                # 返回的是 (线程号, 进程号) —— 进程号在 [1]，[0] 是线程号。
                # 同一进程的窗口线程号各不相同，取错了就会拿线程号去 OpenProcess。
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                path = Window._process_image_name(pid)
                if path and os.path.basename(path).lower() in wanted:
                    found.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return found[0] if found else None

    @staticmethod
    def _process_image_name(pid):
        """进程可执行文件的完整路径；拿不到返回 None。

        用 `QueryFullProcessImageNameW` 而不是 `GetModuleFileNameEx`：前者只要
        PROCESS_QUERY_LIMITED_INFORMATION，对方进程权限更高时也拿得到。
        """
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            ):
                return None
            return buffer.value
        finally:
            kernel32.CloseHandle(handle)

    @classmethod
    def attach(cls, hwnd):
        """给一个**已经存在**的窗口句柄造一个 `Window`，跳过 `__init__`。

        探针要的就是「挂在游戏窗口上抓一帧」，而 `Window()` 的构造会激活窗口、必要时
        还会启动游戏并连点。这条路径只登记 hwnd / 标题 / 客户端类型，别的什么都不做。
        """
        window = object.__new__(cls)
        window.hwnd = hwnd
        window.title = win32gui.GetWindowText(hwnd) or ""
        # 空标题不能让 `_get_client` 判成"云游戏" —— 那条路会去取整个显示器的矩形
        window.client = cls._get_client(window.title) if window.title else "客户端"
        window.winrect = ()
        return window

    @staticmethod
    def current_session_id():
        """本进程所在的 Windows 会话号。"""
        import ctypes
        from ctypes import wintypes

        session = wintypes.DWORD()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
        return session.value

    @staticmethod
    def process_sessions(process_names=GAME_PROCESS_NAMES):
        """系统里名字匹配的进程，返回 `[(pid, 会话号)]`（不区分大小写）。

        走 `NtQuerySystemInformation` —— 它把**会话号直接放在结构体里**，不需要打开对方
        进程、也不需要管理员权限，所以游戏跑在别的 Windows 会话 / 别的用户下时照样看得见。
        （先试过 `ProcessIdToSessionId`，它要求对方进程的 QUERY_INFORMATION 权限，跨用户
        时直接失败并留下一个 0 —— 会报出「会话 0」这种假答案。）
        """
        import ctypes
        from ctypes import wintypes

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [
                ("Length", wintypes.USHORT),
                ("MaximumLength", wintypes.USHORT),
                ("Buffer", ctypes.c_void_p),
            ]

        class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
            """只声明到 `SessionId` 为止 —— 它后面的字段随 Windows 版本变。"""

            _fields_ = [
                ("NextEntryOffset", wintypes.ULONG),
                ("NumberOfThreads", wintypes.ULONG),
                ("WorkingSetPrivateSize", ctypes.c_longlong),
                ("HardFaultCount", wintypes.ULONG),
                ("NumberOfThreadsHighWatermark", wintypes.ULONG),
                ("CycleTime", ctypes.c_ulonglong),
                ("CreateTime", ctypes.c_longlong),
                ("UserTime", ctypes.c_longlong),
                ("KernelTime", ctypes.c_longlong),
                ("ImageName", UNICODE_STRING),
                ("BasePriority", ctypes.c_long),
                ("UniqueProcessId", ctypes.c_void_p),
                ("InheritedFromUniqueProcessId", ctypes.c_void_p),
                ("HandleCount", wintypes.ULONG),
                ("SessionId", wintypes.ULONG),
            ]

        wanted = {name.lower() for name in process_names}
        ntdll = ctypes.windll.ntdll
        ntdll.NtQuerySystemInformation.argtypes = [
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
        ]
        ntdll.NtQuerySystemInformation.restype = ctypes.c_long

        # 这台机器上进程表要 ~2.4 MB，起步给 4 MB 免得白跑一轮
        size = 1 << 22
        while True:
            buffer = ctypes.create_string_buffer(size)
            needed = wintypes.ULONG(0)
            status = ntdll.NtQuerySystemInformation(
                SYSTEM_PROCESS_INFORMATION_CLASS,
                buffer,
                size,
                ctypes.byref(needed),
            )
            # NTSTATUS 从 c_long 回来是**负数**（0xC0000004 → -1073741820），
            # 直接跟无符号常数比会永远不相等 —— 先掩成 32 位无符号再比。
            if (status & 0xFFFFFFFF) == STATUS_INFO_LENGTH_MISMATCH:
                size = max(needed.value, size * 2)
                if size > (1 << 28):
                    return []
                continue
            if status != 0:
                return []
            break

        rows = []
        offset = 0
        while True:
            entry = SYSTEM_PROCESS_INFORMATION.from_buffer(buffer, offset)
            if entry.ImageName.Buffer:
                name = ctypes.wstring_at(
                    entry.ImageName.Buffer, entry.ImageName.Length // 2
                )
                if name.lower() in wanted:
                    rows.append((int(entry.UniqueProcessId or 0), entry.SessionId))
            if not entry.NextEntryOffset:
                return rows
            offset += entry.NextEntryOffset

    @classmethod
    def describe_missing_window(cls, process_names=GAME_PROCESS_NAMES):
        """找不到游戏窗口时，给一句能指导下一步的话。

        「明明开着游戏却说没检测到窗口」最容易被误判成最小化，其实多用户 / RDP 多开
        更常见：Windows 的会话隔离让 `EnumWindows` 只看得见**本会话**的窗口，游戏开在
        别的会话里时一个窗口都找不到 —— 但进程快照看得见它。把这一层说破，省得往
        最小化那条死路上查。
        """
        ours = cls.current_session_id()
        sessions = cls.process_sessions(process_names)
        if not sessions:
            return "没检测到游戏窗口 —— 先把游戏打开再跑本工具。"
        where = "、".join(f"pid {pid}（会话 {session}）" for pid, session in sessions)
        if all(session != ours for _, session in sessions):
            return (
                f"游戏进程在{where}里跑，而本进程在会话 {ours}。"
                "Windows 的会话隔离让跨会话拿不到窗口（EnumWindows 只看得到本会话），"
                "所以抓不到游戏画面 —— 请到游戏所在的那个会话里启动本工具"
                "（多用户 / RDP 多开的情况下，光把游戏挪到前台没用）。"
            )
        return f"游戏进程在{where}，但拿不到它的窗口 —— 可能被最小化了。"

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

    @staticmethod
    def _switch_to_this_window(hwnd):
        """任务栏点窗口时用的那条 API，比 SetForegroundWindow 更容易绕过前台锁。"""
        import ctypes

        try:
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            return True
        except Exception:
            return False

    @staticmethod
    def _force_foreground(hwnd):
        """强制将窗口切到前台（破解 Windows 前台锁限制）。
        SetForegroundWindow 在后台进程调用时常失败，
        AttachThreadInput 关联前台线程后可成功激活。
        """
        import ctypes
        import time as _t

        # 检查窗口是否最小化，如果是则恢复
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # 合成一次 ALT：让本进程被视为「刚接收过输入」，绕过后台进程的前台锁。
        # WebUI 从浏览器点启动时，fhoe 是后台进程的子进程，没有这条经常激活失败。
        try:
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(
                win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
            )
        except Exception:
            pass

        for attempt in range(5):
            used_method = "none"
            try:
                # 获取当前前台窗口和线程
                fg = win32gui.GetForegroundWindow()
                tid_fg = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
                tid_self = win32api.GetCurrentThreadId()

                # 关联线程输入队列
                attached = False
                if tid_fg != tid_self and tid_fg:
                    try:
                        attached = win32api.AttachThreadInput(tid_self, tid_fg, True)
                    except Exception:
                        pass

                try:
                    # 方法1: SetForegroundWindow
                    win32gui.SetForegroundWindow(hwnd)
                    used_method = "SetForegroundWindow"
                except Exception:
                    pass

                try:
                    # 方法2: BringWindowToTop
                    win32gui.BringWindowToTop(hwnd)
                    if used_method == "none":
                        used_method = "BringWindowToTop"
                except Exception:
                    pass

                try:
                    # 方法3: SetWindowPos 置顶
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    )
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    )
                    if used_method == "none":
                        used_method = "SetWindowPos"
                except Exception:
                    pass

                try:
                    # 方法4: ctypes 直接调用 User32
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    if used_method == "none":
                        used_method = "ctypes.User32"
                except Exception:
                    pass

                try:
                    # 方法5: SwitchToThisWindow（任务栏切换用的是这条）
                    if Window._switch_to_this_window(hwnd):
                        if used_method == "none":
                            used_method = "SwitchToThisWindow"
                except Exception:
                    pass

                # 解除线程输入队列关联
                if attached and tid_fg != tid_self and tid_fg:
                    try:
                        win32api.AttachThreadInput(tid_self, tid_fg, False)
                    except Exception:
                        pass

                # 确认是否成功
                _t.sleep(0.1)
                if win32gui.GetForegroundWindow() == hwnd:
                    log.info(f"强激活成功，使用方法: {used_method}")
                    return True
            except Exception as e:
                log.debug(f"强激活尝试 {attempt + 1} 失败: {e}")
            _t.sleep(0.3)
        try:
            foreground = win32gui.GetForegroundWindow()
            foreground_title = win32gui.GetWindowText(foreground)
        except Exception:
            foreground_title = "<读不到>"
        log.warning(
            f"强激活窗口失败(hwnd={hwnd})，当前前台窗口是 {foreground_title!r}。"
            "WebUI 启动时这通常意味着 WebUI 不是管理员，或前台锁没放开"
        )
        return False

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

    @staticmethod
    def _get_client(title: str) -> str:
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
        # 修复：WebUI 无 stdin 时 input() 会 EOFError 崩溃，改为轮询等待
        log.info("未找到星铁窗口，请打开星铁并进入游戏界面，5 秒后自动重试（最长 60 秒）...")
        for _ in range(12):
            time.sleep(5)
            self.get_hwnd()
            if self.hwnd:
                self.switch_window()
                return True
        log.info("等待窗口超时（60 秒），返回失败")
        return False

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
        wait_start = time.time()  # 等待窗口的总超时（避免无 stdin 环境下 input 崩溃/无限等待）

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
                candidates = [w for w in all_windows if is_target_window(w)]
                for w in candidates:
                    log.info(f'激活窗口: {w.title}')
                    try:
                        w.restore()  # 防止最小化状态
                        # 强激活：Windows 前台锁常导致 SetForegroundWindow 失败，
                        # 使用 AttachThreadInput 技巧 + 重试，确保窗口能切到前台
                        if not self._force_foreground(w._hWnd):
                            log.warning(f'窗口强激活失败，尝试下一个: {w.title}')
                            continue
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
                if candidates:
                    # 找到了游戏窗口，但一个都没抢到前台：继续跑只会把键鼠送进
                    # 浏览器/控制台，必须明确失败，让用户手动点一下或提权重试。
                    raise CustomException(
                        "检测到游戏窗口，但无法切到前台。请手动点一下游戏窗口后重试；"
                        "WebUI 请用 Start-WebUI.bat（管理员权限）启动，"
                        "后台启动的子进程常被 Windows 前台锁拦住。"
                    )
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

            # 找不到窗口：轮询等待代替 input 阻塞。
            # 修复：WebUI 启动时 stdin 为空管道，input() 会抛 EOFError 崩溃；
            # 且后台调用场景不应无限等待用户按键。
            # 超时给到 300 秒，覆盖游戏/云游戏慢启动场景（CLI 与 WebUI 通用）。
            if time.time() - wait_start > 300:
                raise CustomException(
                    "无法找到游戏窗口（已等待 300 秒），请先打开游戏再运行锄地")
            log.info("未找到游戏窗口，3 秒后自动重试（最长等待 300 秒）...")
            time.sleep(3)

    def find_lnk_files(self, folder_path):
        lnk_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.lnk'):
                    lnk_files.append(os.path.join(root, file))
        return lnk_files

    def start_lnk_file(self, lnk_path):
        os.system(f'start "" "{lnk_path}"')
