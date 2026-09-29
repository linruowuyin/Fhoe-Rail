"""utils/drivers/window.py —— 窗口查找、标题匹配、客户区/全屏矩形计算。"""

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
        assert Window._get_client(Window, "崩坏：星穹铁道") == "客户端"

    def test_cloud_client(self):
        assert Window._get_client(Window, "云·星穹铁道") == "云游戏"


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
