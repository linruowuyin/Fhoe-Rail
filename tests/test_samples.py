"""utils/vision/samples.py —— 跑图时的图片样本收集与「未使用图片」报告。

全程替身：不连游戏、也不碰仓库里真正的 `picture/`（那是受版本管理的样板图，测试只能读，
不该往里写东西）。所有写盘都指向 tmp 目录。
"""

import json
import os
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import utils.vision.samples as samples


def template(width=24, height=16):
    patch = np.zeros((height, width, 3), np.uint8)
    patch[2 : height - 2, 4 : width - 4] = (255, 128, 0)
    return patch


def frame_with(tpl, left=200, top=100):
    frame = np.zeros((1080, 1920, 3), np.uint8)
    height, width = tpl.shape[:2]
    frame[top : top + height, left : left + width] = tpl
    return frame


@pytest.fixture
def picture_dir(tmp_path, monkeypatch):
    """假的 `picture/` + 指向它的产物目录。默认**开关是关的**。"""
    root = tmp_path / "picture"
    root.mkdir()
    for name in ("alpha.webp", "beta.webp"):
        (root / name).write_bytes(b"")
    monkeypatch.setattr(samples, "PICTURE_DIR", str(root))
    monkeypatch.setattr(samples, "SAMPLES_DIR", str(root / "new_pic"))
    samples.reset()
    yield root
    samples.reset()


@pytest.fixture
def collecting(monkeypatch):
    """把开关打开。"""
    monkeypatch.setattr(
        samples,
        "ConfigurationManager",
        lambda: SimpleNamespace(config_file={"collect_picture_samples": True}),
    )


def alpha_path(picture_dir):
    return os.path.join(str(picture_dir), "alpha.webp")


def seen_json():
    path = os.path.join(samples.SAMPLES_DIR, "_seen.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sample_path(name):
    """样本图落在**本轮目录**里：`new_pic/<年月日_时分秒>/`。"""
    return os.path.join(samples.run_dir(), name)


def report_text():
    """读报告。它是清单的派生视图，跑图里由「每张地图跑完」触发 —— 这里手动触发一次。"""
    samples.write_report()
    path = os.path.join(samples.SAMPLES_DIR, samples.REPORT_FILENAME)
    with open(path, encoding="utf-8") as f:
        return f.read()


def unused_section(report):
    return report.split("=== 未使用")[1].split("===")[1]


def _capture_sleeps(monkeypatch):
    """把 samples 模块里的 `time` 换成只记账的替身，返回被 sleep 的那些秒数。

    换的是**模块里的 `time` 属性**，不是 stdlib 的 `time.sleep` —— 后者会波及整个进程
    （仓库里踩过这个坑）。
    """
    sleeps = []
    monkeypatch.setattr(
        samples,
        "time",
        SimpleNamespace(
            sleep=lambda seconds: sleeps.append(seconds), monotonic=time.monotonic
        ),
    )
    return sleeps


class TestEnabled:
    def test_off_when_the_config_says_false(self, monkeypatch):
        monkeypatch.setattr(
            samples,
            "ConfigurationManager",
            lambda: SimpleNamespace(config_file={"collect_picture_samples": False}),
        )

        assert samples.enabled() is False

    def test_on_when_the_config_says_true(self, collecting):
        assert samples.enabled() is True

    def test_a_broken_config_counts_as_off(self, monkeypatch):
        """读配置失败不能把跑图带崩 —— 按关闭处理。"""

        def boom():
            raise RuntimeError("配置读不出来")

        monkeypatch.setattr(samples, "ConfigurationManager", boom)

        assert samples.enabled() is False


class TestPictureNames:
    def test_lists_recursively_and_skips_new_pic(self, picture_dir):
        (picture_dir / "ui").mkdir()
        (picture_dir / "ui" / "gamma.webp").write_bytes(b"")
        folder = picture_dir / "new_pic" / "20261024"
        folder.mkdir(parents=True)
        (folder / "delta.webp").write_bytes(b"")

        assert samples._picture_names() == ["alpha.webp", "beta.webp", "gamma.webp"]


class TestWhenDisabled:
    """开关关着时一个字节都不该写。"""

    def test_note_loaded_writes_nothing(self, picture_dir):
        samples.note_loaded(alpha_path(picture_dir))

        assert not os.path.exists(samples.SAMPLES_DIR)

    def test_note_match_writes_nothing(self, picture_dir):
        samples.note_match(
            alpha_path(picture_dir),
            frame_with(template()),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.99,
        )

        assert not os.path.exists(samples.SAMPLES_DIR)


class TestSampleImages:
    def test_first_match_writes_both_files(self, picture_dir, collecting):
        tpl = template()

        samples.note_match(
            alpha_path(picture_dir),
            frame_with(tpl),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.97,
        )

        assert os.path.isfile(sample_path("alpha.webp"))
        assert os.path.isfile(sample_path("alpha-newcheck.webp"))

    def test_the_plain_crop_is_the_matched_region_itself(self, picture_dir, collecting):
        """存下来的那一块尺寸 = 模板尺寸，内容就是游戏画面里的那一块。"""
        tpl = template()

        samples.note_match(
            alpha_path(picture_dir),
            frame_with(tpl, left=200, top=100),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.97,
        )

        crop = cv2.imread(sample_path("alpha.webp"))

        assert crop.shape == tpl.shape
        assert np.array_equal(crop, tpl), "无损 webp，取回来必须一个像素都不差"

    def test_the_plain_crop_follows_the_capture_region_offset(self, picture_dir, collecting):
        """帧的原点不一定在屏幕 (0,0) —— 裁的时候要把区域偏移减掉。"""
        tpl = template()

        samples.note_match(
            alpha_path(picture_dir),
            frame_with(tpl, left=20, top=10),
            (300, 400, 2220, 1480),  # 帧原点在屏幕 (300,400)
            (320, 410, 344, 426),  # 同一块，换算成屏幕绝对坐标
            0.97,
        )

        crop = cv2.imread(sample_path("alpha.webp"))

        assert np.array_equal(crop, tpl)

    def test_the_check_image_carries_both_boxes(self, picture_dir, collecting):
        from utils.vision.probe import BOX_COLOR_EXACT, BOX_COLOR_PADDED

        tpl = template()

        samples.note_match(
            alpha_path(picture_dir),
            frame_with(tpl),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.97,
        )

        check = cv2.imread(sample_path("alpha-newcheck.webp"))

        assert check.shape[0] > tpl.shape[0] and check.shape[1] > tpl.shape[1], "带了上下文"
        for color in (BOX_COLOR_EXACT, BOX_COLOR_PADDED):
            assert np.any(np.all(check == np.array(color, np.uint8), axis=-1)), (
                f"没找到颜色 {color}"
            )

    def test_the_same_image_is_only_sampled_once_per_run(self, picture_dir, collecting):
        first_frame = frame_with(template(), left=200, top=100)
        samples.note_match(
            alpha_path(picture_dir), first_frame, (0, 0, 1920, 1080), (200, 100, 224, 116), 0.97
        )
        plain = sample_path("alpha.webp")
        with open(plain, "rb") as f:
            first_bytes = f.read()

        # 同一轮里第二次命中的是画面里**另一个位置** —— 若被重写，内容必然不同
        second_frame = frame_with(template(), left=900, top=700)
        samples.note_match(
            alpha_path(picture_dir), second_frame, (0, 0, 1920, 1080), (900, 700, 924, 716), 0.98
        )

        with open(plain, "rb") as f:
            assert f.read() == first_bytes, "同一轮里只采第一次命中"

    def test_each_run_gets_its_own_directory(self, picture_dir, collecting):
        """每轮一个新目录 —— 老图留着，才能横向比对同一张模板在不同轮次里的样子。"""
        samples.note_match(
            alpha_path(picture_dir),
            frame_with(template()),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.97,
        )
        first_dir = samples.run_dir()

        samples.reset()  # 新一轮跑图 = 新进程

        fresh = np.full((16, 24, 3), 200, np.uint8)
        samples.note_match(
            alpha_path(picture_dir), frame_with(fresh), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.98
        )

        assert samples.run_dir() != first_dir
        assert np.array_equal(cv2.imread(os.path.join(first_dir, "alpha.webp")), template())
        assert np.array_equal(cv2.imread(sample_path("alpha.webp")), fresh)

    def test_run_directories_are_named_by_the_clock(self, picture_dir, collecting):
        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.97
        )

        name = os.path.basename(samples.run_dir())

        assert len(name) == len("20261003_153045") and name[8] == "_", f"不像时间戳：{name}"

    def test_a_run_that_samples_nothing_leaves_no_directory(self, picture_dir, collecting):
        """目录是懒建的 —— 只加载没匹配的一轮不该留个空壳。"""
        samples.note_loaded(alpha_path(picture_dir))

        entries = os.listdir(samples.SAMPLES_DIR)

        assert not [e for e in entries if os.path.isdir(os.path.join(samples.SAMPLES_DIR, e))]

    def test_the_ledger_and_report_stay_at_the_top_level(self, picture_dir, collecting):
        """样本在子目录里，清单与报告在外层 —— 报告说的是"历来"，不只是一轮。"""
        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.97
        )
        report_text()  # 触发一次报告生成

        top = os.listdir(samples.SAMPLES_DIR)

        assert samples.SEEN_FILENAME in top
        assert samples.REPORT_FILENAME in top
        assert "alpha.webp" not in top, "样本图该在子目录里"
        assert "alpha.webp" in os.listdir(samples.run_dir())

    def test_the_cumulative_list_survives_a_new_run(self, picture_dir, collecting):
        """覆盖的是样本图；「哪些图被用到」是累计的，不该跟着重置。"""
        samples.note_loaded(alpha_path(picture_dir))

        samples.reset()

        assert "alpha.webp" in seen_json()

    def test_below_the_floor_is_not_a_sample(self, picture_dir, collecting):
        samples.note_match(
            alpha_path(picture_dir),
            frame_with(template()),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            samples.SAMPLE_FLOOR,  # 严格大于才算
        )

        assert not os.path.exists(samples.SAMPLES_DIR)

    def test_an_image_without_a_file_is_skipped(self, picture_dir, collecting):
        """反色 / 旋转造出来的数组没有对应文件，path_of 给的是 None。"""
        samples.note_match(None, frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.99)

        assert not os.path.exists(samples.SAMPLES_DIR)

    def test_a_broken_frame_does_not_raise(self, picture_dir, collecting):
        """裁不出东西（框在帧外）也不能把跑图带崩。"""
        samples.note_match(
            alpha_path(picture_dir),
            np.zeros((10, 10, 3), np.uint8),
            (0, 0, 10, 10),
            (900, 700, 924, 716),
            0.99,
        )

        assert os.path.isfile(os.path.join(samples.SAMPLES_DIR, "_seen.json"))


class TestScores:
    def test_records_the_score_and_which_map_it_came_from(self, picture_dir, collecting):
        samples.set_current_map("map_1-2_3.json", "主控舱段-1")

        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.9312
        )

        entry = seen_json()["alpha.webp"]["scores"]["map_1-2_3.json"]
        assert entry["score"] == pytest.approx(0.9312)
        assert entry["name"] == "主控舱段-1"

    def test_matches_outside_a_map_are_labelled_as_such(self, picture_dir, collecting):
        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.99
        )

        assert samples.NO_MAP in seen_json()["alpha.webp"]["scores"]

    def test_keeps_the_best_score_per_map(self, picture_dir, collecting):
        samples.set_current_map("map_1-2_3.json", "主控舱段-1")
        for score in (0.93, 0.96):
            samples.note_match(
                alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), score
            )

        assert seen_json()["alpha.webp"]["scores"]["map_1-2_3.json"]["score"] == pytest.approx(0.96)

    def test_leaving_the_map_stops_attributing_to_it(self, picture_dir, collecting):
        samples.set_current_map("map_1-2_3.json", "主控舱段-1")
        samples.set_current_map("")

        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.99
        )

        assert samples.NO_MAP in seen_json()["alpha.webp"]["scores"]


class TestReport:
    def test_lists_the_files_that_were_never_loaded(self, picture_dir, collecting):
        samples.note_loaded(alpha_path(picture_dir))

        unused = unused_section(report_text())

        assert "beta.webp" in unused
        assert "alpha.webp" not in unused

    def test_counts_add_up(self, picture_dir, collecting):
        samples.note_loaded(alpha_path(picture_dir))

        assert "picture/ 共 2 张；已用到 1 张，未使用 1 张" in report_text()

    def test_low_scores_point_back_at_the_map(self, picture_dir, collecting):
        samples.set_current_map("map_1-2_3.json", "主控舱段-1")
        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.9312
        )

        report = report_text()

        assert "alpha.webp" in report
        assert "map_1-2_3.json" in report and "主控舱段-1" in report

    def test_a_healthy_score_is_not_flagged(self, picture_dir, collecting):
        samples.set_current_map("map_1-2_3.json", "主控舱段-1")
        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.99
        )

        low_section = report_text().split(f"< {samples.LOW_SCORE}")[1]

        assert "（无）" in low_section

    def test_the_basis_is_spelled_out(self, picture_dir, collecting):
        """报告要自己说清是累计口径，否则下次看到会以为是本次运行的。"""
        samples.note_loaded(alpha_path(picture_dir))

        assert "累计" in report_text()
        assert samples.SEEN_FILENAME in report_text()

    def test_loading_accumulates_across_runs(self, picture_dir, collecting):
        samples.note_loaded(alpha_path(picture_dir))
        samples.reset()  # 模拟进程重启（磁盘上的清单留着）
        samples.note_loaded(os.path.join(str(picture_dir), "beta.webp"))

        unused = unused_section(report_text())

        assert "alpha.webp" not in unused, "上一趟用过的还算数"
        assert "beta.webp" not in unused


class TestAFailureNeverKillsTheRun:
    """用户实测撞到过：报告正开着看，跑图被一个 PermissionError 带崩了。

    Windows 上目标文件被别的进程打开着时（没有 FILE_SHARE_DELETE），`os.replace`
    会直接拒绝访问。收集器是**旁路**，任何写盘失败都只能告警，绝不能冒到匹配热路径上。
    """

    @staticmethod
    def _report_path():
        return os.path.join(samples.SAMPLES_DIR, samples.REPORT_FILENAME)

    def test_a_locked_report_does_not_raise(self, picture_dir, collecting):
        report_text()  # 先把报告生成出来，才有东西可占

        with open(self._report_path(), "r", encoding="utf-8"):  # 占着不放，模拟"用户正开着看"
            samples.write_report()

    def test_the_list_is_still_recorded_when_the_report_is_locked(self, picture_dir, collecting):
        """清单是主数据、报告是它的派生视图 —— 报告写不进去，清单照记。"""
        report_text()

        with open(self._report_path(), "r", encoding="utf-8"):
            samples.note_loaded(os.path.join(str(picture_dir), "beta.webp"))
            samples.write_report()

        assert "beta.webp" in seen_json()

    def test_a_locked_report_does_not_leave_a_tmp_behind(self, picture_dir, collecting):
        report_text()

        with open(self._report_path(), "r", encoding="utf-8"):
            samples.write_report()

        assert not os.path.exists(self._report_path() + ".tmp"), "写不成要把临时文件收掉"

    def test_an_unexpected_write_failure_is_swallowed(self, picture_dir, collecting, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("磁盘炸了")

        monkeypatch.setattr(samples, "_save", boom)

        samples.note_match(
            alpha_path(picture_dir), frame_with(template()), (0, 0, 1920, 1080), (200, 100, 224, 116), 0.97
        )
        samples.note_loaded(alpha_path(picture_dir))

    def test_the_log_says_which_file_is_in_the_way(self, picture_dir, collecting, log_records):
        report_text()

        with open(self._report_path(), "r", encoding="utf-8"):
            samples.write_report()

        assert any("占着" in record["message"] for record in log_records)

    def test_a_locked_file_is_not_retried_over_and_over(
        self, picture_dir, collecting, monkeypatch
    ):
        """报告每张地图跑完才刷一次，但万一那一次撞上锁，接下来也不能每次都白等重试。"""
        report_text()
        sleeps = _capture_sleeps(monkeypatch)

        with open(self._report_path(), "r", encoding="utf-8"):
            samples.write_report()
            after_first = len(sleeps)
            samples.write_report()

        assert after_first > 0, "第一次撞上锁时该重试"
        assert len(sleeps) == after_first, "进了冷却期就不该再重试"

    def test_it_tries_again_after_the_cooldown_lapses(
        self, picture_dir, collecting, monkeypatch
    ):
        report_text()

        with open(self._report_path(), "r", encoding="utf-8"):
            samples.write_report()
            assert samples._blocked_until.get(self._report_path(), 0.0) > 0.0, "撞上锁之后该进冷却"

            samples._blocked_until[self._report_path()] = 0.0  # 把冷却拨回过去
            sleeps = _capture_sleeps(monkeypatch)
            samples.write_report()

        assert sleeps, "冷却过了就该再试 —— 不然文件关掉之后报告永远跟不上"


class TestMode:
    """三档：off / single / multi。

    这个键在老配置里是布尔值（那时只有开/关）—— 认下来，免得升级之后"明明开着却不采了"。
    """

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("off", samples.MODE_OFF),
            ("single", samples.MODE_SINGLE),
            ("multi", samples.MODE_MULTI),
            (True, samples.MODE_SINGLE),
            (False, samples.MODE_OFF),
            ("看不懂的值", samples.MODE_OFF),
            (None, samples.MODE_OFF),
        ],
    )
    def test_normalises(self, monkeypatch, raw, expected):
        monkeypatch.setattr(
            samples,
            "ConfigurationManager",
            lambda: SimpleNamespace(config_file={"collect_picture_samples": raw}),
        )

        assert samples.mode() == expected

    def test_enabled_is_just_mode_not_off(self, monkeypatch):
        monkeypatch.setattr(
            samples,
            "ConfigurationManager",
            lambda: SimpleNamespace(config_file={"collect_picture_samples": "multi"}),
        )

        assert samples.enabled() is True


class TestMultiMode:
    """多图：**每次**命中都落，按模板分目录 + 顺序编号 —— 看同一张图在整趟流程里的稳定性。"""

    @pytest.fixture(autouse=True)
    def multi(self, monkeypatch):
        monkeypatch.setattr(
            samples,
            "ConfigurationManager",
            lambda: SimpleNamespace(config_file={"collect_picture_samples": "multi"}),
        )

    @staticmethod
    def _folder(name="alpha"):
        return os.path.join(samples.run_dir(), name)

    @staticmethod
    def _plain_names(folder):
        """只看裁下来那张，不看 `-newcheck` 示意图（排序时 `-` 在 `.` 前面，会插进来）。"""
        return sorted(n for n in os.listdir(folder) if "-newcheck" not in n)

    def _match(self, picture_dir, name="alpha", value=100):
        samples.note_match(
            os.path.join(str(picture_dir), f"{name}.webp"),
            frame_with(np.full((16, 24, 3), value, np.uint8)),
            (0, 0, 1920, 1080),
            (200, 100, 224, 116),
            0.97,
        )

    def test_every_match_lands_on_disk(self, picture_dir):
        for _ in range(3):
            self._match(picture_dir)

        assert len(os.listdir(self._folder())) == 6, "3 次命中 × (原图 + 示意图)"

    def test_they_are_numbered_in_order(self, picture_dir):
        for _ in range(3):
            self._match(picture_dir)

        numbers = [n.split("_")[0] for n in self._plain_names(self._folder())]

        assert numbers == ["0001", "0002", "0003"]

    def test_the_map_and_the_time_are_in_the_name(self, picture_dir):
        samples.set_current_map("map_1-2_3.json", "空间站黑塔-2")

        self._match(picture_dir)

        name = self._plain_names(self._folder())[0]
        assert "map_1-2_3" in name, name
        assert name.endswith(".webp") and name[-10:-5].isdigit(), f"末尾该是 HHMMSS：{name}"

    def test_outside_a_map_is_labelled(self, picture_dir):
        samples.set_current_map("")

        self._match(picture_dir)

        assert "nomap" in self._plain_names(self._folder())[0]

    def test_each_template_gets_its_own_folder_and_its_own_counter(self, picture_dir):
        (picture_dir / "beta.webp").write_bytes(b"")

        self._match(picture_dir)
        self._match(picture_dir, name="beta")
        self._match(picture_dir)

        assert sorted(os.listdir(samples.run_dir())) == ["alpha", "beta"]
        assert [n.split("_")[0] for n in self._plain_names(self._folder())] == ["0001", "0002"]
        assert [n.split("_")[0] for n in self._plain_names(self._folder("beta"))] == ["0001"]

    def test_the_check_image_is_saved_too(self, picture_dir):
        self._match(picture_dir)

        assert any("-newcheck." in n for n in os.listdir(self._folder()))

    def test_the_crop_is_what_was_on_screen(self, picture_dir):
        value = 170

        self._match(picture_dir, value=value)

        crop = cv2.imread(os.path.join(self._folder(), self._plain_names(self._folder())[0]))
        assert np.all(crop == value)


class TestConcurrency:
    def test_two_threads_sample_the_same_image_once(self, picture_dir, collecting, monkeypatch):
        """疾跑检测线程也在匹配，落盘必须串起来。"""
        written = []
        original = samples._write_sample_images
        monkeypatch.setattr(
            samples,
            "_write_sample_images",
            lambda *args: (written.append(1), original(*args))[1],
        )
        frame = frame_with(template())
        threads = [
            threading.Thread(
                target=samples.note_match,
                args=(alpha_path(picture_dir), frame, (0, 0, 1920, 1080), (200, 100, 224, 116), 0.97),
            )
            for _ in range(4)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(written) == 1, "只该落一次盘"
