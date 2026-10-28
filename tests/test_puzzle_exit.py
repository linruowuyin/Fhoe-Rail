"""解谜放弃弹窗的黄金图测试：真实弹窗像素 + 多种「像但不是」的负样本。

不连游戏、不碰键鼠：帧和模板都是文件/内存里的数组。
"""

from pathlib import Path
import cv2
import numpy as np
import pytest

from utils.flows import puzzle_exit as flow
from utils.vision import assets
from utils.vision.puzzle_exit import find_puzzle_exit_confirmation


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples():
    # 只保留了匿名弹窗：没有 UID、桌面或账号信息。
    dialog = cv2.imread(str(ROOT / "tests/fixtures/puzzle_exit/dialog.png"))
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[350:750, 460:1460] = dialog
    prompt = cv2.imread(str(ROOT / assets.path("puzzle_exit_prompt")))
    confirm = cv2.imread(str(ROOT / assets.path("puzzle_exit_confirm")))
    return frame, prompt, confirm


def test_real_dialog_returns_confirm_not_cancel(samples):
    """正样本：返回右侧确认按钮中心 (1167, 672)，不是左侧取消。"""
    frame, prompt, confirm = samples
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) == (1167, 672)


def test_confirm_button_without_specific_prompt_is_ignored(samples):
    """负样本 1：只有确认按钮、没有“是否放弃游玩？”提示 —— 不能点。"""
    frame, prompt, confirm = samples
    frame[505:546, 860:1050] = frame[490, 850]
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


def test_prompt_without_confirm_button_is_ignored(samples):
    """负样本 2：只有提示语、确认按钮被擦掉 —— 不能点。"""
    frame, prompt, confirm = samples
    frame[650:695, 1110:1225] = frame[672, 1250]
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


def test_confirm_on_cancel_side_is_not_clicked(samples):
    """负样本 3：确认按钮被挪到左边取消位 —— 区域校验必须拒绝。"""
    frame, prompt, confirm = samples
    frame[650:695, 1110:1225] = frame[672, 1250]
    frame[651:693, 700:798] = confirm
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


def test_a_template_bigger_than_its_region_is_ignored(samples):
    """模板比区域还大时不喂给 cv2（不然会抛断言），直接当没找到。"""
    frame, _, confirm = samples
    oversized_prompt = np.zeros((700, 900, 3), dtype=np.uint8)
    assert find_puzzle_exit_confirmation(frame, oversized_prompt, confirm) is None


@pytest.mark.parametrize("missing", ["frame", "prompt", "confirm"])
def test_missing_input_is_ignored(samples, missing):
    values = dict(zip(("frame", "prompt", "confirm"), samples))
    values[missing] = None
    assert find_puzzle_exit_confirmation(**values) is None


def test_unknown_resolution_is_ignored(samples):
    frame, prompt, confirm = samples
    assert find_puzzle_exit_confirmation(frame[::2, ::2], prompt, confirm) is None


def test_click_adds_the_window_origin():
    """点击坐标 = 帧内坐标 + 窗口原点；识别本身不碰鼠标。"""
    clicks = []
    mouse = type("Mouse", (), {"click": lambda self, point: clicks.append(point)})()

    flow.click((1167, 672), mouse, 1272, 591)

    assert clicks == [(2439, 1263)]


def test_missing_asset_makes_detect_return_none(monkeypatch):
    monkeypatch.setattr(flow, "get_img", lambda p: None)

    assert flow.detect(np.zeros((1080, 1920, 3), dtype=np.uint8)) is None


def test_unrelated_dialog_is_not_recognized(samples):
    """别的弹窗（只有确认按钮、没有这句提示）不能被当成放弃游玩。"""
    frame, _, _ = samples
    frame[505:546, 860:1050] = frame[490, 850]

    assert flow.detect(frame) is None
