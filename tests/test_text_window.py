"""utils/ui/text_window.py —— 开发者调试窗口的文本分发。"""

from types import SimpleNamespace

import pytest

import utils.ui.text_window as text_window_module
from utils.ui.text_window import TEXT_WINDOWS, TextWindow, show_text


class StubCanvas:
    def __init__(self, bbox=(0, 0, 100, 20)):
        self.bbox_value = bbox
        self.text_items = []
        self.deleted = []
        self.configured = []

    def delete(self, item):
        self.deleted.append(item)

    def create_text(self, *args, **kwargs):
        self.text_items.append(kwargs)
        return "item-id"

    def bbox(self, item):
        return self.bbox_value

    def configure(self, **kwargs):
        self.configured.append(kwargs)


class StubRoot:
    def __init__(self):
        self.deiconified = 0
        self.geometry_spec = None

    def deiconify(self):
        self.deiconified += 1

    def geometry(self, spec):
        self.geometry_spec = spec


@pytest.fixture
def registered(monkeypatch):
    """注册一个假的 TextWindow，避免依赖真实的 Tk 窗口。"""
    delivered = []
    window = SimpleNamespace(
        queue=SimpleNamespace(put=lambda task: delivered.append(task)),
        show_text=lambda text, x, y: delivered.append((text, x, y)),
    )
    monkeypatch.setitem(TEXT_WINDOWS, "test-window", window)
    return delivered


class TestShowTextDispatch:
    def test_nouid_mode_shifts_x_left_by_150(self, registered):
        show_text("hello", 300, 100, "nouid", "test-window")

        assert len(registered) == 1
        registered[0]()
        assert registered[1] == ("hello", 150, 100)

    def test_showuid_mode_keeps_x(self, registered):
        show_text("hello", 300, 100, "showuid", "test-window")

        registered[0]()
        assert registered[1] == ("hello", 300, 100)

    def test_unknown_mode_defaults_to_nouid(self, registered):
        show_text("hello", 300, 100, "not-a-mode", "test-window")

        registered[0]()
        assert registered[1] == ("hello", 150, 100)

    def test_unknown_window_id_is_ignored(self, registered):
        show_text("hello", 300, 100, "nouid", "no-such-window")
        assert registered == []

    def test_skips_when_tkinter_is_unavailable(self, registered, monkeypatch):
        monkeypatch.setattr(text_window_module, "TK_AVAILABLE", False)
        show_text("hello", 300, 100, "nouid", "test-window")
        assert registered == []

    def test_text_is_queued_not_applied_immediately(self, registered):
        """show_text 只入队，真正的绘制由 Tk 线程的消息循环执行。"""
        show_text("hello", 300, 100, "nouid", "test-window")
        assert registered[0]() is None


class TestTextWindowShowText:
    def build(self, bbox):
        canvas = StubCanvas(bbox=bbox)
        root = StubRoot()
        return SimpleNamespace(canvas=canvas, root=root), canvas, root

    def test_draws_outline_plus_main_text(self):
        window, canvas, root = self.build(bbox=(0, 0, 100, 20))

        TextWindow.show_text(window, "hello", x=10, y=20)

        drawn = [item for item in canvas.text_items if "width" in item]
        assert len(drawn) == 5, "4 个描边副本 + 1 个正文"
        assert canvas.deleted == ["all", "item-id"], "量完尺寸的临时文本要被删除"
        assert canvas.configured == [{"width": 130, "height": 20}]
        assert root.geometry_spec == "+10+20"
        assert root.deiconified == 1

    def test_text_width_is_canvas_width_minus_padding(self):
        window, canvas, _ = self.build(bbox=(0, 0, 100, 20))

        TextWindow.show_text(window, "hello", x=0, y=0)

        drawn = [item for item in canvas.text_items if "width" in item]
        assert all(item["width"] == 100 for item in drawn)

    @pytest.mark.xfail(
        strict=True,
        reason="width 只在 `if bbox:` 内赋值，却在其外无条件使用；"
        "bbox 为空（例如空文本）时抛 UnboundLocalError，并让 process_queue 不再重排自己",
    )
    def test_empty_bbox_does_not_crash(self):
        window, _, _ = self.build(bbox=None)
        TextWindow.show_text(window, "", x=0, y=0)


class TestWindowRegistry:
    def test_registry_dicts_exist(self):
        assert isinstance(TEXT_WINDOWS, dict)
        assert isinstance(text_window_module.TKINTER_THREADS, dict)

    def test_start_tkinter_thread_is_a_noop_without_tkinter(self, monkeypatch):
        monkeypatch.setattr(text_window_module, "TK_AVAILABLE", False)
        text_window_module.TKINTER_THREADS.clear()

        text_window_module.start_tkinter_thread("some-window")

        assert "some-window" not in text_window_module.TKINTER_THREADS
        assert "some-window" not in TEXT_WINDOWS, "无 tkinter 时应静默降级，不能阻塞主流程"
