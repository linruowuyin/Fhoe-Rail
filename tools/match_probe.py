"""识图探针 —— 独立脚本，按路径运行（也可以双击根目录的 `Match-Probe.bat`）。

    py tools/match_probe.py

输入一个图片名（`picture/` 下的模板），工具抓一帧**游戏窗口**画面，打印这张模板当前
匹配到哪里、匹配得多像，以及两组反推 offset。

它对应 CLAUDE.md §1.2 的「可行性探针」：图像识别是全项目不确定性最高的一层，
阈值和余量只能从真实画面里量出来，这个工具就是那把尺子。

该看的数：
  * 匹配度 vs 阈值 —— 余量。余量 < 0.03 的阈值，游戏一更新就会碎。
  * 次优峰值 —— 这张模板在这一帧里唯一吗。最优 0.97 而次优也 0.96，说明帧里
    到处都长得像它，阈值再高也会指到错的位置。
  * 精确 / 模糊 offset —— `take_screenshot(offset=...)` 的取值。这个参数是**加在
    截图区域四边上的增量**，不是绝对坐标：左上为正（边界往里收），右下为负。
    模糊那组四边各往外扩 5px，留给反烧屏之类的微小 UI 位移。
  * 截图来源 —— `printwindow` 是游戏窗口自己的像素；`screengrab` 是回退去抓屏幕，
    **游戏被别的窗口盖住时抓到的就是盖住它的窗口**。

工具是只读的：抓屏、匹配、打印，不改任何文件、不点击、不动鼠标。游戏没开时它只会
提示你先把游戏打开（不会像主程序那样替你启动）。
"""

import os
import sys

# 按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，不补就 import 不到 utils
# （`ModuleNotFoundError: No module named 'utils'`）。这步必须赶在下面的
# `from utils...` 之前，所以只能放模块级 —— convert.py / validate_maps.py /
# format_maps.py 把同样的两步放进函数，是因为它们只在一个函数里用到 utils；
# 本工具在多个函数里都要用，导入写在模块级，这一步也就只能跟着在模块级。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from utils.core.thresholds import DEFAULT_MATCH
from utils.drivers.screen import (
    BASE_HEIGHT,
    BASE_WIDTH,
    CAPTURE_SCREENGRAB,
    ScreenSource,
)
from utils.drivers.window import Window
from utils.vision import assets as asset_registry
from utils.vision import images as image_library
from utils.vision import probe, viewer

# 系统语言兼容（issue #428 同类问题）：日文系统 cp932 代码页下中文 print 会崩溃。
# 本工具还会输出 ─ / ⚠ 这两个非 GBK 字符，重定向到文件时尤其会踩到。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

#: 模板目录。用户只敲名字（`transfer`）时在这里找，不用记得是 webp 还是 png。
PICTURE_DIR = "picture"

#: 名字没带后缀时假定的第一个候选；`images.resolve_path` 会按 .webp → .png → .jpg
#: 的优先级返回第一个真实存在的文件。
_TEMPLATE_EXTS = (".webp", ".png", ".jpg")

#: 余量低于这个值就标警告 —— 游戏一更新最先碎的就是这些（CLAUDE.md §1.2）
THIN_MARGIN = 0.03

#: `?片段` 一次最多列几张候选。367 张图全列出来没法看，也选不动；
#: 超了就提示把片段写长一点缩小范围。
SUGGEST_LIMIT = 20

LINE = "─" * 68

#: `recognize` 的三种结局。主循环只看它决定「当前图片」要不要更新。
OUTCOME_MEASURED = "measured"  # 出了报告
OUTCOME_MISSING = "missing"  # 图片不存在，压根没抓屏
OUTCOME_REJECTED = "rejected"  # 严格模式丢掉了这一帧，没出报告


def parse_input(text, default_threshold=DEFAULT_MATCH):
    """把一行输入解析成 `(图片名, 阈值)`。

    支持 `transfer` 与 `transfer 0.93` 两种写法。输入非法时抛 ValueError，
    由调用方打印提示后重新要输入 —— 这里不自己 exit。
    """
    parts = text.split()
    if not parts:
        raise ValueError("请输入图片名")
    if len(parts) > 2:
        raise ValueError("最多两个参数：图片名 [阈值]")
    name = parts[0]
    if len(parts) == 1:
        return name, default_threshold
    try:
        threshold = float(parts[1])
    except ValueError as error:
        raise ValueError(f"阈值不是数字：{parts[1]}") from error
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"阈值应落在 0~1：{threshold}")
    return name, threshold


def resolve_template(name, picture_dir=PICTURE_DIR):
    """把用户输入的名字解析成实际图片路径。

    带目录分隔符就按原路径处理；否则在 `picture_dir` 下找。没写后缀时补 `.webp`
    再交给 `images.resolve_path` —— 复用图库自己的 .webp → .png → .jpg 优先级，
    不在这里重写一份。

    找不到时返回**不存在的路径**而不是 None：调用方要用它拼「找不到」的提示。
    """
    path = name if os.path.dirname(name) else os.path.join(picture_dir, name)
    if not os.path.splitext(path)[1]:
        path += _TEMPLATE_EXTS[0]
    return image_library.resolve_path(path)


def suggest_names(fragment, picture_dir=PICTURE_DIR, limit=None):
    """列出图片名里含 `fragment` 的候选（不带后缀），不区分大小写。

    :param limit: None 表示不截断；调用方按自己的展示上限截
    """
    fragment = fragment.lower()
    hits = {
        os.path.splitext(os.path.basename(path))[0]
        for path in asset_registry.iter_picture_files(picture_dir)
        if fragment in os.path.splitext(os.path.basename(path))[0].lower()
    }
    hits = sorted(hits)
    return hits if limit is None else hits[:limit]


def format_report(measurement, name, path):
    """把一次测量的数字排成给人看的报告。纯函数，便于测试。

    :param measurement: `vision/probe.py::measure()` 的返回值
    """
    region_left, region_top, region_right, region_bottom = measurement["region"]
    frame_height, frame_width = measurement["frame"].shape[:2]
    template_height, template_width = measurement["template_shape"][:2]
    box_left, box_top, box_right, box_bottom = measurement["box"]
    score = measurement["score"]
    second = measurement["second"]
    threshold = measurement["threshold"]
    margin = measurement["margin"]

    verdict = "命中" if measurement["passed"] else "未达阈值"
    thin = f"   ⚠ 余量 < {THIN_MARGIN}，游戏一更新就可能碎" if margin < THIN_MARGIN else ""

    lines = [
        f"图片      {name}    文件 {path}",
        f"模板      {template_width}×{template_height} px    帧 {frame_width}×{frame_height}    "
        f"搜索区域 ({region_left}, {region_top})-({region_right}, {region_bottom})",
        f"匹配方式  {_strategy_label(measurement.get('strategy', 'color'))}",
        f"截图来源  {measurement['capture_source']}",
    ]
    if measurement["capture_source"] == CAPTURE_SCREENGRAB:
        lines.append(
            "⚠ 这一帧来自屏幕抓取（PrintWindow 没成）—— 游戏被别的窗口盖住时，"
            "抓到的就是盖住它的窗口"
        )
    lines += [
        "",
        f"匹配度    {score:.4f}  >  阈值 {threshold:.4f}    余量 {margin:+.4f}  [{verdict}]{thin}",
        f"次优峰值  {second:.4f}    与最优相差 {score - second:+.4f}",
        "",
        f"匹配框    左 {box_left}  上 {box_top}  右 {box_right}  下 {box_bottom}    （屏幕绝对坐标）",
        f"匹配中心  {measurement['center']}",
        _offset_line("精确 offset", measurement["exact_offset"], measurement["box"]),
        _offset_line("模糊 offset", measurement["fuzzy_offset"], measurement["padded_box"])
        + _fuzzy_note(measurement),
    ]

    # 登记了调用点搜索区域的模板（`Asset.search_offset`）：再报一行同一帧上的
    # 子区域结果。运行时点击用的就是这个区域，全屏分数好看不代表调用点找得到。
    search_area = next(
        (area for area in measurement.get("areas") or [] if area["area"] == "search"),
        None,
    )
    if search_area is not None:
        lines.append("")
        if search_area["error"]:
            lines.append(
                f"调用点    offset={search_area['offset']}   ⚠ {search_area['error']}"
            )
        else:
            item = next(
                (
                    c
                    for c in search_area["comparisons"]
                    if c["strategy"] == measurement["strategy"]
                ),
                search_area["comparisons"][0],
            )
            area_verdict = "命中" if item["passed"] else "未达阈值"
            lines.append(
                f"调用点    offset={search_area['offset']}    区域 {search_area['region']}"
            )
            lines.append(
                f"          匹配度 {item['score']:.4f}    余量 {item['margin']:+.4f}"
                f"  [{area_verdict}]    框 {item['box']}"
            )
    return "\n".join(lines)


def _offset_line(label, offset, box):
    return f"{label}  offset={offset}    区域 {box[2] - box[0]}×{box[3] - box[1]}"


def _strategy_label(strategy):
    """匹配策略 → 报告里的一小段中文说明。"""
    if strategy == "shape":
        return "形状（梯度幅值 + CCOEFF，不受底色影响）"
    if strategy == "color_ccoeff":
        return "原图 CCOEFF（减均值相关，适合文字/对话框）"
    return "颜色（整图 CCORR）"


def _fuzzy_note(measurement):
    pad = measurement["fuzzy_padding"]
    applied = measurement["pad_applied"]
    if applied == pad:
        return f"   ← 四边各外扩 {pad}px（留给反烧屏之类的微位移）"
    return f"   ← 四边各外扩 {pad}px，但贴着画面边缘了，最少的一侧只扩了 {applied}px"


def print_candidates(fragment, picture_dir=PICTURE_DIR):
    """列出候选并编号，返回**列出来的**那些（供下一次输入选号）。

    输入 `?片段` 之后，下一次可以直接敲编号选中，不用把名字抄一遍。
    """
    hits = suggest_names(fragment, picture_dir)
    if not hits:
        print(f"没有名字含「{fragment}」的图片。")
        return []
    shown = hits[:SUGGEST_LIMIT]
    print(f"名字含「{fragment}」的图片 {len(hits)} 张：")
    for index, item in enumerate(shown, start=1):
        print(f"  {index:>2}. {item}")
    if len(hits) > len(shown):
        print(f"  ……还有 {len(hits) - len(shown)} 张没列出，把片段写长一点缩小范围。")
    print("输编号选中，回车或其它输入取消。")
    return shown


def pick_from_candidates(candidates, text):
    """把一行输入解释成候选编号。不是合法编号就返回 None（由调用方按普通输入处理）。"""
    text = text.strip()
    if not candidates or not text.isdigit():
        return None
    index = int(text)
    if not 1 <= index <= len(candidates):
        return None
    return candidates[index - 1]


def show_preview(measurement):
    """弹窗预览这次匹配：绿框=精确匹配框，黄框=四边外扩后。按任意键关掉。"""
    image = probe.annotate_match(measurement)
    if image is None:
        return
    print("（弹出预览：绿框=精确匹配框，黄框=四边外扩后。看完按任意键）")
    viewer.show(image)
    viewer.pump()
    viewer.wait_key()
    viewer.close_all()


def recognize(screen, name, threshold, picture_dir=PICTURE_DIR, preview=False, allow_fallback=False):
    """抓一帧、测量、打印报告。

    :param preview: 打完报告后弹窗显示匹配框与模板所在的那一块
    :param allow_fallback: 是否放过「回退去抓屏幕」那一帧。默认不放过 —— 那种帧可能
        根本不是游戏画面，量出来的数字看着正常其实量错了对象
    :return: OUTCOME_MEASURED / OUTCOME_MISSING / OUTCOME_REJECTED
    """
    path = resolve_template(name, picture_dir)
    if not os.path.isfile(path):
        print(f"找不到图片：{path}")
        hits = suggest_names(name, picture_dir, limit=8)
        if hits:
            print("名字相近的有：" + "  ".join(hits))
        return OUTCOME_MISSING

    template = image_library.get_img(path)
    if template is None:
        # 文件在、但读不出来（0 字节、或者根本不是图片）。R12 的口径：检测不出就当
        # 「没找到」，不要往下喂给 cv2 才炸。
        print(f"图片读不出来（文件损坏或不是图片）：{path}")
        return OUTCOME_MISSING

    try:
        # 与运行时点击同一份搜索区域（R25：登记在 assets.py，不在这里另配一份）
        measurement = probe.measure(
            screen,
            template,
            threshold,
            allow_screen_fallback=allow_fallback,
            search_offset=image_library.search_offset_of(template),
        )
    except probe.ScreenFallbackRejected as error:
        print(error)
        return OUTCOME_REJECTED

    print(LINE)
    print(format_report(measurement, name, path))
    print(LINE)

    if preview:
        show_preview(measurement)
    return OUTCOME_MEASURED


def print_legend():
    print("识图探针：输入图片名 → 抓一帧游戏画面 → 测量它匹配到哪里。")
    print("「精确 offset」是加在截图区域四边上的增量（左上为正、右下为负），填给")
    print("take_screenshot / scan_screenshot，截取区域就正好罩住匹配框；")
    print("「模糊 offset」把四边各往外扩 5px，留给反烧屏之类的微小 UI 位移。")
    print("回车 = 同一张图重新识别    ?片段 = 列出候选（下一次可直接敲编号选中）")
    print("p = 开关弹窗预览    s = 允许屏幕回退帧（默认拦下）    q = 退出")


def warn_resolution(screen):
    """R8：窗口不是基准分辨率时，截图区域会算歪，先提醒再继续。"""
    left, top, right, bottom = screen.cal_screenshot()
    width, height = right - left, bottom - top
    if (width, height) != (BASE_WIDTH, BASE_HEIGHT):
        print(
            f"⚠ 当前截图区域 {width}×{height}，不是基准 {BASE_WIDTH}×{BASE_HEIGHT}。"
            "匹配位置会跟着歪，结果仅供参考。"
        )


def open_screen_source():
    """拿到**挂在游戏窗口上**的截图源，拿不到返回 None。

    先 `Window.find_window_hwnd()` 找一个游戏窗口（先按进程名 `StarRail.exe`，再退回
    按标题），**不构造 `Window()`** —— 构造它会把鼠标挪到窗口中心，游戏没开时还会
    启动游戏并连点 30 秒。探针只是量一张图，不该动用户的桌面。
    """
    try:
        hwnd = Window.find_window_hwnd()
    except Exception as error:  # noqa: BLE001 —— 顶层边界，给人话而不是堆栈
        print(f"查找游戏窗口失败：{error}")
        return None
    if not hwnd:
        print(Window.describe_missing_window())
        print("（探针只测量：不会替你启动游戏，也不会动你的鼠标。）")
        return None
    return ScreenSource(window=Window.attach(hwnd))


def main():
    print_legend()
    screen = open_screen_source()
    if screen is None:
        return 1
    warn_resolution(screen)

    name = None
    candidate = None
    threshold = DEFAULT_MATCH
    candidates = []
    preview = False
    allow_fallback = False

    while True:
        state = "｜".join(
            part
            for part in (
                name or "",
                "预览 ON" if preview else "",
                "允许回退 ON" if allow_fallback else "",
            )
            if part
        )
        try:
            text = input(f"\n图片名 [阈值]（{state or '必填'}）: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        picked = pick_from_candidates(candidates, text)
        candidates = []
        if picked is not None:
            candidate, threshold = picked, DEFAULT_MATCH
            print(f"选中：{picked}")
        else:
            lowered = text.lower()
            if lowered in ("q", "quit", "exit"):
                return 0
            if lowered == "p":
                preview = not preview
                print(f"弹窗预览已{'开启' if preview else '关闭'}。")
                continue
            if lowered == "s":
                allow_fallback = not allow_fallback
                print(
                    "已允许屏幕回退帧：PrintWindow 拿不到时会退到抓屏幕，结果可能不是游戏画面。"
                    if allow_fallback
                    else "已恢复拦下屏幕回退帧：拿不到游戏窗口自身的像素就报错重来。"
                )
                continue
            if text.startswith("?"):
                candidates = print_candidates(text[1:])
                continue
            if not text:
                if name is None:
                    print("请先输入图片名，或用 ?片段 查找。")
                    continue
                candidate, threshold = name, DEFAULT_MATCH
            else:
                try:
                    candidate, threshold = parse_input(text)
                except ValueError as error:
                    print(f"输入有误：{error}")
                    continue

        try:
            outcome = recognize(
                screen,
                candidate,
                threshold,
                preview=preview,
                allow_fallback=allow_fallback,
            )
        except KeyboardInterrupt:
            print()
            return 0
        except Exception as error:  # noqa: BLE001 —— 抓屏失败不该中断整个工具
            print(f"识别失败：{error}")
            continue

        # 图片不存在就别记成「当前图片」—— 否则下一次回车会一直重试一个错名字。
        # 回退帧被拦下则相反：图是对的，只是这一帧不能用，下次回车该重试同一张。
        if outcome != OUTCOME_MISSING:
            name = candidate


if __name__ == "__main__":
    sys.exit(main())
