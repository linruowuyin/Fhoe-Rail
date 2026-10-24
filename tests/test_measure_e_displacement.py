"""tools/measure_e_displacement.py —— 纯逻辑部分（不连接游戏）。"""

import numpy as np
import pytest

import tools.measure_e_displacement as measure


class TestBestScored:
    def test_picks_the_highest_score(self):
        assert measure.best_scored([(0.2, 0.7), (0.24, 0.83), (0.3, 0.6)]) == (
            0.24,
            0.83,
        )


class TestParseArgs:
    def test_defaults(self):
        opts = measure.parse_args([])
        assert opts["start"] == 0.2
        assert opts["end"] == 1.0
        assert opts["interval"] == 0.02
        assert opts["sprint"] is False
        assert opts["out"] is None

    def test_sprint_flag(self):
        assert measure.parse_args(["--sprint"])["sprint"] is True

    def test_flags(self):
        opts = measure.parse_args(
            [
                "--start",
                "0.3",
                "--end=0.9",
                "--interval",
                "0.05",
                "--sprint",
                "--out=x",
            ]
        )
        assert opts["start"] == 0.3
        assert opts["end"] == 0.9
        assert opts["interval"] == 0.05
        assert opts["sprint"] is True
        assert opts["out"] == "x"

    def test_bad_interval_is_refused(self):
        with pytest.raises(SystemExit):
            measure.parse_args(["--interval", "0"])

    def test_end_before_start_is_refused(self):
        with pytest.raises(SystemExit):
            measure.parse_args(["--start", "1", "--end", "0.5"])

    def test_unknown_argument_is_refused(self):
        with pytest.raises(SystemExit):
            measure.parse_args(["--nope"])


class TestSnap:
    def test_snaps_one_frame_without_waiting_for_stability(self, monkeypatch):
        calls = []

        def fake_capture(img, box):
            calls.append(box)
            return "frame"

        monkeypatch.setattr(measure, "capture", fake_capture)
        monkeypatch.setattr(
            measure, "wait_stable", lambda *a, **k: pytest.fail("不能等画面静止")
        )

        assert measure.snap(object()) == "frame"
        assert calls == [measure.SCORE_BOX]


class TestFinalPaths:
    def test_final_names_include_final_and_duration(self, tmp_path):
        reference, candidate = measure.final_paths(tmp_path, 0.73)
        assert reference.name == "final_huangquan_e.png"
        assert candidate.name == "final_ss_0.73.png"
        assert reference.parent == tmp_path


class TestCrop:
    def test_crops_expected_region(self):
        frame = np.arange(10 * 10 * 3, dtype=np.uint8).reshape(10, 10, 3)
        part = measure.crop(frame, (2, 3, 5, 8))
        assert part.shape == (5, 3, 3)
        assert (part == frame[3:8, 2:5]).all()
