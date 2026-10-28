"""在主界面恢复流程里，退出误开的解谜界面。"""

from utils.core.log import log
from utils.vision import assets
from utils.vision.images import get_img
from utils.vision.puzzle_exit import find_puzzle_exit_confirmation


def try_exit_puzzle(img, mouse):
    """识别到「放弃游玩？」确认弹窗就点「确认」；返回是否点击了。

    只抓一帧：识别和点击用的是同一帧上的坐标，不重新截图（R10）。
    资源缺失或没识别到都返回 False，不抛异常。
    """
    prompt = get_img(assets.path("puzzle_exit_prompt"))
    confirm = get_img(assets.path("puzzle_exit_confirm"))
    if prompt is None or confirm is None:
        return False
    frame, left, top, _, _ = img.take_screenshot()
    point = find_puzzle_exit_confirmation(frame, prompt, confirm)
    if point is None:
        return False
    log.info("检测到“是否放弃游玩？”，确认退出解谜并等待主界面")
    # find_puzzle_exit_confirmation 返回的是帧内坐标，加上窗口原点才是屏幕坐标
    mouse.click((left + point[0], top + point[1]))
    return True
