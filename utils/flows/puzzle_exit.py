"""解谜放弃弹窗：`pre_esc` 修复表里的一项。

识别是纯函数（吃一帧），点击是单独一步 —— 修复表负责把它们接到同一帧上。
"""

from utils.core.log import log
from utils.vision import assets
from utils.vision.images import get_img
from utils.vision.puzzle_exit import find_puzzle_exit_confirmation


def detect(frame):
    """在同一帧里识别「是否放弃游玩？」；返回确认按钮的帧内坐标或 None。"""
    prompt = get_img(assets.path("puzzle_exit_prompt"))
    confirm = get_img(assets.path("puzzle_exit_confirm"))
    if prompt is None or confirm is None:
        return None
    return find_puzzle_exit_confirmation(frame, prompt, confirm)


def click(point, mouse, left=0, top=0):
    """点「确认」：帧内坐标 + 窗口原点才是屏幕坐标。"""
    log.info("检测到“是否放弃游玩？”，确认退出解谜并等待主界面")
    mouse.click((left + point[0], top + point[1]))
