"""跑图时收集图片样本 —— 开发者模式（配置键 `collect_picture_samples`）。

跑图过程中把「游戏里实际长什么样」按模板名字存下来，并累计统计 `picture/` 里哪些图
**没被用到**。两个用途合一：查错（原图和游戏画面对不上、匹配度掉了）与清理死图。

产物都在 `picture/new_pic/`：

    _seen.json             累计清单；删掉它就从零开始
    未使用图片.txt          报告 —— 由清单派生，每张地图跑完刷新一次（不逐帧写）
    <年月日_时分秒>/        每轮运行的样本图，一轮一个目录

`collect_picture_samples` 有三档（默认 `off`）：

    off     不收集
    single  每张图**本轮第一次**命中时落一张 —— 看"游戏里长什么样"够用了
    multi   **每次**命中都落 —— 用来看同一张图在整个流程里的稳定性

单图（`single`）：

    <轮次>/<原名>.webp
    <轮次>/<原名>-newcheck.webp

多图（`multi`）—— 每个模板一个子目录，序号按模板各自排：

    <轮次>/<原名>/0001_<地图>_<时分秒>.webp
    <轮次>/<原名>/0001_<地图>_<时分秒>-newcheck.webp
    <轮次>/<原名>/0002_<地图>_<时分秒>.webp
    …

多图那一档一趟跑下来可能是几千对文件（`-newcheck` 也照存），只该在分析时开。

两条口径，别混：

* **「被用到」= 被 `images.get_img` 加载过** —— 代码里引用到了它就算在用。这样连
  `arrow.py` / `mini_asu.py` 那两条绕过 `Matcher` 的匹配路径也覆盖得到（它们直接调
  cv2，钩不到）。「加载了但一次都没匹配上」算在用 —— 那属于"当前匹配不上"，
  分数列会显示出来，不是"没人用它"。
* **落样本图**才要求匹配成功（`> SAMPLE_FLOOR`），且**每轮运行每个文件名只落一次**
  （取第一次命中的那一帧）。新一轮跑图会把这些图**覆盖**掉 —— 不是只采一次就冻住。
"""

import json
import os
import re
import threading
import time
from datetime import datetime

import cv2

from utils.config.config import ConfigurationManager
from utils.core.log import log
from utils.core.match_offsets import padded_offset_for_box
from utils.core.thresholds import DEFAULT_MATCH
from utils.vision import assets

#: 样板图目录与产物目录（相对仓库根，与代码里其它地方用 `picture/` 的方式一致）
PICTURE_DIR = "picture"
SAMPLES_DIR = os.path.join(PICTURE_DIR, "new_pic")

#: 本轮运行的样本目录名：`new_pic/<年月日_时分秒>/`。**第一次要落盘时才生成** ——
#: 一张都没采到的一轮不该留个空目录。每轮一个新目录，这样同一张模板在不同轮次里的样子
#: 可以横向比对。
_run_dir_name = None
SEEN_FILENAME = "_seen.json"
REPORT_FILENAME = "未使用图片.txt"

#: 样本图的地板匹配度：收集器不知道调用方的阈值，用一个统一下限。
#: 报告里会把分数列出来，贴着地板的那些自己现形。
SAMPLE_FLOOR = DEFAULT_MATCH

#: 报告里把「分数偏低」单列一段的门槛 —— 哪天阈值碎了，最先碎的就是这些（§1.2）
LOW_SCORE = 0.95

#: 匹配发生时不在任何地图里（回主界面、月卡、跨日…）时用的记法
NO_MAP = "（地图外）"

_PICTURE_EXTS = (".webp", ".png", ".jpg", ".jpeg")

#: 写盘撞上文件锁时的重试与冷却（见 `_replace`）
_REPLACE_ATTEMPTS = 2
_REPLACE_RETRY_SECONDS = 0.02
_RETRY_COOLDOWN = 5.0

#: 保护 `_seen` 与磁盘上的清单：跑图不是单线程（疾跑检测线程也在匹配）
_lock = threading.Lock()
#: 累计清单 `{文件名: {"at": …, "scores": {地图名: {"score": …, "name": …}}}}`；None 表示还没读盘
_seen = None
#: `{目标路径: 冷却截止时刻}`：撞上锁的目标在一段时间内不再重试
_blocked_until = {}
#: **本轮运行**里已经落过样本的文件名。判据是「本轮跑过没有」而不是「文件在不在」——
#: 后者会让上一轮的样本永远冻住（用户实测提过：第二轮不会替换第一轮采的图）。
#: 新一轮 = 新进程（每次跑图都是 fresh 的 fhoe.py），这张表自然是空的。
#: 只用于单图模式；多图模式每次都落，不看它。
_sampled_this_run = set()
#: 多图模式：`{文件名: 本轮已落几张}` —— 序号按模板各自排
_multi_counts = {}

#: 当前正在跑哪张地图，由 `flows/map_operations.py` 在开跑/跑完时告知（R15：有明确的所有者）
_current_map = {"file": "", "name": ""}

#: 本轮运行有没有在日志里报过产物目录 —— 每轮只说一次，别每帧匹配刷屏
_location_logged = False


#: 收集模式。配置键 `collect_picture_samples` 存这三个值之一。
#:   single —— 每张图**本轮第一次**命中时落一张（默认，够看出"游戏里长什么样"）
#:   multi  —— **每次**命中都落一张，按模板分目录 + 顺序编号
#:             用来分析同一张图在整个锄大地流程里的稳定性
MODE_OFF = "off"
MODE_SINGLE = "single"
MODE_MULTI = "multi"

#: 老配置里这个键是布尔值；认下来，免得升级之后"明明开着却不采了"
_LEGACY_MODES = {True: MODE_SINGLE, False: MODE_OFF}


def mode() -> str:
    """当前收集模式。读配置请每次取 `cfg.config_file`（R14），不要存引用。"""
    try:
        raw = ConfigurationManager().config_file.get("collect_picture_samples")
    except Exception as error:  # noqa: BLE001 —— 读不到就当没开，不能把跑图带崩
        log.debug(f"读收集开关失败，按关闭处理：{error}")
        return MODE_OFF
    if raw in _LEGACY_MODES:
        return _LEGACY_MODES[raw]
    return raw if raw in (MODE_OFF, MODE_SINGLE, MODE_MULTI) else MODE_OFF


def enabled() -> bool:
    """收集开着没有。匹配钩子每帧都问一次，所以它是 `mode()` 的薄包装。"""
    return mode() != MODE_OFF


def log_location():
    """收集开着时，把产物目录的**绝对路径**写进日志 —— 每轮运行只写一次。

    逐张的「图片样本已存」只带相对 `new_pic/` 的路径，用户得自己猜它落在地盘哪里；
    这里在开跑时先说清楚 `picture/new_pic/` 解析到的绝对位置。
    """
    global _location_logged
    current = mode()
    if current == MODE_OFF:
        return
    with _lock:
        if _location_logged:
            return
        _location_logged = True
    log.info(
        f"图片样本收集已开启（模式：{current}），产物目录：{os.path.abspath(SAMPLES_DIR)}"
    )


def set_current_map(map_file, map_name=""):
    """记下现在在跑哪张地图。`map_file` 传空表示离开地图（回主界面、月卡…）。"""
    _current_map["file"] = map_file or ""
    _current_map["name"] = map_name or ""


def samples_dir():
    return SAMPLES_DIR


def run_dir():
    """本轮运行的样本目录 `new_pic/<年月日_时分秒>/`（第一次真正用到时才定下来）。

    同一秒里已经有同名目录时往后加序号 —— 真实跑图不会这么巧，但撞上就等于两轮串在一起。
    """
    global _run_dir_name
    if _run_dir_name is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate, index = stamp, 2
        while os.path.isdir(os.path.join(SAMPLES_DIR, candidate)):
            candidate, index = f"{stamp}_{index}", index + 1
        _run_dir_name = candidate
    return os.path.join(SAMPLES_DIR, _run_dir_name)


def note_loaded(image_path):
    """一张图**被加载**了 —— 「被用到」的信号。文件首次出现时才写盘。"""
    if not enabled():
        return
    name = os.path.basename(image_path)
    if not name:
        return
    try:
        with _lock:
            seen = _load()
            if name in seen:
                return
            seen[name] = {"at": _now(), "scores": {}}
            _save(seen)
    except Exception as error:  # noqa: BLE001 —— 收集是旁路，绝不能把跑图带崩
        log.warning(f"记录图片使用情况失败（不影响跑图）：{error}")


def note_match(image_path, frame, region, box, score):
    """一次匹配**成功了** —— 记分数，并按当前模式落样本图。

    单图：本轮第一次命中时落一张（`<轮次>/<原名>.webp` + `-newcheck`）
    多图：**每次**命中都落（`<轮次>/<原名>/0001_<地图>_<时分秒>.webp` + `-newcheck`）
          —— 用来看同一张图在整个锄大地流程里的稳定性

    :param image_path: 模板文件路径；反色/旋转造出来的图没有对应文件，传 None 即可
    :param frame: 这一帧（BGR ndarray）
    :param region: 帧对应的屏幕区域 `(left, top, right, bottom)`
    :param box: 匹配框，屏幕绝对坐标
    :param score: 匹配度
    """
    current = mode()
    if current == MODE_OFF or not image_path or score <= SAMPLE_FLOOR:
        return
    name = os.path.basename(image_path)
    try:
        with _lock:
            seen = _load()
            entry = seen.setdefault(name, {"at": _now(), "scores": {}})
            key = _current_map["file"] or NO_MAP
            recorded = entry["scores"].get(key, {}).get("score", 0.0)
            if score > recorded:
                entry["scores"][key] = {"score": score, "name": _current_map["name"]}
            _save(seen)

            if current == MODE_MULTI:
                index = _multi_counts.get(name, 0) + 1
                _multi_counts[name] = index
                paths = _multi_paths(name, index)
            else:
                if name in _sampled_this_run:
                    return
                _sampled_this_run.add(name)
                paths = _single_paths(name)

            _write_sample_images(paths, frame, region, box)
    except Exception as error:  # noqa: BLE001 —— 同上：采样失败不能把跑图带崩
        log.warning(f"记录图片样本失败（不影响跑图）：{error}")


def write_report():
    """重写一次报告。

    **不在每次匹配时写** —— 清了才干净：这份报告是 `_seen.json` 的派生视图，
    只在「每张地图跑完」和「整趟收尾」时生成（`flows/map_operations.py` 调）。
    反复替换同一个文件才是撞上"被别的程序占着"的根源，少写几次就基本不会撞上。
    """
    if not enabled():
        return
    try:
        with _lock:
            _write_report(_load())
    except Exception as error:  # noqa: BLE001 —— 旁路，绝不带崩跑图
        log.warning(f"写图片样本报告失败（不影响跑图）：{error}")


def reset(clear_disk=False):
    """清掉内存态。`clear_disk` 连产物目录里的清单与报告一起删（测试用）。

    每轮跑图是**新进程**，所以正常情况下不需要谁去调它 —— 模拟新一轮运行时才用得上。
    """
    global _seen, _run_dir_name, _location_logged
    with _lock:
        _seen = None
        _run_dir_name = None
        _location_logged = False
        _sampled_this_run.clear()
        _multi_counts.clear()
        _blocked_until.clear()
        set_current_map("")
        if clear_disk:
            for name in (SEEN_FILENAME, REPORT_FILENAME):
                path = os.path.join(SAMPLES_DIR, name)
                if os.path.isfile(path):
                    os.remove(path)


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load():
    """读磁盘上的累计清单（只读一次，之后走内存）。"""
    global _seen
    if _seen is not None:
        return _seen
    path = os.path.join(SAMPLES_DIR, SEEN_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _seen = data if isinstance(data, dict) else {}
    except FileNotFoundError:
        _seen = {}
    except Exception as error:  # noqa: BLE001 —— 清单坏了就从零开始，不能把跑图带崩
        log.warning(f"样本清单读不出来（{error}），本次从零开始累计：{path}")
        _seen = {}
    return _seen


def _replace(tmp, path):
    """`os.replace`，对着 Windows 的文件锁做几次短重试。返回是否换成。

    Windows 上**目标文件被别的进程打开着**时（最常见的就是你正开着这份报告在看），
    MoveFileEx 会直接拒绝访问 —— 那边的句柄没有 FILE_SHARE_DELETE。这不是异常情况：
    等一会儿多半就好了，等不到就让这次更新落后一拍，别去打扰跑图。

    失败过的目标会进一个**冷却期**：清单与报告是**每次匹配**都要写的，不冷却的话，
    你一直开着报告看，每一帧匹配都要在这儿白等两轮重试（约 200ms）—— 那才是真打扰。
    冷却期里直接跳过，等你关掉文件后最多 `_RETRY_COOLDOWN` 秒就自己恢复。
    """
    now = time.monotonic()
    if _blocked_until.get(path, 0.0) > now:
        _discard(tmp)
        return False

    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(tmp, path)
            _blocked_until.pop(path, None)
            return True
        except PermissionError:
            if attempt + 1 < _REPLACE_ATTEMPTS:
                time.sleep(_REPLACE_RETRY_SECONDS)

    _blocked_until[path] = time.monotonic() + _RETRY_COOLDOWN
    log.warning(
        f"{os.path.basename(path)} 被别的程序占着（多半是你正开着它），"
        f"这次没更新成；{int(_RETRY_COOLDOWN)} 秒内不再重试，关掉它就会自己跟上"
    )
    _discard(tmp)
    return False


def _discard(tmp):
    try:
        os.remove(tmp)
    except OSError:
        pass


def _save(seen):
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    path = os.path.join(SAMPLES_DIR, SEEN_FILENAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)
    _replace(tmp, path)


def _sample_ext(name):
    stem, ext = os.path.splitext(name)
    return stem, ext if ext.lower() in _PICTURE_EXTS else ".webp"


def _single_paths(name):
    """单图：`<轮次>/<原名>.webp`（+ `-newcheck`）。"""
    stem, ext = _sample_ext(name)
    folder = run_dir()
    return (
        os.path.join(folder, stem + ext),
        os.path.join(folder, f"{stem}-newcheck{ext}"),
    )


def _multi_paths(name, index):
    """多图：`<轮次>/<原名>/<序号>_<地图>_<时分秒>.webp`（+ `-newcheck`）。

    序号按模板各自排（打开一个目录就能顺着翻完那张图）；地图名与时间写进文件名，
    看到怪样能立刻知道是在流程的哪一段。
    """
    stem, ext = _sample_ext(name)
    map_part = _safe_part(os.path.splitext(_current_map["file"])[0] or "nomap")
    base = f"{index:04d}_{map_part}_{datetime.now().strftime('%H%M%S')}"
    folder = os.path.join(run_dir(), stem)
    return (
        os.path.join(folder, base + ext),
        os.path.join(folder, base + "-newcheck" + ext),
    )


def _safe_part(text):
    """文件名里只留安全字符。地图名本来就取自文件名，防的是有人手改出怪名字。"""
    return re.sub(r"[^\w\-.]+", "_", text)


def _crop(frame, region, box):
    """从帧里把匹配框那一块裁出来。越界时夹到帧内；裁不出来返回 None。"""
    left, top = region[0], region[1]
    frame_height, frame_width = frame.shape[:2]
    x0 = max(0, min(frame_width, box[0] - left))
    y0 = max(0, min(frame_height, box[1] - top))
    x1 = max(0, min(frame_width, box[2] - left))
    y1 = max(0, min(frame_height, box[3] - top))
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1].copy()


def encode_webp(image) -> bytes:
    """无损 webp。**只有 quality=101 是无损** —— 95/100 都会动像素（实测过）。"""
    ok, buffer = cv2.imencode(".webp", image, [cv2.IMWRITE_WEBP_QUALITY, 101])
    if not ok:
        raise RuntimeError("webp 编码失败")
    return buffer.tobytes()


def _write_sample_images(paths, frame, region, box):
    """落两张图：裁下来的原样一块 + 画了框的示意图。"""
    from utils.vision.probe import annotate_match  # 延迟 import：probe → matcher → 本模块，会成环

    plain, check = paths
    os.makedirs(os.path.dirname(plain), exist_ok=True)
    try:
        crop = _crop(frame, region, box)
        if crop is not None:
            with open(plain, "wb") as f:
                f.write(encode_webp(crop))

        _, padded_box, _ = padded_offset_for_box(box, region)
        annotated = annotate_match(
            {"frame": frame, "region": region, "box": box, "padded_box": padded_box}
        )
        if annotated is not None:
            with open(check, "wb") as f:
                f.write(encode_webp(annotated))
        log.info(f"图片样本已存：{os.path.relpath(plain, SAMPLES_DIR)}")
    except Exception as error:  # noqa: BLE001 —— 采样失败不能把跑图带崩
        log.warning(f"存图片样本失败（{os.path.basename(plain)}）：{error}")


def _picture_names():
    """`picture/` 下所有图片的文件名（递归，跳过 `new_pic/` 自己）。

    清单按**文件名**记（`_seen.json` 与样本都按 basename 命名）—— 文件名全局
    唯一是 R25 的约定，所以分目录后不会串。
    """
    return sorted(
        os.path.basename(path) for path in assets.iter_picture_files(PICTURE_DIR)
    )


def _run_dir_label():
    """报告里写「本轮样本在哪」—— 还没采到就不编一个目录名出来。"""
    if _run_dir_name is None:
        return "（本轮还没采到样本）"
    return os.path.join(SAMPLES_DIR, _run_dir_name)


def _write_report(seen):
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    names = _picture_names()
    unused = [name for name in names if name not in seen]

    lines = [
        "图片样本收集报告",
        f"生成时间：{_now()}",
        "",
        f"{SAMPLES_DIR}/ 下面：",
        f"  {SEEN_FILENAME}        累计清单 —— 「被用到」记在这里，删掉它就从头计",
        f"  {REPORT_FILENAME}      本文件；每张地图跑完刷新一次（不逐帧写，免得跟正在看它的你抢）",
        "  <年月日_时分秒>/        每轮运行的样本图，一轮一个目录：",
        "                          单图 → <原名>.webp；多图 → <原名>/0001_<地图>_<时分秒>.webp",
        f"  当前收集模式：{mode()}",
        f"  本轮样本目录：{_run_dir_label()}",
        "",
        "口径：",
        "  「被用到」= 被加载过（代码里引用到了它），不要求匹配成功；",
        "  只跑过少数几张地图时，未使用里绝大多数是「这轮没跑到的图」，不是死图。",
        "  样本图：每轮里同名只落第一次命中的那一帧。",
        "",
        f"picture/ 共 {len(names)} 张；已用到 {len(names) - len(unused)} 张，"
        f"未使用 {len(unused)} 张",
        "",
        f"=== 未使用（{len(unused)} 张）===",
    ]
    lines += unused or ["（无）"]

    lines += ["", f"=== 已用到但匹配度偏低（< {LOW_SCORE}）==="]
    lines.append("哪天阈值碎了最先碎的就是这些，后面跟着的是它碎在哪张地图里：")
    low = []
    for name in sorted(seen):
        for map_key, info in sorted((seen[name].get("scores") or {}).items()):
            if info.get("score", 1.0) < LOW_SCORE:
                where = map_key if map_key == NO_MAP else f"{map_key}（{info.get('name') or '未知'}）"
                low.append(f"  {name:<40} {info['score']:.4f}  {where}")
    lines += low or ["（无）"]

    path = os.path.join(SAMPLES_DIR, REPORT_FILENAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    _replace(tmp, path)
