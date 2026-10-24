"""utils/flows/orientation.py —— 视角校准。

识别部分（HSV 取箭头、360 度暴力匹配）在 vision/arrow.py，不在这里测。这里测两样东西：
角度换算那三个纯函数（零替身），以及 convergence 循环与 set_angle 的编排。
"""

from types import SimpleNamespace

import pytest

import utils.flows.orientation as orientation_module
from utils.flows.orientation import (
    MAX_ALIGN_TRIES,
    Orientation,
    median_filtered,
    signed_rotation_to,
    unwrap_angle_delta,
)


class TestSignedRotationTo:
    """cal_ang 给 0..359，鼠标要按反方向转，并折到 (-180, 180]。"""

    @pytest.mark.parametrize(
        "ang,expected",
        [
            (90, -90),
            (180, -180),
            (270, 90),
            (359, 1),
            (1, -1),
        ],
    )
    def test_flips_and_wraps(self, ang, expected):
        assert signed_rotation_to(ang) == expected

    def test_zero_becomes_a_tiny_nonzero(self):
        """0 会让调用方的 while 空转，所以替换成极小值。"""
        assert signed_rotation_to(0) == 1e-9
        assert signed_rotation_to(0) != 0


class TestUnwrapAngleDelta:
    """朝一个方向转却读出反号，说明中间跨了 0 度。"""

    def test_positive_direction_with_a_negative_reading(self):
        assert unwrap_angle_delta(-350, 60) == 10

    def test_negative_direction_with_a_positive_reading(self):
        assert unwrap_angle_delta(350, -60) == -10

    def test_readings_already_on_the_right_side_are_untouched(self):
        assert unwrap_angle_delta(10, 60) == 10
        assert unwrap_angle_delta(-10, -60) == -10

    def test_zero_direction_counts_as_positive(self):
        assert unwrap_angle_delta(-5, 0) == 355


class TestMedianFiltered:
    def test_empty_stays_empty(self):
        assert median_filtered([]) == []

    def test_keeps_the_cluster(self):
        assert median_filtered([10, 10, 10]) == [10, 10, 10]

    def test_drops_the_outlier(self):
        assert median_filtered([10, 10, 100]) == [10, 10]


class FakeArrow:
    """按顺序吐出 cal_ang 的读数。take_arrow 只回一个记号，不消耗读数。"""

    def __init__(self, reads):
        self.reads = list(reads)

    def take_arrow(self, img):
        return "ARROW"

    def cal_ang(self, img, arrow_img, begin_img):
        assert self.reads, "cal_ang 被调用次数超出脚本"
        return self.reads.pop(0)


@pytest.fixture
def build(make_instance, monkeypatch):
    """造一个不碰屏幕、不真等待的 Orientation。"""

    def _build(reads, **attrs):
        recorder = SimpleNamespace(
            slept=[], mouse=[], walked=[], written=[]
        )
        monkeypatch.setattr(orientation_module, "arrow", FakeArrow(reads))
        monkeypatch.setattr(
            orientation_module, "time", SimpleNamespace(sleep=recorder.slept.append)
        )
        cfg = SimpleNamespace(
            CONFIG_FILE_NAME="config.json",
            modify_json_file=lambda filename, key, value: recorder.written.append(
                (key, value)
            ),
        )
        defaults = dict(
            cfg=cfg,
            img=SimpleNamespace(image_rotate=lambda img, deg: ("ROTATED", deg)),
            mouse_event=SimpleNamespace(
                mouse_move=lambda sub, **kw: recorder.mouse.append(sub)
            ),
            move=lambda value=0, key="w": recorder.walked.append((value, key)),
            arrow_begin="BEGIN",
            arrow_0="ARROW_0",
            multi_config=1.0,
        )
        defaults.update(attrs)
        return make_instance(Orientation, **defaults), recorder

    return _build


class TestAligning:
    def test_view_set_records_the_initial_arrow(self, build):
        inst, rec = build([])
        inst.handle_view_set(0.3)
        assert inst.arrow_begin == "ARROW"
        assert rec.slept == [0.3]

    def test_reset_stops_once_aligned(self, build):
        # 第一次差 90 度（要转 -90），第二次只差 1 度 → 收工
        inst, rec = build([90, 359])
        inst.handle_view_reset(0.1)
        assert rec.mouse == [-90, 1]
        # 0.6 出现两次：handle_view_reset 的前置一次 + 第一轮没对齐后一次。
        # 第二轮对齐了就不该再等。
        assert rec.slept.count(0.6) == 2

    def test_reset_gives_up_after_max_tries(self, build):
        inst, rec = build([90] * MAX_ALIGN_TRIES)
        inst.handle_view_reset(0.1)
        assert len(rec.mouse) == MAX_ALIGN_TRIES, "试满上限就放弃"
        # 前置一次 + 每一轮结束各一次（最后一轮失败后也走到底）
        assert rec.slept.count(0.6) == MAX_ALIGN_TRIES + 1

    def test_rotate_targets_the_rotated_arrow(self, build):
        inst, rec = build([359])  # 一次就对齐
        inst.handle_view_rotate(90)
        assert rec.mouse == [1]
        assert inst.img.image_rotate("ARROW_0", -90) == ("ROTATED", -90)

    def test_reset_and_rotate_share_the_same_convergence(self, build):
        """两者只有目标箭头和日志前缀不同 —— 收敛过程是同一段。"""
        # 逐个建、逐个跑：`arrow` 是模块全局，两次 build 会共用最后那次打的桩
        reset_inst, reset_rec = build([90, 359])
        reset_inst.handle_view_reset(0.1)

        rotate_inst, rotate_rec = build([90, 359])
        rotate_inst.handle_view_rotate(90)

        assert reset_rec.mouse == rotate_rec.mouse == [-90, 1]


class TestSetAngle:
    def test_calibrates_and_writes_the_scale(self, build):
        # 每个 move_num：1 次 init 读数 + （repeat 1 跑 1 次、repeat 1 被跳过、repeat 3 跑 3 次）
        # 角度每次都前进 30 度 → 比例 = move_num * n / (30n) = move_num/30
        reads = [10, 40, 70, 100, 130] + [10, -20, -50, -80, -110]
        inst, rec = build(reads)

        inst.set_angle()

        assert inst.multi_config == 2.0, "60/30 与 -60/(-30) 都是 2"
        assert ("angle", "2.0") in rec.written
        assert ("angle_set", True) in rec.written

    def test_gives_up_when_there_is_nothing_to_average(self, build):
        """一个有效读数都没有 → offset_list 空 → 一句「校准失败」，不写盘。

        默认的 ang=[1,1,3] 每组至少会跑一次、每跑一次就有一个读数，所以必然有值；
        要走到这个分支得让 repeat 序列为空。
        """
        inst, rec = build([1, 1])

        inst.set_angle(ang=[])

        assert rec.written == []
        assert inst.multi_config == 1.0

    def test_suspicious_zero_total_falls_back_to_one(self, build):
        """推进量之和为 0（读数没动）→ 退回 1 倍，而不是除零崩掉。"""
        inst, rec = build([5] * 12)

        inst.set_angle()

        assert ("angle", "1.0") in rec.written, "每一组都走「疑似校准错误」分支，值取 1"
        assert inst.multi_config == 1.0
