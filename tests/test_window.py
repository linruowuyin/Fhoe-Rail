"""utils/drivers/window.py —— 窗口查找、标题匹配、客户区/全屏矩形计算。"""

import os
import sys
import time

import pyautogui
import pytest
import win32api
import win32con
import win32gui
import win32process

import utils.drivers.window as window_module
from utils.core.exceptions import CustomException
from utils.drivers.window import Window


class FakeWindowHandle:
    """pyautogui 窗口对象的替身。"""

    def __init__(self, title, hwnd=4242, rect=(0, 0, 1920, 1080)):
        self.title = title
        self._hWnd = hwnd
        self.left, self.top, self.width, self.height = rect

    def restore(self):
        return None


@pytest.fixture
def no_sleep(monkeypatch):
    """window.py 里有大量固定 sleep（重试间隔以秒计），测试里全部跳过。"""
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


class TestIsTargetWindow:
    def test_exact_client_title(self):
        assert Window.is_target_window(FakeWindowHandle("崩坏：星穹铁道")) is True

    def test_title_with_stray_spaces(self):
        assert Window.is_target_window(FakeWindowHandle("崩坏：星 穹铁道")) is True

    def test_title_with_middle_dot(self):
        assert Window.is_target_window(FakeWindowHandle("崩坏：星·穹铁道")) is True

    def test_cloud_client(self):
        assert Window.is_target_window(FakeWindowHandle("云星穹铁道")) is True

    def test_cloud_client_with_separator(self):
        assert Window.is_target_window(FakeWindowHandle("云·星穹铁道")) is True

    def test_unrelated_window(self):
        assert Window.is_target_window(FakeWindowHandle("记事本")) is False

    def test_empty_title(self):
        assert Window.is_target_window(FakeWindowHandle("")) is False


class TestFindWindowHwnd:
    """找游戏窗口 —— **先按进程名，再退回按标题**。不激活、不动鼠标、不启动游戏。

    加进程名那条的原因：`is_target_window` 里的标题是硬编码的中文串，客户端语言或
    标题格式一变就认不出来；进程名（`StarRail.exe`）不会变。
    """

    @staticmethod
    def _title_windows(monkeypatch, *titles):
        monkeypatch.setattr(
            window_module.pyautogui,
            "getAllWindows",
            lambda: [FakeWindowHandle(t) for t in titles],
        )

    @staticmethod
    def _processes(monkeypatch, mapping):
        """mapping: {hwnd: exe 完整路径}；拿 hwnd 当 pid 用。"""
        monkeypatch.setattr(window_module.win32gui, "IsWindowVisible", lambda hwnd: True)
        monkeypatch.setattr(
            window_module.win32gui,
            "EnumWindows",
            lambda callback, param: [callback(hwnd, param) for hwnd in mapping],
        )
        monkeypatch.setattr(
            window_module.win32process,
            "GetWindowThreadProcessId",
            lambda hwnd: (0, hwnd),
        )
        monkeypatch.setattr(
            Window, "_process_image_name", staticmethod(lambda pid: mapping.get(pid))
        )

    def test_finds_the_window_by_process_name(self, monkeypatch):
        """标题认不出来（换个语言就是另一个串），进程名照样认得出。"""
        self._title_windows(monkeypatch, "Honkai: Star Rail")
        self._processes(monkeypatch, {111: r"D:\MHY\Star Rail Game\StarRail.exe"})

        assert Window.find_window_hwnd() == 111

    def test_process_name_match_ignores_case(self, monkeypatch):
        self._title_windows(monkeypatch)
        self._processes(monkeypatch, {111: r"D:\sTaRrAiL.EXE"})

        assert Window.find_window_hwnd() == 111

    def test_process_name_wins_over_the_title(self, monkeypatch):
        self._title_windows(monkeypatch, "崩坏：星穹铁道")
        self._processes(monkeypatch, {111: r"D:\StarRail.exe"})

        assert Window.find_window_hwnd() == 111

    def test_falls_back_to_the_title_when_the_process_is_unknown(self, monkeypatch):
        """云游戏是浏览器进程，进程名认不出来 —— 靠标题那条兜。"""
        self._title_windows(monkeypatch, "记事本", "云星穹铁道")
        self._processes(monkeypatch, {111: r"C:\chrome.exe"})

        assert Window.find_window_hwnd() == 4242  # FakeWindowHandle 的默认 hwnd

    def test_none_when_neither_matches(self, monkeypatch):
        self._title_windows(monkeypatch, "记事本")
        self._processes(monkeypatch, {111: r"C:\notepad.exe"})

        assert Window.find_window_hwnd() is None

    def test_none_when_there_are_no_windows_at_all(self, monkeypatch):
        self._title_windows(monkeypatch)
        self._processes(monkeypatch, {})

        assert Window.find_window_hwnd() is None

    def test_does_not_move_the_mouse_or_launch_the_game(self, monkeypatch):
        """这两件事是 `switch_window()` 干的，也是这条路径存在的理由。"""
        self._title_windows(monkeypatch, "记事本")
        self._processes(monkeypatch, {})
        monkeypatch.setattr(
            window_module.pyautogui, "moveTo", lambda *a, **k: pytest.fail("不该移动鼠标")
        )
        monkeypatch.setattr(
            Window,
            "start_lnk_file",
            staticmethod(lambda *a, **k: pytest.fail("不该启动游戏")),
        )

        assert Window.find_window_hwnd() is None


class TestAttach:
    """给一个已经存在的 hwnd 造 `Window`，跳过 `__init__`。"""

    def test_registers_the_handle_without_activating_anything(self, monkeypatch):
        monkeypatch.setattr(
            window_module.win32gui, "GetWindowText", lambda hwnd: "崩坏：星穹铁道"
        )
        monkeypatch.setattr(
            Window, "switch_window", lambda self: pytest.fail("不该激活窗口")
        )

        window = Window.attach(7788)

        assert window.hwnd == 7788
        assert window.title == "崩坏：星穹铁道"
        assert window.client == "客户端"
        assert window.winrect == ()

    def test_cloud_client_is_detected_from_the_title(self, monkeypatch):
        monkeypatch.setattr(
            window_module.win32gui, "GetWindowText", lambda hwnd: "云·星穹铁道"
        )

        assert Window.attach(7788).client == "云游戏"

    def test_empty_title_defaults_to_the_local_client(self, monkeypatch):
        """空标题不能让客户端判成云游戏 —— 那条路会去取整个显示器的矩形，截图范围就歪了。"""
        monkeypatch.setattr(window_module.win32gui, "GetWindowText", lambda hwnd: "")

        assert Window.attach(7788).client == "客户端"


class TestGetHwndByTitle:
    def test_finds_first_matching_visible_window(self, monkeypatch):
        titles = {1: "别的窗口", 2: "崩坏：星穹铁道", 3: "崩坏：星穹铁道"}
        monkeypatch.setattr(win32gui, "IsWindowVisible", lambda hwnd: True)
        monkeypatch.setattr(win32gui, "GetWindowText", lambda hwnd: titles[hwnd])

        def fake_enum(callback, extra):
            for hwnd in titles:
                if not callback(hwnd, extra):
                    break

        monkeypatch.setattr(win32gui, "EnumWindows", fake_enum)
        assert Window.get_hwnd_by_title("崩坏：星穹铁道") == 2

    def test_skips_invisible_windows(self, monkeypatch):
        monkeypatch.setattr(win32gui, "IsWindowVisible", lambda hwnd: hwnd == 3)
        monkeypatch.setattr(win32gui, "GetWindowText", lambda hwnd: "崩坏：星穹铁道")

        def fake_enum(callback, extra):
            for hwnd in (1, 2, 3):
                callback(hwnd, extra)

        monkeypatch.setattr(win32gui, "EnumWindows", fake_enum)
        assert Window.get_hwnd_by_title("崩坏：星穹铁道") == 3

    def test_returns_none_when_no_match(self, monkeypatch):
        monkeypatch.setattr(win32gui, "IsWindowVisible", lambda hwnd: True)
        monkeypatch.setattr(win32gui, "GetWindowText", lambda hwnd: "记事本")
        monkeypatch.setattr(win32gui, "EnumWindows", lambda cb, extra: None)
        assert Window.get_hwnd_by_title("崩坏：星穹铁道") is None


class TestIsFullscreen:
    def test_windowed_style_is_not_fullscreen(self, monkeypatch):
        monkeypatch.setattr(
            win32gui, "GetWindowLong", lambda hwnd, index: win32con.WS_OVERLAPPEDWINDOW
        )
        assert Window.is_fullscreen(1) is False

    def test_borderless_style_is_fullscreen(self, monkeypatch):
        monkeypatch.setattr(win32gui, "GetWindowLong", lambda hwnd, index: 0)
        assert Window.is_fullscreen(1) is True


class TestGetClient:
    def test_official_client(self):
        assert Window._get_client("崩坏：星穹铁道") == "客户端"

    def test_cloud_client(self):
        assert Window._get_client("云·星穹铁道") == "云游戏"


class TestProcessSessions:
    """跨会话列出进程 —— 「明明开着游戏却说没检测到窗口」的定位手段。"""

    def test_finds_our_own_process_and_its_session(self):
        """拿自己当样本：Toolhelp32 + ProcessIdToSessionId 这条路真能列出进程。

        这条不走替身 —— 替身测不出 ctypes 那层结构体对齐、句柄类型这些坑。
        """
        ours = os.path.basename(sys.executable).lower()

        rows = Window.process_sessions((ours,))

        assert (os.getpid(), Window.current_session_id()) in rows

    def test_an_unrelated_name_yields_nothing(self):
        assert Window.process_sessions(("绝对不存在的进程名.exe",)) == []

    def test_is_case_insensitive(self):
        ours = os.path.basename(sys.executable).upper()

        assert any(pid == os.getpid() for pid, _ in Window.process_sessions((ours,)))

    def test_current_session_id_is_an_int(self):
        assert isinstance(Window.current_session_id(), int)


class TestDescribeMissingWindow:
    """找不到窗口时那句提示 —— 别让人一直往「是不是最小化了」上查。"""

    def test_says_the_game_is_in_another_session(self, monkeypatch):
        monkeypatch.setattr(Window, "current_session_id", staticmethod(lambda: 1))
        monkeypatch.setattr(
            Window, "process_sessions", staticmethod(lambda names=None: [(34148, 7)])
        )

        message = Window.describe_missing_window()

        assert "会话 7" in message and "会话 1" in message
        assert "34148" in message
        assert "会话隔离" in message

    def test_says_the_window_is_just_unreachable_in_our_session(self, monkeypatch):
        """进程就在本会话里、却拿不到窗口 —— 这才轮到「是不是最小化了」。"""
        monkeypatch.setattr(Window, "current_session_id", staticmethod(lambda: 1))
        monkeypatch.setattr(
            Window, "process_sessions", staticmethod(lambda names=None: [(34148, 1)])
        )

        message = Window.describe_missing_window()

        assert "会话 1" in message
        assert "最小化" in message

    def test_says_the_game_is_not_running_when_there_is_no_process(self, monkeypatch):
        monkeypatch.setattr(Window, "current_session_id", staticmethod(lambda: 1))
        monkeypatch.setattr(Window, "process_sessions", staticmethod(lambda names=None: []))

        assert "没检测到游戏窗口" in Window.describe_missing_window()


class TestRectCalculations:
    def test_client_rect_is_converted_to_screen_coordinates(self, monkeypatch):
        monkeypatch.setattr(win32gui, "GetClientRect", lambda hwnd: (0, 0, 1920, 1080))
        monkeypatch.setattr(win32gui, "ClientToScreen", lambda hwnd, point: (100, 200))
        win = object.__new__(Window)
        assert win._get_window_rect(1) == (100, 200, 2020, 1280)

    def test_fullscreen_rect_uses_the_containing_monitor(self, monkeypatch):
        monkeypatch.setattr(win32gui, "GetWindowRect", lambda hwnd: (0, 0, 1920, 1080))
        monkeypatch.setattr(
            win32api, "MonitorFromPoint", lambda point, flag: "MONITOR"
        )
        monkeypatch.setattr(
            win32api, "GetMonitorInfo", lambda handle: {"Monitor": (0, 0, 1920, 1080)}
        )
        win = object.__new__(Window)
        assert win._get_fullscreen_rect(1) == (0, 0, 1920, 1080)

    def test_get_rect_dispatches_on_client_type(self, monkeypatch):
        win = object.__new__(Window)
        win.hwnd = 1
        win.client = "云游戏"
        monkeypatch.setattr(Window, "_get_fullscreen_rect", lambda self, hwnd: "FULL")
        monkeypatch.setattr(Window, "_get_window_rect", lambda self, hwnd: "WINDOW")
        assert win.get_rect() == "FULL"

        win.client = "客户端"
        assert win.get_rect() == "WINDOW"


class TestCheckWindowVisibility:
    def test_true_for_visible_window(self, monkeypatch):
        monkeypatch.setattr(win32gui, "IsWindowVisible", lambda hwnd: True)
        win = object.__new__(Window)
        win.hwnd = 1
        assert win.check_window_visibility() is True

    def test_deepest_guard_gives_up(self, monkeypatch):
        """depth 已经 >= 3 时直接放弃，不再重试。"""
        monkeypatch.setattr(win32gui, "IsWindowVisible", lambda hwnd: False)
        win = object.__new__(Window)
        win.hwnd = 1
        assert win.check_window_visibility(depth=3) is False


class TestGetHwndTitle:
    def test_raises_after_exhausting_retries(self, monkeypatch, no_sleep):
        monkeypatch.setattr(pyautogui, "getAllWindows", lambda: [])
        win = object.__new__(Window)
        with pytest.raises(CustomException):
            win.get_hwnd_title(hwnd_max_retries=3)

    def test_returns_title_when_window_present(self, monkeypatch, no_sleep):
        monkeypatch.setattr(
            pyautogui, "getAllWindows", lambda: [FakeWindowHandle("崩坏：星穹铁道")]
        )
        win = object.__new__(Window)
        assert win.get_hwnd_title() == "崩坏：星穹铁道"

    @pytest.mark.xfail(
        strict=True,
        reason="all_windows 在重试循环之外只取一次，循环里反复扫描同一份快照，"
        "后来才出现的游戏窗口永远看不到",
    )
    def test_sees_window_that_appears_after_first_scan(self, monkeypatch, no_sleep):
        scans = []

        def fake_get_all_windows():
            scans.append(1)
            if len(scans) == 1:
                return []
            return [FakeWindowHandle("崩坏：星穹铁道")]

        monkeypatch.setattr(pyautogui, "getAllWindows", fake_get_all_windows)
        win = object.__new__(Window)
        assert win.get_hwnd_title(hwnd_max_retries=3) == "崩坏：星穹铁道"


class TestForceForeground:
    def _common_mocks(self, monkeypatch, foreground):
        monkeypatch.setattr(win32gui, "IsIconic", lambda hwnd: False)
        monkeypatch.setattr(win32gui, "GetForegroundWindow", lambda: foreground)
        monkeypatch.setattr(win32gui, "SetForegroundWindow", lambda hwnd: None)
        monkeypatch.setattr(win32gui, "BringWindowToTop", lambda hwnd: None)
        monkeypatch.setattr(win32gui, "SetWindowPos", lambda *a, **k: None)
        monkeypatch.setattr(win32api, "GetCurrentThreadId", lambda: 1)
        monkeypatch.setattr(win32process, "GetWindowThreadProcessId", lambda hwnd: (1, 0))
        monkeypatch.setattr(time, "sleep", lambda seconds: None)

    def test_reports_success_when_window_becomes_foreground(self, monkeypatch):
        self._common_mocks(monkeypatch, foreground=4242)
        assert Window._force_foreground(4242) is True

    def test_returns_false_when_every_method_fails(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("拒绝访问")

        self._common_mocks(monkeypatch, foreground=999)
        monkeypatch.setattr(win32gui, "SetForegroundWindow", boom)
        monkeypatch.setattr(win32gui, "BringWindowToTop", boom)
        monkeypatch.setattr(win32gui, "SetWindowPos", boom)
        assert Window._force_foreground(4242) is False

    def test_restores_minimised_window(self, monkeypatch):
        shown = []
        self._common_mocks(monkeypatch, foreground=4242)
        monkeypatch.setattr(win32gui, "IsIconic", lambda hwnd: True)
        monkeypatch.setattr(
            win32gui, "ShowWindow", lambda hwnd, cmd: shown.append((hwnd, cmd))
        )
        Window._force_foreground(4242)
        assert shown == [(4242, win32con.SW_RESTORE)]


class TestSwitchWindow:
    def test_activates_matching_window(self, monkeypatch, no_sleep):
        moved = []
        monkeypatch.setattr(
            pyautogui, "getAllWindows", lambda: [FakeWindowHandle("崩坏：星穹铁道")]
        )
        monkeypatch.setattr(
            pyautogui, "moveTo", lambda x, y: moved.append((x, y))
        )
        monkeypatch.setattr(Window, "_force_foreground", staticmethod(lambda hwnd: True))

        win = object.__new__(Window)
        win.switch_window()

        assert moved == [(960, 540)], "找到窗口后应把鼠标移到窗口中心"

    def test_skips_windows_that_fail_to_activate(self, monkeypatch, no_sleep):
        monkeypatch.setattr(
            pyautogui,
            "getAllWindows",
            lambda: [
                FakeWindowHandle("崩坏：星穹铁道", hwnd=1),
                FakeWindowHandle("崩坏：星穹铁道", hwnd=2),
            ],
        )
        monkeypatch.setattr(pyautogui, "moveTo", lambda x, y: None)
        monkeypatch.setattr(Window, "_force_foreground", staticmethod(lambda hwnd: True))
        # 第一个窗口 restore() 抛异常，应继续尝试第二个
        original = FakeWindowHandle.restore

        def flaky(self):
            if self._hWnd == 1:
                raise RuntimeError("无法激活")
            return original(self)

        monkeypatch.setattr(FakeWindowHandle, "restore", flaky)

        win = object.__new__(Window)
        win.switch_window()  # 不应抛出


class TestFindLnkFiles:
    def test_finds_lnk_case_insensitively(self, tmp_path):
        (tmp_path / "a.lnk").write_text("", encoding="utf-8")
        (tmp_path / "b.LNK").write_text("", encoding="utf-8")
        (tmp_path / "c.txt").write_text("", encoding="utf-8")
        win = object.__new__(Window)
        found = sorted(tmp_path / name for name in ("a.lnk", "b.LNK"))
        assert sorted(win.find_lnk_files(tmp_path)) == [str(p) for p in found]

    def test_searches_subdirectories(self, tmp_path):
        nested = tmp_path / "sub"
        nested.mkdir()
        (nested / "deep.lnk").write_text("", encoding="utf-8")
        win = object.__new__(Window)
        assert len(win.find_lnk_files(tmp_path)) == 1

    def test_returns_empty_for_missing_folder(self, tmp_path):
        win = object.__new__(Window)
        assert win.find_lnk_files(tmp_path / "nope") == []


class TestStartLnkFile:
    def test_quotes_the_path(self, monkeypatch):
        commands = []
        monkeypatch.setattr(window_module.os, "system", lambda cmd: commands.append(cmd))
        win = object.__new__(Window)
        win.start_lnk_file("C:\\path with spaces\\game.lnk")
        assert commands == ['start "" "C:\\path with spaces\\game.lnk"']
