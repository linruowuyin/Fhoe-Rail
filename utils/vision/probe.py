"""图片探针 —— CLI 与 WebUI 共用的一份实现。

探针要回答的是同一件事：**这张模板现在匹配到哪、匹配得多像、两种 offset 各是多少**。
两个入口（`tools/match_probe.py` 与 WebUI 的探针页）都调这里，谁也不许自己再写一遍
配方 —— 严格 `>` 判定、次优峰、`框 = max_loc + 模板尺寸` 这几处一旦两边各抄一份，
迟早漂移。

放 vision 层是因为预览图要画框、要编码 PNG，而全项目只有 vision 可以直接 import cv2
（`tests/test_architecture.py::TestVisionIsolation` 是硬规则）。**cv2 一律在函数内部
惰性 import**，这样单测 offset 数学与 `measure` 不需要显示环境。
"""

from utils.core.match_offsets import (
    FUZZY_PADDING,
    offset_for_box,
    padded_offset_for_box,
)
from utils.core.thresholds import DEFAULT_MATCH
from utils.drivers.screen import CAPTURE_PRINTWINDOW
from utils.vision import images as image_library
from utils.vision.matcher import Matcher

#: 预览图在匹配框外再留多少像素的上下文 —— 够看清框有没有套在正确的特征上
PREVIEW_MARGIN = 120

#: 探针的抓帧重试。`take_screenshot` 默认 50 次 × 2 秒（主程序等游戏加载用的），
#: 探针是人手动触发的、而且 WebUI 那边还占着一个 HTTP 请求线程，挂 100 秒不可接受。
PROBE_MAX_RETRIES = 5
PROBE_RETRY_INTERVAL = 1.0

#: 预览图里两个框的颜色（BGR）。绿=精确匹配框，黄=四边外扩后那个框
BOX_COLOR_EXACT = (0, 255, 0)
BOX_COLOR_PADDED = (0, 191, 255)


class ScreenFallbackRejected(RuntimeError):
    """这一帧是从屏幕上抓的，不是游戏窗口自己的像素，调用方要求必须后一种。"""


def measure(
    screen,
    template,
    threshold=DEFAULT_MATCH,
    pad=FUZZY_PADDING,
    max_retries=PROBE_MAX_RETRIES,
    retry_interval=PROBE_RETRY_INTERVAL,
    allow_screen_fallback=False,
) -> dict:
    """抓一帧，量出这张模板的匹配情况。

    :param screen: `ScreenSource`（测试里可以是替身）。必须由调用方持有 ——
        抓帧来源记在它身上（`last_capture_source`），这里只能读。
    :param template: 模板图 ndarray（BGR，与帧同序）
    :param threshold: 用于算余量的阈值。仓库里没有「图片名 → 阈值」的表，所以这个
        值由调用方给，默认取 `DEFAULT_MATCH`
    :param pad: 模糊 offset 的四边外扩量
    :param max_retries: 抓帧重试次数，见 `PROBE_MAX_RETRIES`
    :param retry_interval: 每次重试之间等几秒
    :param allow_screen_fallback: 是否接受「回退去抓屏幕」那一帧。默认**不接受** ——
        `PrintWindow` 失败时主程序会退到按屏幕坐标抓，抓到的可能是盖在游戏上的别的
        窗口；那种帧量出来的数字看着正常，其实量错了对象。探针宁可报错也不要这个。
    :return: 结果 dict。`frame` 也在这里 —— 预览图必须画**同一帧**，
        不然两次抓屏之间画面变了，预览和数字就对不上
    :raises ScreenFallbackRejected: 拿到的是回退帧而 `allow_screen_fallback` 为假
    """
    frame, left, top, right, bottom = screen.take_screenshot(
        max_retries=max_retries, retry_interval=retry_interval
    )
    if not allow_screen_fallback and screen.last_capture_source != CAPTURE_PRINTWINDOW:
        raise ScreenFallbackRejected(
            "这一帧是从屏幕上抓的（PrintWindow 没成），可能根本不是游戏画面 —— 已丢弃。"
            "常见原因：① 游戏窗口被最小化；② 本进程的权限级别低于游戏（游戏以管理员运行、"
            "本进程没有）—— Windows 的 UIPI 会让 PrintWindow 发不出 WM_PRINT；"
            "③ 窗口句柄选错了（该进程名下有多个窗口）。确认后重试；"
            "确实拿不到游戏窗口像素的话，可以显式允许回退。"
        )
    region = (left, top, right, bottom)

    frame_height, frame_width = frame.shape[:2]
    template_height, template_width = template.shape[:2]
    if template_height > frame_height or template_width > frame_width:
        # 不说这一句的话，cv2.matchTemplate 会抛一句没人看得懂的断言；
        # 而调用方（WebUI 路由）需要把它当成「参数不对」来报 400。
        raise ValueError(
            f"模板比截图区域还大（模板 {template_width}×{template_height}，"
            f"区域 {frame_width}×{frame_height}），匹配不了"
        )

    matched = Matcher.match_peaks(frame, template, left, top)
    height, width = template.shape[:2]
    box_left, box_top = matched["max_loc"]
    box = (box_left, box_top, box_left + width, box_top + height)

    fuzzy_offset, padded_box, pad_applied = padded_offset_for_box(box, region, pad)

    return {
        "frame": frame,
        "region": region,
        "template_shape": template.shape,
        "box": box,
        "padded_box": padded_box,
        "center": (box_left + width // 2, box_top + height // 2),
        "score": matched["max_val"],
        "second": matched["second_val"],
        "strategy": image_library.strategy_of(template),
        "threshold": threshold,
        "margin": matched["max_val"] - threshold,
        # 全项目的判定都是严格大于，不是大于等于（core/thresholds.py 的约定）
        "passed": matched["max_val"] > threshold,
        "exact_offset": offset_for_box(box, region),
        "fuzzy_offset": fuzzy_offset,
        "fuzzy_padding": pad,
        "pad_applied": pad_applied,
        "capture_source": screen.last_capture_source,
    }


def annotate_match(measurement, margin=PREVIEW_MARGIN):
    """给一次测量结果裁一张预览图，画上精确框与外扩框。

    裁的是匹配框周围一块带上下文的区域，不是整帧 1920×1080 —— 整帧编码成 PNG 有好几
    兆，而人要看的就是框有没有套在正确的特征上。

    :param margin: 框外再留多少像素的上下文
    :return: BGR ndarray；裁剪区域为空时返回 None（调用方跳过预览）
    """
    import cv2

    frame = measurement["frame"]
    region_left, region_top = measurement["region"][0], measurement["region"][1]
    box = measurement["box"]
    padded = measurement["padded_box"]
    frame_height, frame_width = frame.shape[:2]

    # 屏幕绝对坐标 → 帧内坐标
    left = min(box[0], padded[0]) - region_left
    top = min(box[1], padded[1]) - region_top
    right = max(box[2], padded[2]) - region_left
    bottom = max(box[3], padded[3]) - region_top

    crop_left = max(0, left - margin)
    crop_top = max(0, top - margin)
    crop_right = min(frame_width, right + margin)
    crop_bottom = min(frame_height, bottom + margin)
    if crop_left >= crop_right or crop_top >= crop_bottom:
        return None

    crop = frame[crop_top:crop_bottom, crop_left:crop_right].copy()

    def _draw(rect, color):
        # cv2.rectangle 的右下角是闭区间，减 1 让描边落在框内
        cv2.rectangle(
            crop,
            (rect[0] - region_left - crop_left, rect[1] - region_top - crop_top),
            (rect[2] - region_left - crop_left - 1, rect[3] - region_top - crop_top - 1),
            color,
            2,
        )

    _draw(padded, BOX_COLOR_PADDED)  # 先画外框，精确框压在上面
    _draw(box, BOX_COLOR_EXACT)
    return crop


def encode_png(image) -> bytes:
    """把一张图编码成 PNG 字节。"""
    import cv2

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("PNG 编码失败")
    return buffer.tobytes()


def render_preview_png(measurement, margin=PREVIEW_MARGIN):
    """`annotate_match` + `encode_png` 的合体，给 WebUI 直接塞进响应里。"""
    crop = annotate_match(measurement, margin)
    return None if crop is None else encode_png(crop)
