import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key as KeyboardKey


class KeyboardEvent:
    def __init__(self):
        self.keyboard = KeyboardController()

    @staticmethod
    def translate_key(key_name: str):
        """
        转换key
        """
        if key_name == "space":
            key_name = KeyboardKey.space
        if key_name == "caps":
            key_name = KeyboardKey.caps_lock

        return key_name

    @staticmethod
    def keyboard_press(key_name: str, delay: float = 0):
        """
        按下键盘后延迟抬起
        """
        key_name = KeyboardEvent.translate_key(key_name)
        KeyboardController().press(key_name)
        time.sleep(delay)
        KeyboardController().release(key_name)
