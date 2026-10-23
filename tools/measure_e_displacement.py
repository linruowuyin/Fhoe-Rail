"""测量「黄泉 E 的位移 = 银狼 ss 多少秒」（基座舱段，固定传送点）。

一次连续移动（默认走路，可选疾跑），在 ss 0.2–1.0 秒之间尽量每 0.02 秒
截一张图，再挑和黄泉 E 终点（银狼机位）最像的那张；它的时间戳就是答案。

    py tools/measure_e_displacement.py
    py tools/measure_e_displacement.py --sprint --start 0.45 --end 0.65

`--sprint` 打开后，黄泉助跑、银狼助跑、采样段全部按疾跑走，三段的起点保持一致。

流程（全程自动，不需要人工输入，银狼段只传送一次）：

  1. 黄泉段：回主界面 → 基座舱段完整 start → 按 `1`（1 号位黄泉）→ 等画面稳定
     → s:2.5 → 截图 O（基准）→ E:2 → 等冲刺动画结束 → 截图 A
     → 切到银狼再拍一张同机位的 A_ref
  2. 银狼段：按 `2`（2 号位银狼）→ s:2.5 → 不松键继续走，
     从 0.2 到 1.0 秒连续截图（实际间隔受截图耗时限制，日志会打印）
  3. 每帧与 A_ref 在固定位置比相似度，取最高帧的时刻
  4. 输出逐帧截图 `t_<时刻>.png`、scores.csv、result.json

前提：

  * 1 号位必须是黄泉，2 号位必须是银狼，且秘技点/零食充足
  * 基地舱段的传送点周围不能有敌人；E 的位移方向必须和 s 同向
  * 默认不疾跑；加 `--sprint` 则全段开疾跑（`auto_run_in_map` 跟着切换）
  * 建议用 `Start-WebUI` / 管理员终端运行；截图必须来自 PrintWindow

输出在 `logs/e_calibration/<时间戳>/`：O/A/A_ref、逐帧截图、scores.csv、result.json。
"""

import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PIL import Image

from utils.config.config import ConfigurationManager
from utils.core.log import log
from utils.core.map_info import MapInfo
from utils.core.thresholds import MAP_BACK, MAP_OPEN
from utils.drivers.keyboard_event import KeyboardEvent
from utils.drivers.screen import CAPTURE_PRINTWINDOW
from utils.flows.map_operations import MapOperations
from utils.vision import compare

#: 基座舱段-1：起点就在这个传送点旁边，start 里已经有完整导航
BASE_MAP = "map_1-1_1.json"
#: 助跑：固定 2.5 秒，强制 normal_run（不疾跑）
RUN_UP_SECONDS = 2.5

#: 相似度比对：左侧 360，去掉左上小地图（y 380 以下）
SCORE_BOX = (0, 380, 360, 1080)
#: 相位相关：用更宽的场景区，避免位移超过 360 后没有重叠
SHIFT_BOX = (0, 380, 960, 1080)

STABLE_TIMEOUT = 12.0
STABLE_INTERVAL = 0.4
STABLE_SCORE = 0.99


def crop(image, box):
    left, top, right, bottom = box
    return image[top:bottom, left:right]


def save_part(part, path):
    """已经裁好的 BGR 片段 → RGB PNG。"""
    Image.fromarray(part[:, :, ::-1]).save(path)


def save_crop(image, box, path):
    """截图的 BGR ndarray → RGB PNG。只裁不缩放，方便肉眼核对。"""
    save_part(crop(image, box), path)


def parse_args(argv):
    opts = {
        "start": 0.2,
        "end": 1.0,
        "interval": 0.02,
        "sprint": False,
        "out": None,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, sep, inline = arg.partition("=")
        if name in ("--start", "--end", "--interval"):
            if sep:
                value = inline
            else:
                i += 1
                value = argv[i] if i < len(argv) else ""
            opts[name[2:]] = float(value)
        elif name == "--sprint":
            opts["sprint"] = True
        elif name == "--out":
            if sep:
                opts["out"] = inline or None
            else:
                i += 1
                opts["out"] = argv[i] if i < len(argv) else None
        else:
            raise SystemExit(f"未知参数：{arg}（用法见文件头）")
        i += 1
    if opts["interval"] <= 0:
        raise SystemExit("--interval 必须 > 0")
    if opts["start"] < 0:
        raise SystemExit("--start 不能为负")
    if opts["end"] <= opts["start"]:
        raise SystemExit("--end 必须大于 --start")
    return opts


def best_scored(scored):
    """`(时刻, 相似度)` 列表里相似度最高的一项。"""
    return max(scored, key=lambda item: item[1])


def final_paths(out_dir, duration):
    """最终确认的两张图：黄泉 E 参考帧 + 最相似的银狼候选帧。"""
    root = Path(out_dir)
    return (
        root / "final_huangquan_e.png",
        root / f"final_ss_{duration:.2f}.png",
    )


class _NoPause:
    """工具不需要 F7-F10：给 process_single_map_start 一个永不暂停的替身。"""

    pending_key = None

    def check_pause(self, dev, last_point=""):
        return False

    def wait_if_paused(self):
        return 0.0


def capture(img, box):
    """抓一帧并裁到 box；拒绝 screengrab 回退帧（可能根本不是游戏）。"""
    frame, *_ = img.take_screenshot(max_retries=5, retry_interval=1)
    if img.screen.last_capture_source != CAPTURE_PRINTWINDOW:
        raise RuntimeError(
            "这一帧是从屏幕上抓的（PrintWindow 失败），可能拍到了别的窗口；"
            "请确保游戏可见、不与本工具争管理员权限。"
        )
    height, width = frame.shape[:2]
    if (width, height) != (1920, 1080):
        raise RuntimeError(
            f"游戏画面是 {width}×{height}，本工具的裁切区域按 1920×1080 写死；"
            "请先把游戏调到 1920×1080。"
        )
    return frame


def wait_stable(img, box, timeout=STABLE_TIMEOUT):
    """轮询到连续两帧足够像为止（R1：不用固定 sleep 对齐游戏状态）。"""
    previous = crop(capture(img, box), box)
    started = time.time()
    while time.time() - started < timeout:
        time.sleep(STABLE_INTERVAL)
        frame = capture(img, box)
        current = crop(frame, box)
        score = compare.scene_score(previous, current)
        if score >= STABLE_SCORE:
            return frame
        previous = current
    print(f"！画面 {timeout:.0f} 秒内没有完全稳定，使用最后一帧继续（相似度可能受影响）")
    return frame


def snap(img):
    """动作一结束就截一帧，不等画面静止。

    `wait_stable` 会等相机缓动追上角色，把「松开按键那一刻」拍成「相机稳定后」，
    0.1 秒级的位移里，这段相机追赶会让终点看起来比实际更靠前。
    """
    return capture(img, SCORE_BOX)


def wait_main(img, timeout=60.0):
    return img.on_main_interface(timeout=timeout)


def _map_screen_visible(ops, img):
    """地图界面是否已经打开。

    不用 `Map.open_map` 的 `_wait_for_main_interface`：新版地图界面左上角的图标
    仍会命中「主界面灯泡」，那里的循环会反复按 M 把地图开了又关。这里只看地图
    独有的锚点：底部的收起按钮，退而求其次看右上角的返回键。
    """
    contraction = ops.img.get_img("./picture/contraction.png")
    if contraction is not None and img.on_interface(
        check_list=[contraction],
        timeout=1.0,
        interface_desc="地图界面",
        threshold=MAP_OPEN,
        offset=(530, 960, -1050, -50),
        allow_log=False,
    ):
        return True

    back = ops.img.get_img("./picture/map_back.png")
    return bool(
        back is not None
        and img.on_interface(
            check_list=[back],
            timeout=0.5,
            interface_desc="地图返回键",
            threshold=MAP_BACK,
            offset=(1830, 0, 0, -975),
            allow_log=False,
        )
    )


def open_map_direct(ops, img, handle):
    """按一次 M 并确认地图真的开了；绕开 open_map 的死循环。"""
    for _ in range(4):
        if _map_screen_visible(ops, img):
            return
        if not img.on_main_interface(timeout=3.0):
            handle.back_to_main()
        handle.window.switch_window()  # 每次按键前确认游戏在前台
        print("按 M 打开地图…")
        KeyboardEvent.keyboard_press("m")
        time.sleep(1.5)
        if _map_screen_visible(ops, img):
            return
        handle.back_to_main()
    raise RuntimeError(
        "无法打开地图：按 M 后既没检测到地图收起按钮，也没检测到地图返回键。"
        "请确认游戏在前台、当前不在战斗/对话/加载中。"
    )


def teleport(ops, img, handle):
    """回主界面，手动开地图，再走基座舱段-1 的 start（跳过其中的 `map` 步）。"""
    handle.back_to_main()
    open_map_direct(ops, img, handle)

    original_open = ops.map.open_map
    ops.map.open_map = lambda: None  # `map` 步：地图已经开了，别再按一次 M
    try:
        ops.process_single_map_start(0, BASE_MAP)
    finally:
        ops.map.open_map = original_open
    if not wait_main(img):
        raise RuntimeError("传送后没有回到游戏主界面；请确认传送点与网络状态")


def reset_movement(handle):
    handle.movement.last_step_run = False
    handle.movement.run_fixed = False
    handle.movement.run_fix_time = 0


def run_segment(ops, img, handle, kind, switch_key=None, sprint=False):
    """跑一段，返回 (O0, X)。

    O0 永远在助跑前拍，X 是动作结束瞬间的帧（E 的 A 要到冲刺动画结束）。
    `sprint=True` 时助跑按疾跑走（与银狼轨迹段的助跑保持一致）。

    * kind="run"：只做 s:2.5，一结束就拍 Os —— 专门量助跑位移
    * kind="e"  ：s:2.5 后**立即** E，等冲刺动作走完再拍 A

    s 和 E 之间不能有任何等待：一旦停下来，量到的起点就不是连续的走路终点。
    Os 是 `handle_move` 返回后立刻截图（`snap`），不等画面静止；
    E 的 A 例外：`handle_e` 返回时冲刺动画还没放完，必须等动作结束。
    """
    log.info(f"当前段落: {kind}（{'疾跑' if sprint else '走路'}）")

    teleport(ops, img, handle)

    if switch_key:
        # 数字键切队伍位：黄泉段 1 号位、银狼段 2 号位
        handle.handle_num(0.5, switch_key)
        wait_stable(img, SCORE_BOX)

    reset_movement(handle)
    frame_o0 = wait_stable(img, SCORE_BOX)  # 助跑前，静态基准
    handle.handle_move(RUN_UP_SECONDS, "s", normal_run=not sprint)

    if kind == "run":
        frame_x = snap(img)
        frames = (frame_o0, frame_x)
    elif kind == "e":
        handle.handle_e(2)  # 黄泉：只放秘技，不点屏幕
        # 这里不能立即截图：handle_e 只等 0.25 秒，冲刺动画还没走完。
        # 等的是「动作结束」，不是「画面静止」。
        frame_hq = wait_stable(img, SCORE_BOX)
        if not img.on_main_interface(timeout=5.0):
            raise RuntimeError(
                "E 后不在主界面：可能进了战斗。请换一个没有敌人的传送点。"
            )
        # 切到银狼再拍一张：E 的终点不变，但相机高度变成银狼的。
        # 扫描时拿它和银狼候选帧比，才是同一机位。
        handle.handle_num(0.5, "2")
        frame_ref = wait_stable(img, SCORE_BOX)
        frames = (frame_o0, frame_hq, frame_ref)
    else:
        raise ValueError(f"未知段落类型: {kind}")

    if not img.on_main_interface(timeout=5.0):
        raise RuntimeError(
            "动作后不在主界面：可能进了战斗或打开了别的界面。"
            "请换一个没有敌人的传送点，或先清掉附近的怪。"
        )
    return frames


def run_trajectory(ops, img, handle, start, end, interval, sprint=False):
    """传送后连续按住 s（走路或疾跑），从 start 到 end 秒按 interval 采样。

    返回 `(O0, [(时刻, 截图), ...])`，时刻相对「2.5 秒助跑走完」。

    位移与时间线性，所以每帧就对应一个 ss 时长，不用为每个秒数重新传送。
    `sprint=True` 时助跑交给 `handle_move` 开疾跑，并借 `next_key` 让 s 与
    Shift 保持按住，采样直接从疾跑状态开始；否则自己按住 s 走 2.5 秒。
    截图本身有耗时，`interval` 只是下限：实际间隔以日志打印为准，
    帧时刻取单帧拍摄过程的中点。
    """
    teleport(ops, img, handle)
    handle.handle_num(0.5, "2")  # 银狼 2 号位
    wait_stable(img, SCORE_BOX)
    reset_movement(handle)
    frame_o0 = wait_stable(img, SCORE_BOX)

    frames = []
    # R5：按键动作放在 try 里面，无论怎么退出都要松开
    try:
        if sprint:
            # 助跑开疾跑；next_key="ss" 会让 handle_move 不松键并保留 Shift，
            # 返回时角色仍在疾跑，采样从这里开始
            handle.handle_move(RUN_UP_SECONDS, "s", next_key="ss")
            base = time.perf_counter()
        else:
            KeyboardEvent.press_key("s")
            started = time.perf_counter()
            while time.perf_counter() - started < RUN_UP_SECONDS:
                time.sleep(0.01)  # 助跑走完之前不采样，也避免忙等（R2）
            base = time.perf_counter()
        next_at = start
        while True:
            now = time.perf_counter() - base
            if now > end:
                break
            if now < next_at:
                time.sleep(min(interval, next_at - now))
                continue
            before = time.perf_counter()
            frame = capture(img, SCORE_BOX)
            after = time.perf_counter()
            frames.append(((before + after) / 2 - base, crop(frame, SCORE_BOX)))
            # 按计划推进下一个采样点；截图本身比间隔还慢时就立刻拍下一帧
            next_at += interval
            if next_at < after - base:
                next_at = after - base
    finally:
        try:
            handle.movement.release_held()
        except Exception:
            pass
        try:
            KeyboardEvent.release_key("s")
            KeyboardEvent.release_key("shift")
        except Exception:
            pass

    if len(frames) > 1:
        gaps = [later[0] - earlier[0] for earlier, later in zip(frames, frames[1:])]
        log.info(
            f"轨迹采样 {len(frames)} 帧，实际间隔 {min(gaps):.3f}–{max(gaps):.3f}s"
        )
        if max(gaps) > interval * 1.5:
            print(
                f"！实际采样间隔最大 {max(gaps):.3f}s（比 --interval 慢，截图耗时所致），"
                "最佳时刻的精度按实际间隔算"
            )

    if not img.on_main_interface(timeout=5.0):
        raise RuntimeError(
            "轨迹采样后不在主界面：可能进了战斗或打开了别的界面。"
            "请换一个没有敌人的传送点，或先清掉附近的怪。"
        )
    return frame_o0, frames


def _override_config(cfg, sprint=False):
    old_version = cfg.config_file.get("map_version", "default")
    old_run = cfg.config_file.get("auto_run_in_map", False)
    old_samples = cfg.config_file.get("collect_picture_samples", "off")
    cfg.swap_map_version("HuangQuan")
    # 默认不疾跑：走路速度固定，位移与时长才是线性的；--sprint 时放开自动疾跑
    cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "auto_run_in_map", bool(sprint))
    # 标定不需要采样本，否则每一帧都写 webp，拖慢轮询
    cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "collect_picture_samples", "off")
    cfg._config = None
    map_info = MapInfo()
    map_info._map_version = "HuangQuan"
    return old_version, old_run, old_samples


def _restore_config(cfg, old_version, old_run, old_samples):
    try:
        cfg.swap_map_version(old_version)
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "auto_run_in_map", old_run)
        cfg.modify_json_file(
            cfg.CONFIG_FILE_NAME, "collect_picture_samples", old_samples
        )
        cfg._config = None
        MapInfo()._map_version = old_version
    except Exception as e:
        print(f"！恢复配置失败：{e}")


def _make_ops():
    import utils.flows.map_operations as map_ops_module

    # 标定不需要给用户发 webhook
    map_ops_module.webhook_and_log = lambda *args, **kwargs: None
    ops = MapOperations()
    ops.pause = _NoPause()
    ops.map.pause_gate = lambda: 0.0
    # 标定不按白名单/黑名单过滤，也不做月卡检查
    ops.map.check_allowlist_maps = lambda name: False
    ops.map.check_forbidden_maps = lambda name: False
    ops.monthly_pass = SimpleNamespace(monthly_pass_check=lambda: None)
    return ops


def ensure_admin():
    """游戏以管理员运行，低权限进程的键鼠注入会被 UIPI 静默丢弃。

    表现就是：日志里一切正常、窗口也激活成功，但游戏里实际没收到 M/数字键。
    这里和 Start-WebUI 一样自动提权，原进程退出。
    """
    if os.name != "nt":
        return
    import ctypes

    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
    except Exception:
        return

    if getattr(sys, "frozen", False):
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        params = subprocess.list2cmdline(
            [os.path.abspath(__file__), *sys.argv[1:]]
        )
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if rc <= 32:
        print("[ERROR] 需要管理员权限：请右键以管理员身份运行，或先运行 Start-WebUI.bat。")
        raise SystemExit(1)
    raise SystemExit(0)


def main(argv=None):
    ensure_admin()
    # 所有资源路径（map/、config.json、logs/）都相对仓库根；
    # 用户经常在 tools/ 下直接跑脚本，不切 cwd 的话 MapInfo 连 map 目录都找不到
    os.chdir(_REPO_ROOT)
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    cfg = ConfigurationManager()
    old_version, old_run, old_samples = _override_config(cfg, opts["sprint"])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(opts["out"] or Path(_REPO_ROOT) / "logs" / "e_calibration" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)

    ops = None
    try:
        ops = _make_ops()
        img = ops.img
        handle = ops.handle

        print("基准段 1/2：黄泉机位的 s:2.5…")
        o_bh, os_bh = run_segment(
            ops, img, handle, "run", switch_key="1", sprint=opts["sprint"]
        )
        save_crop(o_bh, SCORE_BOX, out_dir / "O_baseline_huangquan.png")
        save_crop(os_bh, SCORE_BOX, out_dir / "OS_baseline_huangquan.png")

        print("基准段 2/2：银狼机位的 s:2.5…")
        o_bs, os_bs = run_segment(
            ops, img, handle, "run", switch_key="2", sprint=opts["sprint"]
        )
        save_crop(o_bs, SCORE_BOX, out_dir / "O_baseline_silverwolf.png")
        save_crop(os_bs, SCORE_BOX, out_dir / "OS_baseline_silverwolf.png")

        print("黄泉段：s:2.5 后立即 E，再切银狼拍同机位参考帧…")
        o_e, a_hq, a_ref = run_segment(
            ops, img, handle, "e", switch_key="1", sprint=opts["sprint"]
        )
        save_crop(o_e, SCORE_BOX, out_dir / "O_huangquan.png")
        save_crop(a_hq, SCORE_BOX, out_dir / "A_e_huangquan_camera.png")
        save_crop(a_ref, SCORE_BOX, out_dir / "A_e_silverwolf_camera.png")

        print(
            f"银狼段：连续{'疾跑' if opts['sprint'] else '走路'}采样 ss "
            f"{opts['start']:.2f}–{opts['end']:.2f}s"
            f"（目标间隔 {opts['interval']:.2f}s）…"
        )
        o_s, samples = run_trajectory(
            ops,
            img,
            handle,
            opts["start"],
            opts["end"],
            opts["interval"],
            sprint=opts["sprint"],
        )
        save_crop(o_s, SCORE_BOX, out_dir / "O_silverwolf.png")
        if not samples:
            raise RuntimeError("一帧都没采到：检查截图耗时与 --start/--end")

        start_score = min(
            compare.scene_score(crop(o_bh, SCORE_BOX), crop(o_e, SCORE_BOX)),
            compare.scene_score(crop(o_bs, SCORE_BOX), crop(o_s, SCORE_BOX)),
        )
        # 两个机位各量各的 s:2.5；相机高度不同，不能混用基准
        shift_run_hq, resp_run_hq = compare.estimate_shift(
            crop(o_bh, SHIFT_BOX), crop(os_bh, SHIFT_BOX)
        )
        shift_run_sw, resp_run_sw = compare.estimate_shift(
            crop(o_bs, SHIFT_BOX), crop(os_bs, SHIFT_BOX)
        )
        shift_ea, resp_ea = compare.estimate_shift(
            crop(o_e, SHIFT_BOX), crop(a_hq, SHIFT_BOX)
        )
        e_shift = (
            shift_ea[0] - shift_run_hq[0],
            shift_ea[1] - shift_run_hq[1],
        )
        e_ratio, e_cos = compare.ratio_along(e_shift, shift_run_hq)

        print("\n=== 位移测量 ===")
        print(f"起点可重复性（同机位 O0 最小值）：{start_score:.4f}")
        print(
            f"助跑 s:2.5（黄泉机位）: {shift_run_hq[0]:+.1f}, {shift_run_hq[1]:+.1f} px"
            f"（置信度 {resp_run_hq:.3f}）"
        )
        print(
            f"助跑 s:2.5（银狼机位）: {shift_run_sw[0]:+.1f}, {shift_run_sw[1]:+.1f} px"
            f"（置信度 {resp_run_sw:.3f}）"
        )
        print(
            f"E 位移（扣除黄泉助跑）: {e_shift[0]:+.1f}, {e_shift[1]:+.1f} px"
            f" → {e_ratio:+.3f} 倍助跑；方向一致性 {e_cos:.3f}"
        )

        if abs(e_shift[0]) + abs(e_shift[1]) < 20:
            print(
                "！E 的位移只有不到 20px：E 可能没放出来（秘技点不足 / 角色不是黄泉），"
                "或相机没有跟随。先确认角色与秘技点再重跑。"
            )
        if start_score < 0.95:
            print("！同机位起点的相似度过低：传送后的相机/站位不稳定，结果不可信")
        if resp_ea < 0.1 or resp_run_hq < 0.1 or resp_run_sw < 0.1:
            print("！相位相关置信度过低：画面纹理不足或位移过大，结果不可信")
        if e_cos < 0.9:
            print("！E 的位移方向与助跑不一致：比例结果不可信，看截图扫描为准")

        a_ref_part = crop(a_ref, SCORE_BOX)
        scored = []
        for t, part in samples:
            save_part(part, out_dir / f"t_{t:.3f}.png")
            scored.append((t, compare.scene_score(a_ref_part, part)))
        best_t, best_score = best_scored(scored)

        # 最终确认的两张：黄泉 E 的参考帧 + 最相似的采样帧。
        final_reference, final_candidate = final_paths(out_dir, best_t)
        shutil.copyfile(out_dir / "A_e_silverwolf_camera.png", final_reference)
        shutil.copyfile(out_dir / f"t_{best_t:.3f}.png", final_candidate)

        with open(out_dir / "scores.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "score"])
            writer.writerows((f"{t:.4f}", f"{score:.6f}") for t, score in scored)

        result = {
            "mode": "trajectory",
            "start": opts["start"],
            "end": opts["end"],
            "interval": opts["interval"],
            "sample_count": len(scored),
            "start_score": start_score,
            "shift_run_huangquan": shift_run_hq,
            "shift_run_silverwolf": shift_run_sw,
            "shift_e": e_shift,
            "ratio_e": e_ratio,
            "response_run_huangquan": resp_run_hq,
            "response_run_silverwolf": resp_run_sw,
            "response_e": resp_ea,
            "best_time": best_t,
            "best_score": best_score,
            "final_reference": str(final_reference),
            "final_candidate": str(final_candidate),
            "samples": [{"time": t, "score": score} for t, score in scored],
        }
        with open(out_dir / "result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        print("\n=== 逐帧相似度 ===")
        for t, score in scored:
            print(f"  t={t:.3f}s  score={score:.4f}")
        print(f"\n最佳：ss:{best_t:.3f}s（相似度 {best_score:.4f}）")
        if best_t <= scored[0][0] or best_t >= scored[-1][0]:
            print("！最佳落在采样区间边缘：把 --start / --end 往那一侧挪再跑")
        print(f"最终对比图：{final_reference.name}  vs  {final_candidate.name}")
        print(f"结果目录：{out_dir}")
        return 0
    finally:
        try:
            if ops is not None:
                ops.handle.movement.release_held()
                ops.handle.back_to_main()
        except Exception:
            pass
        _restore_config(cfg, old_version, old_run, old_samples)


if __name__ == "__main__":
    sys.exit(main())
