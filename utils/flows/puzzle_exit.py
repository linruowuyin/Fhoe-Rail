"""Exit an accidentally opened puzzle during main-interface recovery."""

from utils.core.log import log
from utils.vision.images import get_img
from utils.vision.puzzle_exit import find_puzzle_exit_confirmation


def try_exit_puzzle(img, mouse):
    """Click only a recognized puzzle-abandon confirmation, using one frame."""
    prompt = get_img("picture/puzzle_exit_prompt.png")
    confirm = get_img("picture/puzzle_exit_confirm.png")
    if prompt is None or confirm is None:
        return False
    frame, left, top, _, _ = img.take_screenshot()
    point = find_puzzle_exit_confirmation(frame, prompt, confirm)
    if point is None:
        return False
    log.info("检测到“是否放弃游玩？”，确认退出解谜并等待主界面")
    mouse.click((left + point[0], top + point[1]))
    return True
