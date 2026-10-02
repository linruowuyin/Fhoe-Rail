"""utils/vision/viewer.py —— 调试图片窗口的 cv2 显示接口。

这里只测 `wait_key` 的退出条件：它是个真的等人的循环，必须能退出（CLAUDE.md R3）。
真开窗口那一半只能在有桌面环境的机器上冒烟。
"""

import utils.vision.viewer as viewer


class TestWaitKey:
    def test_returns_the_pressed_key(self, monkeypatch):
        monkeypatch.setattr(viewer.cv2, "waitKey", lambda poll_ms: 13)

        assert viewer.wait_key() == 13

    def test_gives_up_when_the_window_was_closed(self, monkeypatch):
        """用户点右上角关掉窗口时必须能退出来 —— 直接 waitKey(0) 会一直挂住。"""
        monkeypatch.setattr(viewer.cv2, "waitKey", lambda poll_ms: -1)
        monkeypatch.setattr(viewer.cv2, "getWindowProperty", lambda *args: 0)

        assert viewer.wait_key() == -1

    def test_gives_up_when_the_window_is_gone(self, monkeypatch):
        def no_such_window(*args):
            raise viewer.cv2.error("NULL window")

        monkeypatch.setattr(viewer.cv2, "waitKey", lambda poll_ms: -1)
        monkeypatch.setattr(viewer.cv2, "getWindowProperty", no_such_window)

        assert viewer.wait_key() == -1

    def test_keeps_waiting_while_the_window_is_alive(self, monkeypatch):
        """没人按键、窗口还在 —— 继续等，每一轮都让出事件循环。"""
        polls = []

        def wait_key(poll_ms):
            polls.append(poll_ms)
            return 27 if len(polls) == 3 else -1

        monkeypatch.setattr(viewer.cv2, "waitKey", wait_key)
        monkeypatch.setattr(viewer.cv2, "getWindowProperty", lambda *args: 1)

        assert viewer.wait_key() == 27
        assert len(polls) == 3
