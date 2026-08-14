import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key as KeyboardKey

# 特殊键名映射，避免 pynput 收到字符串时抛异常或行为异常
_KEY_MAP = {
    "space": KeyboardKey.space,
    "caps": KeyboardKey.caps_lock,
    "alt": KeyboardKey.alt,
    "alt_l": KeyboardKey.alt_l,
    "alt_r": KeyboardKey.alt_r,
    "shift": KeyboardKey.shift,
    "shift_l": KeyboardKey.shift_l,
    "shift_r": KeyboardKey.shift_r,
    "ctrl": KeyboardKey.ctrl,
    "ctrl_l": KeyboardKey.ctrl_l,
    "ctrl_r": KeyboardKey.ctrl_r,
    "esc": KeyboardKey.esc,
    "enter": KeyboardKey.enter,
    "tab": KeyboardKey.tab,
    "backspace": KeyboardKey.backspace,
}


class KeyboardEvent:
    def __init__(self):
        self.keyboard = KeyboardController()

    @staticmethod
    def translate_key(key_name: str):
        """
        转换key，支持特殊键名映射
        """
        return _KEY_MAP.get(key_name, key_name)

    @staticmethod
    def keyboard_press(key_name: str, delay: float = 0):
        """
        按下键盘后延迟抬起
        使用 try/finally 保证按键一定会被释放，避免异常导致按键卡住
        """
        key_name = KeyboardEvent.translate_key(key_name)
        controller = KeyboardController()
        try:
            controller.press(key_name)
            time.sleep(delay)
        finally:
            controller.release(key_name)
