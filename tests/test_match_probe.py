"""tools/match_probe.py —— 识图探针的纯逻辑与交互回路。

探针要抓屏、要游戏窗口，这里只覆盖不碰屏幕的那部分：输入解析、名字解析、候选列表、
报告排版，以及整条交互回路（截图源与 `input` 都换替身）。抓屏与匹配分别由
`utils/drivers/screen.py`、`utils/vision/probe.py` 自己的测试覆盖。
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import tools.match_probe as match_probe
from utils.core.thresholds import DEFAULT_MATCH
from utils.drivers.screen import CAPTURE_PRINTWINDOW, CAPTURE_SCREENGRAB

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestParseInput:
    def test_name_only_falls_back_to_the_default_threshold(self):
        assert match_probe.parse_input("transfer") == ("transfer", DEFAULT_MATCH)

    def test_explicit_threshold_wins(self):
        assert match_probe.parse_input("transfer 0.93") == ("transfer", 0.93)

    def test_extra_spaces_are_tolerated(self):
        assert match_probe.parse_input("  transfer   0.93  ") == ("transfer", 0.93)

    @pytest.mark.parametrize(
        "text",
        ["", "   ", "a b c", "a abc", "a 1.5", "a -0.1"],
        ids=["空", "全空格", "三个参数", "阈值不是数字", "阈值超过 1", "阈值为负"],
    )
    def test_bad_input_raises_value_error(self, text):
        with pytest.raises(ValueError):
            match_probe.parse_input(text)


class TestResolveTemplate:
    def test_bare_name_is_looked_up_in_the_picture_dir(self, tmp_path):
        (tmp_path / "transfer.webp").write_bytes(b"")

        assert match_probe.resolve_template("transfer", str(tmp_path)) == os.path.join(
            str(tmp_path), "transfer.webp"
        )

    def test_suffix_is_optional_even_for_png_only_images(self, tmp_path):
        """名字没写后缀时不该只试 webp —— 库里既有 webp 也有 png。"""
        (tmp_path / "sw.png").write_bytes(b"")

        assert match_probe.resolve_template("sw", str(tmp_path)) == os.path.join(
            str(tmp_path), "sw.png"
        )

    def test_wrong_suffix_still_finds_the_sibling(self, tmp_path):
        """敲成 .png 但库里只有 .webp —— 按图库自己的优先级找回 webp。"""
        (tmp_path / "transfer.webp").write_bytes(b"")

        assert match_probe.resolve_template("transfer.png", str(tmp_path)) == os.path.join(
            str(tmp_path), "transfer.webp"
        )

    def test_explicit_path_is_used_as_is(self, tmp_path):
        target = tmp_path / "custom.webp"
        target.write_bytes(b"")

        assert match_probe.resolve_template(str(target), "unused-dir") == str(target)

    def test_unknown_name_returns_a_nonexistent_path(self, tmp_path):
        result = match_probe.resolve_template("nope", str(tmp_path))

        assert not os.path.isfile(result), "找不到时要返回不存在的路径，由调用方报错"


class TestSuggestNames:
    def test_matches_on_substring_without_extension(self, tmp_path):
        (tmp_path / "transfer.webp").write_bytes(b"")
        (tmp_path / "F_Teleport.webp").write_bytes(b"")

        assert match_probe.suggest_names("trans", str(tmp_path)) == ["transfer"]

    def test_is_case_insensitive(self, tmp_path):
        (tmp_path / "F_Teleport.webp").write_bytes(b"")

        assert match_probe.suggest_names("teleport", str(tmp_path)) == ["F_Teleport"]

    def test_limit_truncates(self, tmp_path):
        for name in ("a1", "a2", "a3"):
            (tmp_path / f"{name}.webp").write_bytes(b"")

        assert match_probe.suggest_names("a", str(tmp_path), limit=2) == ["a1", "a2"]

    def test_finds_images_in_subdirectories(self, tmp_path):
        (tmp_path / "map_ui").mkdir()
        (tmp_path / "map_ui" / "transfer.webp").write_bytes(b"")

        assert match_probe.suggest_names("trans", str(tmp_path)) == ["transfer"]

    def test_sample_output_directory_is_ignored(self, tmp_path):
        (tmp_path / "new_pic" / "20261024").mkdir(parents=True)
        (tmp_path / "new_pic" / "20261024" / "transfer.webp").write_bytes(b"")

        assert match_probe.suggest_names("trans", str(tmp_path)) == []

    def test_missing_directory_yields_nothing(self, tmp_path):
        assert match_probe.suggest_names("x", str(tmp_path / "nope")) == []


class TestPickFromCandidates:
    """`?片段` 之后的下一次输入可以是一个编号。"""

    def test_a_valid_index_selects(self):
        assert match_probe.pick_from_candidates(["a", "b"], "2") == "b"

    def test_surrounding_spaces_are_tolerated(self):
        assert match_probe.pick_from_candidates(["a", "b"], " 1 ") == "a"

    @pytest.mark.parametrize("text", ["0", "3", "abc", "", "  ", "-1", "1.0"])
    def test_out_of_range_or_non_numeric_is_not_a_pick(self, text):
        assert match_probe.pick_from_candidates(["a", "b"], text) is None

    def test_nothing_pending_never_picks(self):
        assert match_probe.pick_from_candidates([], "1") is None


class TestPrintCandidates:
    def test_numbers_the_hits(self, tmp_path, capsys):
        for name in ("battle_esc_check", "battle_start"):
            (tmp_path / f"{name}.webp").write_bytes(b"")

        shown = match_probe.print_candidates("battle", str(tmp_path))

        out = capsys.readouterr().out
        assert shown == ["battle_esc_check", "battle_start"]
        assert "  1. battle_esc_check" in out
        assert "  2. battle_start" in out
        assert "输编号选中" in out

    def test_says_so_when_nothing_matches(self, tmp_path, capsys):
        assert match_probe.print_candidates("nope", str(tmp_path)) == []
        assert "没有名字含" in capsys.readouterr().out

    def test_truncates_and_says_how_many_are_left(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(match_probe, "SUGGEST_LIMIT", 2)
        for index in range(5):
            (tmp_path / f"p{index}.webp").write_bytes(b"")

        shown = match_probe.print_candidates("p", str(tmp_path))

        assert len(shown) == 2, "只列出上限那么多，选得到的也就是这些"
        assert "还有 3 张没列出" in capsys.readouterr().out


def measurement(**overrides):
    """一份 `probe.measure()` 会返回的 dict，数字取自一次真实测量的形状。"""
    data = {
        "frame": np.zeros((1080, 1920, 3), np.uint8),
        "region": (0, 0, 1920, 1080),
        "template_shape": (20, 50, 3),
        "box": (812, 640, 862, 660),
        "padded_box": (807, 635, 867, 665),
        "center": (837, 650),
        "score": 0.9312,
        "second": 0.8901,
        "threshold": 0.93,
        "margin": 0.0012,
        "passed": True,
        "exact_offset": (812, 640, -1058, -420),
        "fuzzy_offset": (807, 635, -1053, -415),
        "fuzzy_padding": 5,
        "pad_applied": 5,
        "capture_source": CAPTURE_PRINTWINDOW,
    }
    data.update(overrides)
    return data


class TestFormatReport:
    @staticmethod
    def _report(**overrides):
        return match_probe.format_report(
            measurement(**overrides), "transfer", "picture/transfer.webp"
        )

    def test_reports_the_exact_offset_of_the_matched_box(self):
        # 右/下两边是负增量：offset 是「给搜索区域加的增量」，不是框的绝对坐标
        assert "offset=(812, 640, -1058, -420)" in self._report()

    def test_reports_the_fuzzy_offset(self):
        report = self._report()

        assert "offset=(807, 635, -1053, -415)" in report
        assert "四边各外扩 5px" in report

    def test_says_when_the_padding_hit_the_frame_edge(self):
        report = self._report(pad_applied=2)

        assert "只扩了 2px" in report

    def test_reports_the_match_center_which_is_where_clicks_land(self):
        assert "(837, 650)" in self._report()

    def test_marks_a_thin_margin(self):
        """余量 0.0012 是该报警的阈值 —— 游戏一更新就碎。"""
        report = self._report()

        assert "余量 +0.0012" in report
        assert "余量 < 0.03" in report

    def test_a_wide_margin_is_not_flagged(self):
        report = self._report(score=0.99, margin=0.09)

        assert "余量 +0.0900" in report
        assert "⚠" not in report

    def test_says_so_when_the_threshold_is_missed(self):
        assert "[未达阈值]" in self._report(score=0.85, passed=False)

    def test_warns_when_the_frame_came_from_the_screen(self):
        """回退抓屏幕拿到的可能根本不是游戏画面 —— 数字再好看也不能信。"""
        report = self._report(capture_source=CAPTURE_SCREENGRAB)

        assert "屏幕抓取" in report
        assert "盖住它的窗口" in report

    def test_no_such_warning_for_a_printwindow_frame(self):
        assert "屏幕抓取" not in self._report()


    def test_reports_the_call_site_region_when_registered(self):
        report = self._report(
            strategy="color",
            areas=[
                {"area": "full", "label": "全屏", "offset": (0, 0, 0, 0),
                 "region": (0, 0, 1920, 1080), "error": None, "comparisons": []},
                {"area": "search", "label": "调用点", "offset": (1843, 0, -35, 0),
                 "region": (1843, 0, 1885, 1080), "error": None,
                 "comparisons": [{"strategy": "color", "score": 0.82,
                                  "margin": -0.11, "passed": False,
                                  "box": (1848, 400, 1898, 420)}]},
            ],
        )

        assert "调用点" in report
        assert "offset=(1843, 0, -35, 0)" in report
        assert "0.8200" in report
        assert "[未达阈值]" in report

    def test_no_call_site_section_without_a_registered_region(self):
        assert "调用点" not in self._report()

    def test_warns_when_the_registered_region_is_invalid(self):
        report = self._report(
            areas=[{"area": "search", "label": "调用点", "offset": (9, 9, 9, 9),
                    "region": (0, 0, 1920, 1080), "comparisons": [],
                    "error": "四边增量把搜索区域裁成了空，运行时同样会退回全屏搜索"}],
        )

        assert "⚠" in report
        assert "退回全屏" in report

# ---------------------------------------------------------------------------
# 抓屏与交互回路：截图源换替身，不需要游戏窗口
# ---------------------------------------------------------------------------


def structured_template():
    """有结构的模板。纯色模板配 TM_CCORR_NORMED 会到处都打 1.0，测不出东西。"""
    template = np.zeros((16, 24, 3), np.uint8)
    template[4:12, 6:18] = (255, 128, 0)
    return template


def frame_with(template, left=812, top=640):
    frame = np.zeros((1080, 1920, 3), np.uint8)
    height, width = template.shape[:2]
    frame[top : top + height, left : left + width] = template
    return frame


def write_template(directory, template, name="probe_target"):
    """存成 png。PIL 写的是 RGB，所以先翻成 RGB 再存 —— `get_img` 读回来才是原样。"""
    path = directory / f"{name}.png"
    Image.fromarray(template[:, :, ::-1].copy()).save(path)
    return path


class StubScreen:
    """截图源替身：直接给一帧合成画面，并记下每次被要求传了什么。"""

    def __init__(self, frame, source=CAPTURE_PRINTWINDOW, region=(0, 0, 1920, 1080)):
        self.frame = frame
        self.region = region
        self.last_capture_source = source
        self.calls = []

    def cal_screenshot(self):
        return self.region

    def take_screenshot(self, offset=(0, 0, 0, 0), max_retries=50, retry_interval=2):
        self.calls.append(
            {
                "offset": offset,
                "max_retries": max_retries,
                "retry_interval": retry_interval,
            }
        )
        return self.frame, *self.region


def stub_window(hwnd=1234, reason="没检测到游戏窗口 —— 先把游戏打开再跑本工具。"):
    """`match_probe.Window` 的替身：只实现探针用到的三个方法。

    `hwnd=None` 表示没找到游戏窗口，此时会问到 `describe_missing_window`。
    """
    return SimpleNamespace(
        find_window_hwnd=lambda: hwnd,
        attach=lambda handle: f"window-{handle}",
        describe_missing_window=lambda: reason,
    )


class TestRecognize:
    def test_missing_image_reports_instead_of_crashing(self, tmp_path, capsys):
        screen = StubScreen(frame_with(structured_template()))

        outcome = match_probe.recognize(screen, "nope", 0.9, str(tmp_path))

        assert outcome == match_probe.OUTCOME_MISSING
        assert "找不到图片" in capsys.readouterr().out
        assert screen.calls == [], "图都没找到，不该去抓屏"

    def test_measures_a_template_placed_at_a_known_spot(self, tmp_path, capsys):
        template = structured_template()
        write_template(tmp_path, template)
        screen = StubScreen(frame_with(template))

        outcome = match_probe.recognize(screen, "probe_target", 0.9, str(tmp_path))

        assert outcome == match_probe.OUTCOME_MEASURED
        out = capsys.readouterr().out
        # 812+24 = 836，836-1920 = -1084；640+16 = 656，656-1080 = -424
        assert "offset=(812, 640, -1084, -424)" in out
        assert "匹配中心  (824, 648)" in out

    def test_a_frame_without_the_template_misses_the_threshold(self, tmp_path, capsys):
        write_template(tmp_path, structured_template())
        screen = StubScreen(np.zeros((1080, 1920, 3), np.uint8))

        assert match_probe.recognize(
            screen, "probe_target", 0.9, str(tmp_path)
        ) == match_probe.OUTCOME_MEASURED
        assert "[未达阈值]" in capsys.readouterr().out

    def test_a_near_miss_name_lists_the_candidates(self, tmp_path, capsys):
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()))

        assert match_probe.recognize(
            screen, "probe_targe", 0.9, str(tmp_path)
        ) == match_probe.OUTCOME_MISSING
        assert "名字相近的有：probe_target" in capsys.readouterr().out

    def test_an_unreadable_image_is_reported_not_fed_to_cv2(self, tmp_path, capsys):
        """0 字节、或者根本不是图片的文件 —— 不能一路喂到 matchTemplate 才炸（R12）。"""
        (tmp_path / "broken.webp").write_bytes(b"")
        screen = StubScreen(frame_with(structured_template()))

        outcome = match_probe.recognize(screen, "broken", 0.9, str(tmp_path))

        assert outcome == match_probe.OUTCOME_MISSING
        assert "图片读不出来" in capsys.readouterr().out
        assert screen.calls == [], "图都读不出来，不该去抓屏"

    def test_fails_fast_instead_of_waiting_a_hundred_seconds(self, tmp_path):
        """take_screenshot 默认 50 次 × 2 秒 —— 探针是人手动触发的，等不起。"""
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()))

        match_probe.recognize(screen, "probe_target", 0.9, str(tmp_path))

        assert screen.calls[-1]["max_retries"] <= 5
        assert screen.calls[-1]["retry_interval"] <= 1

    def test_a_screengrab_frame_is_discarded_by_default(self, tmp_path, capsys):
        """回退抓屏幕拿到的可能根本不是游戏画面，默认直接丢掉。"""
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()), source=CAPTURE_SCREENGRAB)

        outcome = match_probe.recognize(screen, "probe_target", 0.9, str(tmp_path))

        assert outcome == match_probe.OUTCOME_REJECTED
        out = capsys.readouterr().out
        assert "从屏幕上抓的" in out
        assert "匹配度" not in out, "丢掉的帧不该出报告"

    def test_a_printwindow_frame_passes_by_default(self, tmp_path, capsys):
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()))

        outcome = match_probe.recognize(screen, "probe_target", 0.9, str(tmp_path))

        assert outcome == match_probe.OUTCOME_MEASURED
        assert "匹配度" in capsys.readouterr().out

    def test_a_screengrab_frame_can_be_allowed_explicitly(self, tmp_path, capsys):
        """环境本来就拿不到游戏窗口像素时，留一个出口。"""
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()), source=CAPTURE_SCREENGRAB)

        outcome = match_probe.recognize(
            screen, "probe_target", 0.9, str(tmp_path), allow_fallback=True
        )

        assert outcome == match_probe.OUTCOME_MEASURED
        assert "screengrab" in capsys.readouterr().out

    def test_preview_pops_a_window_when_asked(self, tmp_path, monkeypatch):
        """弹窗在无显示环境里跑不了，所以只验「确实把图画出来了」。"""
        shown = []
        monkeypatch.setattr(match_probe.viewer, "show", shown.append)
        monkeypatch.setattr(match_probe.viewer, "pump", lambda: None)
        monkeypatch.setattr(match_probe.viewer, "wait_key", lambda: 13)
        monkeypatch.setattr(match_probe.viewer, "close_all", lambda: None)
        write_template(tmp_path, structured_template())
        screen = StubScreen(frame_with(structured_template()))

        match_probe.recognize(screen, "probe_target", 0.9, str(tmp_path), preview=True)

        assert len(shown) == 1
        assert shown[0].ndim == 3, "画的是一张图，不是 None"


class TestMainLoop:
    """交互回路：`ScreenSource` 与 `Window` 换替身、`input` 换脚本。"""

    @pytest.fixture
    def wired(self, monkeypatch, capsys):
        monkeypatch.setattr(
            match_probe,
            "Window",
            stub_window(),
        )
        monkeypatch.setattr(
            match_probe, "ScreenSource", lambda window=None: StubScreen(np.zeros((1080, 1920, 3), np.uint8))
        )
        return capsys

    @staticmethod
    def scripted_input(monkeypatch, *answers):
        """按脚本回答 input()；脚本用尽就抛 EOFError，让 main 退出而不是挂死。

        提示语由这个替身自己打出来 —— 真的 `input()` 也会把 prompt 写进 stdout，
        少了这一步就断言不到「当前图片」这类提示。
        """
        pending = list(answers)

        def fake_input(prompt=""):
            print(prompt, end="")
            if not pending:
                raise EOFError
            return pending.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)

    def test_quit_returns_zero(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "q")

        assert match_probe.main() == 0

    def test_end_of_input_returns_zero(self, wired, monkeypatch):
        self.scripted_input(monkeypatch)

        assert match_probe.main() == 0

    def test_empty_input_before_any_name_asks_for_one(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "", "q")

        assert match_probe.main() == 0
        assert "请先输入图片名" in wired.readouterr().out

    def test_bad_threshold_is_reported_without_quitting(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "transfer 9", "q")

        assert match_probe.main() == 0
        assert "阈值应落在 0~1" in wired.readouterr().out

    def test_question_mark_lists_candidates(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "?trans", "q")

        assert match_probe.main() == 0
        assert "名字含「trans」的图片" in wired.readouterr().out

    def test_a_number_picks_from_the_candidates(self, tmp_path, monkeypatch, capsys):
        """?probe 列出候选之后，敲 2 直接选中第二个 —— 不用把名字抄一遍。"""
        picture_dir = tmp_path / "picture"
        picture_dir.mkdir()
        template = structured_template()
        write_template(picture_dir, template)
        (picture_dir / "probe_aaa.webp").write_bytes(b"")  # 排序在前，把 2 让给 target
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(match_probe, "Window", stub_window())
        monkeypatch.setattr(
            match_probe, "ScreenSource", lambda window=None: StubScreen(frame_with(template))
        )
        self.scripted_input(monkeypatch, "?probe", "2", "q")

        assert match_probe.main() == 0
        out = capsys.readouterr().out
        assert "选中：probe_target" in out
        assert "匹配度" in out

    def test_p_toggles_the_preview(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "p", "q")

        assert match_probe.main() == 0
        assert "弹窗预览已开启" in wired.readouterr().out

    def test_s_can_allow_the_screen_fallback(self, wired, monkeypatch):
        self.scripted_input(monkeypatch, "s", "q")

        assert match_probe.main() == 0
        assert "已允许屏幕回退帧" in wired.readouterr().out

    def test_a_missing_image_does_not_become_the_current_one(self, wired, monkeypatch):
        """输错名字后回车不该一直重试那个错名字 —— 它不该被记成「当前图片」。"""
        self.scripted_input(monkeypatch, "nope", "", "q")

        assert match_probe.main() == 0
        out = wired.readouterr().out
        assert "找不到图片" in out
        assert "（必填）" in out.split("找不到图片")[-1], "下一次提示还应是「必填」"

    def test_a_found_image_becomes_the_current_one_and_repeats_on_enter(
        self, tmp_path, monkeypatch, capsys
    ):
        """主路径：命中一次之后，回车用同一张图重新抓一帧。

        `PICTURE_DIR` 是相对路径 "picture"，所以切 cwd 而不是改常量 ——
        顺带验的正是「工具必须在仓库根目录跑」这条真实约定。
        """
        picture_dir = tmp_path / "picture"
        picture_dir.mkdir()
        template = structured_template()
        write_template(picture_dir, template)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(match_probe, "Window", stub_window())
        monkeypatch.setattr(
            match_probe, "ScreenSource", lambda window=None: StubScreen(frame_with(template))
        )
        self.scripted_input(monkeypatch, "probe_target", "", "q")

        assert match_probe.main() == 0
        out = capsys.readouterr().out
        assert out.count("匹配中心") == 2, "回车要再测一帧，不是只测一次"
        assert "（probe_target）" in out, "命中的图要成为「当前图片」"

    def test_a_failing_screenshot_is_reported_without_quitting(
        self, tmp_path, monkeypatch, capsys
    ):
        """抓屏失败（窗口不可见等）只报一条，不能把整个工具带走。"""
        picture_dir = tmp_path / "picture"
        picture_dir.mkdir()
        write_template(picture_dir, structured_template())

        class FailingScreen(StubScreen):
            def take_screenshot(self, **kwargs):
                raise RuntimeError("窗口不可见")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(match_probe, "Window", stub_window())
        monkeypatch.setattr(
            match_probe, "ScreenSource", lambda window=None: FailingScreen(np.zeros((4, 4, 3), np.uint8))
        )
        self.scripted_input(monkeypatch, "probe_target", "q")

        assert match_probe.main() == 0
        assert "识别失败：窗口不可见" in capsys.readouterr().out


class TestStartup:
    def test_warns_when_the_capture_region_is_off_the_base_resolution(
        self, monkeypatch, capsys
    ):
        """R8：分辨率不对时截图区域会算歪，先提醒再继续。"""
        monkeypatch.setattr(match_probe, "Window", stub_window())
        monkeypatch.setattr(
            match_probe,
            "ScreenSource",
            lambda window=None: StubScreen(np.zeros((4, 4, 3), np.uint8), region=(0, 0, 1280, 720)),
        )
        TestMainLoop.scripted_input(monkeypatch, "q")

        assert match_probe.main() == 0
        assert "⚠ 当前截图区域 1280×720" in capsys.readouterr().out

    def test_refuses_to_run_without_the_game(self, monkeypatch, capsys):
        """拿不到游戏窗口就直接退出，绝不落到构造 `Window()` 那条路上。

        那条路会把鼠标挪到窗口中心，游戏没开时还会启动游戏并连点 30 秒。
        """

        def must_not_construct(window=None):
            pytest.fail("没检测到窗口时不该构造 ScreenSource")

        monkeypatch.setattr(match_probe, "ScreenSource", must_not_construct)
        monkeypatch.setattr(match_probe, "Window", stub_window(hwnd=None))

        assert match_probe.main() == 1
        out = capsys.readouterr().out
        assert "没检测到游戏窗口" in out
        assert "不会动你的鼠标" in out

    def test_the_screen_source_is_bound_to_the_found_window(self, tmp_path, monkeypatch, capsys):
        """探针必须挂在**找到的那个窗口**上抓帧，而不是让 ScreenSource 自己兜底。"""
        seen = {}

        def remember(window=None):
            seen["window"] = window
            return StubScreen(np.zeros((1080, 1920, 3), np.uint8))

        monkeypatch.setattr(match_probe, "Window", stub_window(hwnd=7788))
        monkeypatch.setattr(match_probe, "ScreenSource", remember)
        TestMainLoop.scripted_input(monkeypatch, "q")

        assert match_probe.main() == 0
        assert seen["window"] == "window-7788"

    def test_a_failing_window_lookup_is_reported(self, monkeypatch, capsys):
        def boom():
            raise RuntimeError("枚举窗口失败")

        monkeypatch.setattr(
            match_probe,
            "Window",
            SimpleNamespace(find_window_hwnd=boom, attach=lambda hwnd: None),
        )

        assert match_probe.main() == 1
        assert "查找游戏窗口失败：枚举窗口失败" in capsys.readouterr().out


class TestRunnableAsAScript:
    """`py tools/match_probe.py` 这条路径要单独钉住。

    踩过的坑：工具本身没问题、从测试里 `import tools.match_probe` 也没问题，但用户
    双击 .bat 时第一行 import 就报 `ModuleNotFoundError: No module named 'utils'`。
    原因是按路径跑时 sys.path[0] 是 `tools/` 而不是仓库根 —— 而**此前每次验证都是先
    import 再调 main()**，sys.path 里早就有仓库根了，这条路径一次都没走到过。

    这里用子进程把 sys.path 摆成按路径跑的样子：只留 `tools/`，不含仓库根。
    """

    def test_imports_when_only_tools_is_on_the_path(self, tmp_path):
        # `-c` 时 sys.path[0] 是 ''（即 cwd）；换成 tools/ 就复现了脚本的处境，
        # 同时把 cwd 从搜索路径里挤掉 —— 仓库根于是无处可寻。
        code = (
            f"import sys; sys.path[0] = {str(REPO_ROOT / 'tools')!r};"
            " import match_probe; print('import ok')"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,  # 日志目录别落在仓库里
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, result.stderr
        assert "import ok" in result.stdout
