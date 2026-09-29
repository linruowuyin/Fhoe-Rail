"""utils/ui/record.py —— 地图录制器的按键映射与输出格式。

record_main 里的一切都是嵌套函数，只能通过驱动整个函数并捕获
pynput 的回调来测试；因此这里把监听器换成替身，直接调用回调。
"""

import builtins
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import utils.ui.record as record_module
from utils.core.json_io import is_canonical


class FakeKeyboardListener:
    def __init__(self, on_press=None, on_release=None):
        self.on_press = on_press
        self.on_release = on_release

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def join(self):
        return None


class FakePynputKeyboard:
    """替身：Key 用字符串哨兵，Listener 只记录回调。"""

    class Key:
        left = "KEY_LEFT"
        right = "KEY_RIGHT"
        space = "KEY_SPACE"
        esc = "KEY_ESC"
        f9 = "KEY_F9"

    def __init__(self):
        self.listener = None

    def Listener(self, on_press=None, on_release=None):
        self.listener = FakeKeyboardListener(on_press, on_release)
        return self.listener


class FakeMouseModule:
    class Listener:
        def __init__(self, on_click=None, on_move=None):
            self.on_click = on_click

        def start(self):
            return None

        def stop(self):
            return None


class FakeShell32:
    def __init__(self, is_admin=True, recorder=None):
        self.is_admin = is_admin
        self.recorder = recorder if recorder is not None else []

    def IsUserAnAdmin(self):
        return self.is_admin

    def ShellExecuteW(self, *args):
        self.recorder.append(args)


def drive_recorder(monkeypatch, root, real_width=1920, is_admin=True):
    """驱动 record_main 并返回 (回调, 捕获的 print, 鼠标事件)。

    real_width 必须在 record_main 之前写进 config.json —— 它在录制开始时被读一次
    并闭包捕获，之后再改配置不会生效。
    """
    config_with_width(root, real_width)

    keyboard_stub = FakePynputKeyboard()
    shell32 = FakeShell32(is_admin=is_admin)
    monkeypatch.setattr(record_module, "keyboard", keyboard_stub)
    monkeypatch.setattr(record_module, "mouse", FakeMouseModule)
    monkeypatch.setattr(
        record_module,
        "mouseController",
        lambda: SimpleNamespace(position=(960, 540)),
    )
    monkeypatch.setattr(record_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        record_module,
        "ctypes",
        SimpleNamespace(windll=SimpleNamespace(shell32=shell32)),
    )

    printed = []
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: printed.append(args))

    mouse_events = []
    monkeypatch.setattr(
        record_module.win32api, "mouse_event", lambda *args: mouse_events.append(args)
    )
    monkeypatch.setattr(record_module.win32api, "SetCursorPos", lambda pos: None)

    record_module.record_main()

    return SimpleNamespace(
        press=keyboard_stub.listener.on_press,
        release=keyboard_stub.listener.on_release,
        printed=printed,
        mouse_events=mouse_events,
        shell32=shell32,
        root=root,
    )


@pytest.fixture
def recorder(monkeypatch, isolated_cwd):
    return drive_recorder(monkeypatch, isolated_cwd)


@pytest.fixture
def make_recorder(monkeypatch, isolated_cwd):
    def _make(real_width=1920, is_admin=True):
        return drive_recorder(
            monkeypatch, isolated_cwd, real_width=real_width, is_admin=is_admin
        )

    return _make


def config_with_width(root, width):
    path = root / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["real_width"] = width
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def press_and_release(recorder, key):
    recorder.press(SimpleNamespace(char=key) if isinstance(key, str) else key)
    recorder.release(SimpleNamespace(char=key) if isinstance(key, str) else key)


def latest_output(root):
    files = sorted(Path(root).glob("output*.json"))
    assert files, "F9 应写出 output*.json"
    return json.loads(files[-1].read_text(encoding="utf-8"))


class TestStartup:
    def test_prints_a_startup_banner(self, recorder):
        assert any("开启录制" in str(args) for args in recorder.printed)

    def test_reports_the_centre_coordinate(self, recorder):
        assert any("中心点坐标" in str(args) for args in recorder.printed)


class TestAdminRelaunch:
    def test_does_not_relaunch_when_already_admin(self, make_recorder):
        recorder = make_recorder(is_admin=True)
        assert recorder.shell32.recorder == []

    @pytest.mark.xfail(
        strict=True,
        reason="提权拉起副本后只 return 不退出，未提权的原进程会继续录制，"
        "于是两个进程各跑一份监听、各写一份 output*.json",
    )
    def test_original_process_stops_after_relaunching_as_admin(self, make_recorder):
        recorder = make_recorder(is_admin=False)

        assert recorder.shell32.recorder, "应先拉起提权副本"
        assert not any("开启录制" in str(args) for args in recorder.printed), (
            "提权后原进程不应继续录制"
        )


class TestKeyboardCapture:
    def test_direction_key_emits_relative_move(self, recorder):
        recorder.release(FakePynputKeyboard.Key.right)
        assert recorder.mouse_events[-1][1] == int(200 * 1295 / 1920)

    def test_left_key_moves_the_other_way(self, recorder):
        recorder.release(FakePynputKeyboard.Key.left)
        assert recorder.mouse_events[-1][1] == int(-200 * 1295 / 1920)

    @pytest.mark.xfail(
        strict=True,
        reason="real_width 取自 config，未初始化分辨率时默认为 0，"
        "按左右方向键会抛 ZeroDivisionError",
    )
    def test_zero_real_width_does_not_crash(self, make_recorder):
        recorder = make_recorder(real_width=0)

        recorder.release(FakePynputKeyboard.Key.right)

    def test_w_key_becomes_a_move_entry(self, recorder):
        press_and_release(recorder, "w")
        recorder.release(FakePynputKeyboard.Key.f9)
        entry = latest_output(recorder.root)["map"][0]
        assert list(entry) == ["w"]

    def test_x_key_becomes_fighting_1(self, recorder):
        press_and_release(recorder, "x")
        recorder.release(FakePynputKeyboard.Key.f9)
        assert {"fighting": 1} in latest_output(recorder.root)["map"]

    def test_e_key_becomes_channel_e(self, recorder):
        press_and_release(recorder, "e")
        recorder.release(FakePynputKeyboard.Key.f9)
        assert {"e": 2} in latest_output(recorder.root)["map"]

    def test_f_key_uses_the_fifteen_second_default(self, recorder):
        press_and_release(recorder, "f")
        recorder.release(FakePynputKeyboard.Key.f9)
        assert {"f": 15} in latest_output(recorder.root)["map"]

    def test_v_key_becomes_an_await_step(self, recorder):
        press_and_release(recorder, "v")
        recorder.release(FakePynputKeyboard.Key.f9)
        assert "await" in latest_output(recorder.root)["map"][0]

    def test_space_key_is_recorded(self, recorder):
        recorder.press(FakePynputKeyboard.Key.space)
        recorder.release(FakePynputKeyboard.Key.f9)
        assert "space" in latest_output(recorder.root)["map"][0]

    def test_unknown_keys_are_ignored(self, recorder):
        press_and_release(recorder, "z")
        recorder.release(FakePynputKeyboard.Key.f9)
        assert latest_output(recorder.root)["map"] == []


class TestOutputFormat:
    def test_output_has_the_map_file_skeleton(self, recorder):
        recorder.release(FakePynputKeyboard.Key.f9)
        document = latest_output(recorder.root)
        assert set(document) == {"name", "author", "start", "map"}

    def test_f9_writes_the_file(self, recorder):
        recorder.release(FakePynputKeyboard.Key.f9)
        assert list(Path(recorder.root).glob("output*.json"))

    def test_written_file_is_in_the_canonical_format(self, recorder):
        # 录制产出也是地图 JSON，跟 webui 保存、convert.py 走同一个序列化器（R22）
        recorder.release(FakePynputKeyboard.Key.right)
        press_and_release(recorder, "w")
        recorder.release(FakePynputKeyboard.Key.f9)

        text = sorted(Path(recorder.root).glob("output*.json"))[-1].read_text(encoding="utf-8")
        assert is_canonical(text)

    def test_mouse_move_is_aggregated_into_one_entry(self, recorder):
        recorder.release(FakePynputKeyboard.Key.right)
        recorder.release(FakePynputKeyboard.Key.right)
        press_and_release(recorder, "w")
        recorder.release(FakePynputKeyboard.Key.f9)

        entries = latest_output(recorder.root)["map"]
        mouse_entries = [e for e in entries if "mouse_move" in e]
        assert len(mouse_entries) == 1, "连续的方向键应合并成一次视角移动"
