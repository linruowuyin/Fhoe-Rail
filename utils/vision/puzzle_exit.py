"""Recognize the specific Chinese puzzle-abandon dialog from one 1080p frame.

The prompt and the confirm button must both match in their expected regions.
Matching only the generic confirm label could accept purchases or battle exits.
"""

import cv2

from utils.core.thresholds import PUZZLE_EXIT_CONFIRM, PUZZLE_EXIT_PROMPT


def _match_region(frame, template, bounds, threshold):
    if template is None:
        return None
    left, top, right, bottom = bounds
    region = frame[top:bottom, left:right]
    height, width = template.shape[:2]
    if region.shape[0] < height or region.shape[1] < width:
        return None
    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    if score <= threshold:
        return None
    return left + location[0] + width // 2, top + location[1] + height // 2


def find_puzzle_exit_confirmation(frame, prompt, confirm):
    """Return the confirm-button center, or None; never capture or click here.

    Coordinates refer to the same 1920x1080 client frame supplied by ScreenSource.
    Unknown resolutions and missing resources fail closed.
    """
    if frame is None or frame.shape[:2] != (1080, 1920):
        return None
    if _match_region(frame, prompt, (576, 432, 1344, 616), PUZZLE_EXIT_PROMPT) is None:
        return None
    return _match_region(frame, confirm, (960, 616, 1440, 756), PUZZLE_EXIT_CONFIRM)
