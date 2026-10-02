"""匹配框 ↔ 搜索区域 offset 的换算。

`take_screenshot(offset=...)` / `scan_screenshot(prepared, offset=...)` 要的是一个
**四边增量**：加上去之后搜索区域正好落在匹配框上。探针要这个值两次 —— 精确一次、
四边各外扩一次 —— 所以抽成纯函数放 core：输入输出都是数字，不碰画面也不碰时钟
（CLAUDE.md §1.4）。

约定与 `drivers/screen.py::apply_offset` 一致：**左上为正、右下为负**。正值让该条边
往里收，负值往外放；`(0, 0, 0, 0)` 就是整个截图区域。
"""

#: 反烧屏之类微位移的容差：四边各往外扩这么多像素。
#: 这不是匹配阈值（那种数字归 core/thresholds.py 管），是几何容差。
FUZZY_PADDING = 5


def offset_for_box(box, region):
    """把匹配框换算成「让搜索区域正好落在框上」的四边增量。

    :param box: 匹配框 `(left, top, right, bottom)`，屏幕绝对坐标
    :param region: 本次截图的区域，同一坐标系
    :return: `(dl, dt, dr, db)`，可直接传给 `take_screenshot(offset=...)`
    """
    box_left, box_top, box_right, box_bottom = box
    region_left, region_top, region_right, region_bottom = region
    return (
        box_left - region_left,
        box_top - region_top,
        box_right - region_right,
        box_bottom - region_bottom,
    )


def padded_offset_for_box(box, region, pad=FUZZY_PADDING):
    """四边各往外扩 `pad` 像素，并把结果**夹在 `region` 之内**。

    为什么必须夹：贴着画面边缘的框往外扩会扩到窗口外面去，那部分像素不存在 ——
    把没夹过的值填进项目里，抓到的就是桌面，或者干脆是一片黑。夹过之后某一侧可能
    没扩满，实际扩了多少由返回值里的 `pad_applied` 说明。

    前提：`box` 落在 `region` 之内（匹配框本来就来自这一帧里的匹配位置，恒成立）。

    :return: `(offset, padded_box, pad_applied)`
        `offset` 是外扩后那个框反推出来的四边增量；
        `padded_box` 是实际生效的框（被夹过的）；
        `pad_applied` 是**四边里最小的**实际外扩量 —— 有一侧贴着画面边缘时它会小于
        `pad`，四边都贴边时为 0
    """
    box_left, box_top, box_right, box_bottom = box
    region_left, region_top, region_right, region_bottom = region

    padded = (
        max(region_left, box_left - pad),
        max(region_top, box_top - pad),
        min(region_right, box_right + pad),
        min(region_bottom, box_bottom + pad),
    )
    pad_applied = min(
        box_left - padded[0],
        box_top - padded[1],
        padded[2] - box_right,
        padded[3] - box_bottom,
    )
    return offset_for_box(padded, region), padded, pad_applied
