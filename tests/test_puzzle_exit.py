"""Real dialog pixels plus similar-looking negatives; no game or device input."""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from utils.flows import puzzle_exit as flow
from utils.vision.puzzle_exit import find_puzzle_exit_confirmation


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples():
    # Only the anonymous dialog was retained: no UID, desktop or account data.
    dialog = cv2.imread(str(ROOT / "tests/fixtures/puzzle_exit/dialog.png"))
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[350:750, 460:1460] = dialog
    prompt = cv2.imread(str(ROOT / "picture/puzzle_exit_prompt.png"))
    confirm = cv2.imread(str(ROOT / "picture/puzzle_exit_confirm.png"))
    return frame, prompt, confirm


def test_real_dialog_returns_confirm_not_cancel(samples):
    frame, prompt, confirm = samples
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) == (1167, 672)


def test_confirm_button_without_specific_prompt_is_ignored(samples):
    frame, prompt, confirm = samples
    frame[505:546, 860:1050] = frame[490, 850]
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


def test_prompt_without_confirm_button_is_ignored(samples):
    frame, prompt, confirm = samples
    frame[650:695, 1110:1225] = frame[672, 1250]
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


def test_confirm_on_cancel_side_is_not_clicked(samples):
    frame, prompt, confirm = samples
    frame[650:695, 1110:1225] = frame[672, 1250]
    frame[651:693, 700:798] = confirm
    assert find_puzzle_exit_confirmation(frame, prompt, confirm) is None


@pytest.mark.parametrize("missing", ["frame", "prompt", "confirm"])
def test_missing_input_is_ignored(samples, missing):
    values = dict(zip(("frame", "prompt", "confirm"), samples))
    values[missing] = None
    assert find_puzzle_exit_confirmation(**values) is None


def test_unknown_resolution_is_ignored(samples):
    frame, prompt, confirm = samples
    assert find_puzzle_exit_confirmation(frame[::2, ::2], prompt, confirm) is None


def test_one_frame_and_screen_origin_used_for_click(samples, monkeypatch):
    frame, prompt, confirm = samples
    monkeypatch.setattr(flow, "get_img", lambda p: prompt if "prompt" in p else confirm)
    captured, clicks = [], []
    def capture():
        captured.append(1)
        return frame, 1272, 591, 3192, 1671
    assert flow.try_exit_puzzle(
        SimpleNamespace(take_screenshot=capture), SimpleNamespace(click=clicks.append)
    )
    assert captured == [1]
    assert clicks == [(2439, 1263)]


def test_missing_asset_does_not_capture_or_click(monkeypatch):
    monkeypatch.setattr(flow, "get_img", lambda p: None)
    assert not flow.try_exit_puzzle(SimpleNamespace(), SimpleNamespace())


def test_unrelated_dialog_does_not_click(samples, monkeypatch):
    frame, prompt, confirm = samples
    frame[505:546, 860:1050] = frame[490, 850]
    monkeypatch.setattr(flow, "get_img", lambda p: prompt if "prompt" in p else confirm)
    assert not flow.try_exit_puzzle(
        SimpleNamespace(take_screenshot=lambda: (frame, 0, 0, 1920, 1080)),
        SimpleNamespace(),
    )
