"""utils/core/match_offsets.py —— 匹配框与搜索区域 offset 的换算。

纯函数，零替身。这个值的唯一去向是 `take_screenshot(offset=...)`，所以除了真值表，
还专门和 `apply_offset` 对了一遍（符号写反的话那一条会立刻红）。
"""

import pytest

from utils.core.match_offsets import (
    FUZZY_PADDING,
    offset_for_box,
    padded_offset_for_box,
)

#: 一次真实量出来的例子：模板 100×100，落在窗口左上方
REGION = (100, 100, 2020, 1180)
BOX = (500, 400, 600, 500)


class TestOffsetForBox:
    def test_maps_a_box_into_the_four_edge_deltas(self):
        assert offset_for_box(BOX, REGION) == (400, 300, -1420, -680)

    def test_a_box_equal_to_the_region_is_all_zeros(self):
        assert offset_for_box(REGION, REGION) == (0, 0, 0, 0)

    def test_it_reproduces_the_box_through_apply_offset(self):
        """这个值最终是喂给 drivers/screen.py::apply_offset 的 —— 对一遍符号。"""
        from utils.drivers.screen import apply_offset

        region = (100, 100, 2020, 1180)

        offset = offset_for_box(BOX, region)

        assert apply_offset(region, offset) == (BOX, True)


class TestPaddedOffsetForBox:
    def test_expands_every_side_outward(self):
        offset, padded, applied = padded_offset_for_box(BOX, REGION)

        assert padded == (495, 395, 605, 505)
        assert offset == (395, 295, -1415, -675)
        assert applied == FUZZY_PADDING

    def test_the_padded_offset_reproduces_the_padded_box(self):
        from utils.drivers.screen import apply_offset

        region = (100, 100, 2020, 1180)

        offset, padded, _ = padded_offset_for_box(BOX, region)

        assert apply_offset(region, offset) == (padded, True)

    def test_default_padding_is_five(self):
        _, _, applied = padded_offset_for_box(BOX, REGION)

        assert FUZZY_PADDING == 5
        assert applied == 5

    def test_padding_is_configurable(self):
        _, padded, applied = padded_offset_for_box(BOX, REGION, pad=20)

        assert padded == (480, 380, 620, 520)
        assert applied == 20

    def test_zero_padding_matches_the_exact_offset(self):
        offset, padded, applied = padded_offset_for_box(BOX, REGION, pad=0)

        assert offset == offset_for_box(BOX, REGION)
        assert padded == BOX
        assert applied == 0


class TestClampingAtTheFrameEdge:
    """贴着画面边缘的框往外扩会扩到窗口外 —— 那部分像素不存在，必须夹住。"""

    def test_clamped_on_the_left_and_top(self):
        # 框的左上角就是截图区域的左上角：往左/往上无处可扩
        region = (100, 100, 1920, 1080)

        _, padded, applied = padded_offset_for_box((100, 100, 200, 200), region)

        assert padded == (100, 100, 205, 205), "只往右下扩得动"
        assert applied == 0, "最小的那一侧是 0"

    def test_clamped_on_the_right_and_bottom(self):
        region = (0, 0, 1920, 1080)

        _, padded, applied = padded_offset_for_box((1820, 980, 1920, 1080), region)

        assert padded == (1815, 975, 1920, 1080), "只往左上扩得动"
        assert applied == 0

    def test_partially_clamped_reports_the_smallest_side(self):
        """左边只扩得动 2px，其余三边是满的 —— 报最小的那个。"""
        region = (100, 100, 1920, 1080)

        _, padded, applied = padded_offset_for_box((102, 110, 200, 200), region)

        assert padded == (100, 105, 205, 205)
        assert applied == 2, "左边贴着区域边界，只扩了 2px"

    def test_a_box_filling_the_whole_region_cannot_expand_at_all(self):
        region = (0, 0, 100, 100)

        offset, padded, applied = padded_offset_for_box(region, region)

        assert padded == region
        assert offset == (0, 0, 0, 0)
        assert applied == 0


class TestHandlesTinyBoxes:
    """模板可能只有几个像素宽 —— 外扩不能把框挤成负数。"""

    @pytest.mark.parametrize("size", [1, 2, 5])
    def test_a_tiny_box_still_expands_by_the_full_padding(self, size):
        region = (0, 0, 1920, 1080)
        box = (500, 400, 500 + size, 400 + size)

        _, padded, applied = padded_offset_for_box(box, region)

        assert padded == (495, 395, 505 + size, 405 + size)
        assert applied == FUZZY_PADDING
