"""utils/flows/pre_esc.py —— 按 ESC 前的统一修复表。

用替身检测器验调度语义（同帧、顺序、首次命中、once），再用真实解谜帧做一条
端到端：同一帧识别 → 原点换算 → 点击。
"""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from utils.flows import pre_esc
from utils.flows.pre_esc import PreEscFix


def make_fixer(fixes, monthly_pass=None, mouse=None):
    """构造一个只带给定修复表的 fixer（跳过真实月卡/解谜项的装配）。"""
    fixer = pre_esc.PreEscFixer(
        img=None,
        mouse=mouse or object(),
        monthly_pass=monthly_pass
        or SimpleNamespace(match_frame=lambda frame: None),
    )
    fixer.fixes = tuple(fixes)
    return fixer


class TestDispatch:
    def test_no_match_returns_false_and_applies_nothing(self):
        applied = []
        fixer = make_fixer(
            [PreEscFix("a", lambda frame: None, lambda action, l, t: applied.append(1))]
        )

        assert fixer.try_fix(frame=object(), left=0, top=0) is False
        assert applied == []

    def test_first_match_applies_with_the_frame_origin_and_stops(self):
        applied, detected = [], []

        def detect_b(frame):
            detected.append("b")
            return "action-b"

        fixer = make_fixer(
            [
                PreEscFix("a", lambda frame: None, lambda action, l, t: applied.append("a")),
                PreEscFix("b", detect_b, lambda action, l, t: applied.append((action, l, t))),
                PreEscFix("c", lambda frame: "action-c", lambda action, l, t: applied.append("c")),
            ]
        )

        assert fixer.try_fix(frame=object(), left=100, top=200) is True
        assert applied == [("action-b", 100, 200)]
        assert detected == ["b"], "命中后不再往下尝试"

    def test_every_fix_gets_the_same_frame_object(self):
        frames = []
        fixer = make_fixer(
            [
                PreEscFix("a", lambda frame: frames.append(frame), lambda *a: None),
                PreEscFix("b", lambda frame: frames.append(frame), lambda *a: None),
            ]
        )
        frame = object()

        fixer.try_fix(frame, 0, 0)

        assert frames == [frame, frame]

    def test_a_once_fix_is_not_retried_after_a_miss(self):
        calls = []
        fixer = make_fixer(
            [PreEscFix("monthly", lambda frame: calls.append(1), lambda *a: None, once=True)]
        )

        fixer.try_fix(object(), 0, 0)
        fixer.try_fix(object(), 0, 0)

        assert calls == [1], "没命中也不在本次 back_to_main 里重复试"

    def test_a_once_fix_is_not_retried_after_a_hit(self):
        calls = []
        fixer = make_fixer(
            [
                PreEscFix(
                    "monthly",
                    lambda frame: calls.append(1) or "action",
                    lambda *a: None,
                    once=True,
                )
            ]
        )

        assert fixer.try_fix(object(), 0, 0) is True
        assert fixer.try_fix(object(), 0, 0) is False

        assert calls == [1]

    def test_a_normal_fix_can_retry_on_the_next_iteration(self):
        calls = []
        fixer = make_fixer(
            [PreEscFix("puzzle", lambda frame: calls.append(1), lambda *a: None)]
        )

        fixer.try_fix(object(), 0, 0)
        fixer.try_fix(object(), 0, 0)

        assert calls == [1, 1]


class TestRealPuzzleFix:
    @pytest.fixture
    def frame(self, repo_root):
        dialog = cv2.imread(str(repo_root / "tests/fixtures/puzzle_exit/dialog.png"))
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[350:750, 460:1460] = dialog
        return frame

    def test_recognizes_the_dialog_and_clicks_with_the_origin_added(self, frame):
        clicks = []
        mouse = type("Mouse", (), {"click": lambda self, point: clicks.append(point)})()
        monthly = type("Monthly", (), {"match_frame": lambda self, frame: None})()
        fixer = pre_esc.PreEscFixer(img=None, mouse=mouse, monthly_pass=monthly)

        assert fixer.try_fix(frame, 1272, 591) is True
        assert clicks == [(2439, 1263)]

    def test_an_unrelated_frame_falls_through_to_the_next_fix(self, frame):
        frame = frame.copy()
        frame[505:546, 860:1050] = frame[490, 850]  # 擦掉“是否放弃游玩？”
        applied = []
        monthly = type(
            "Monthly",
            (),
            {"match_frame": lambda self, f: "monthly-action"},
        )()
        fixer = pre_esc.PreEscFixer(img=None, mouse=object(), monthly_pass=monthly)

        # 把月卡的 apply 换掉，避免真的点
        fixer.fixes = (
            fixer.fixes[0],
            PreEscFix(
                "monthly_pass",
                monthly.match_frame,
                lambda action, left, top: applied.append(action),
                once=True,
            ),
        )

        assert fixer.try_fix(frame, 0, 0) is True
        assert applied == ["monthly-action"]
