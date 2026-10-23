"""画面比较 —— 固定位置相似度 + 整帧平移估计（CLAUDE.md §1.5 / 探针同层）。

标定 E 位移不需要点击、不需要识别 UI，只需要两张同机位截图的差异：

    scene_score(ref, cand)     同一区域、同一位置有多像（-1..1，1 为完全一致）
    estimate_shift(a, b)       整帧平移 (dx, dy) 与置信度（相位相关）

两个函数都只吃 ndarray，不碰截图、不碰窗口 —— 截图由调用方（工具/探针）给。
cv2 只在函数内部惰性 import，单测可以只测数学。
"""


def _gray(image):
    import cv2

    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def scene_score(reference, candidate):
    """比较两块**同尺寸**画面在固定位置的相似度。

    用 `TM_CCOEFF_NORMED` 在唯一位置（0,0）取值：不搜索、不允许平移补偿，
    所以位移不同会直接体现在分数上。完全一致为 1.0，反相关可到 -1。
    """
    import cv2

    ref = _gray(reference)
    cand = _gray(candidate)
    if ref.shape != cand.shape:
        raise ValueError(f"尺寸不一致：{ref.shape} vs {cand.shape}")
    if ref.size == 0:
        raise ValueError("空画面")
    if float(ref.std()) < 1e-6 and float(cand.std()) < 1e-6:
        # 两块纯色画面没有可比较的结构，归一化相关在数学上无定义
        return 0.0
    score = float(cv2.matchTemplate(cand, ref, cv2.TM_CCOEFF_NORMED)[0, 0])
    if score != score:  # NaN：纯色/无纹理画面
        return 0.0
    return score


def estimate_shift(a, b):
    """用相位相关估计 b 相对 a 的整帧平移。

    :return: `((dx, dy), response)`。`response` 接近 1 表示平移可信；接近 0
        说明两张图几乎没有可对齐的结构（或不是平移关系）。
    """
    import cv2
    import numpy as np

    ga = np.float32(_gray(a))
    gb = np.float32(_gray(b))
    if ga.shape != gb.shape:
        raise ValueError(f"尺寸不一致：{ga.shape} vs {gb.shape}")
    (dx, dy), response = cv2.phaseCorrelate(ga, gb)
    return (float(dx), float(dy)), float(response)


def projection(shift, direction):
    """把位移向量投影到 direction 方向上（同向为正，反向为负）。"""
    dx, dy = shift
    ux, uy = direction
    norm = (ux * ux + uy * uy) ** 0.5
    if norm == 0:
        return 0.0
    return (dx * ux + dy * uy) / norm


def ratio_along(shift, baseline):
    """把位移换算成「基准位移的倍数」，同时返回方向余弦。

    相机高度会在黄泉/银狼之间变化，同一个世界位移在像素上的长度不一样；
    用各自角色自己的 s:2.5 基准归一化后，才能比较两个位移。
    """
    bx, by = baseline
    norm = (bx * bx + by * by) ** 0.5
    total = (shift[0] ** 2 + shift[1] ** 2) ** 0.5
    if norm == 0 or total == 0:
        return 0.0, 0.0
    along = projection(shift, baseline)
    return along / norm, along / total


def equivalent_duration(shift_ref, shift_sample, sample_duration):
    """E 的位移等价于多少秒的 `ss`。

    :param shift_ref: O→A 的位移（E）
    :param shift_sample: O→B 的位移（样本时长）
    :param sample_duration: B 对应的 ss 秒数
    :return: (估计秒数, 方向余弦)。方向余弦 < 1 说明两者不共线，结果不可信。
    """
    sx, sy = shift_sample
    speed = (sx * sx + sy * sy) ** 0.5
    if speed == 0:
        return 0.0, 1.0
    direction = (sx / speed, sy / speed)
    along = projection(shift_ref, direction)
    total_ref = (shift_ref[0] ** 2 + shift_ref[1] ** 2) ** 0.5
    cosine = (along / total_ref) if total_ref else 0.0
    return sample_duration * along / speed, cosine
