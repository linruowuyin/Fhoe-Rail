"""月卡领取流程测试 —— 独立脚本，手动运行（不进 pytest / CI）。

    py tools/monthly_pass_flow_test.py
    py tools/monthly_pass_flow_test.py --picture monthly_pass_pic --threshold 0.91
    py tools/monthly_pass_flow_test.py --picture setting_icon --threshold 0.80 --delay 5

测的是 issue #450 修好的那条流程：**画面停在某个「ESC 关不掉」的界面时，
`Handle.back_to_main()` 能不能把它识别成月卡领取界面、点掉它、然后回到主界面。**
调用的是真实组件（真实截图、真实键鼠、真实的 `back_to_main`），不替身、不改任何文件。

为什么默认用 `setting_icon` 当测试图：真实的「今日补给」界面一天只出现一次，没法
反复测。设置菜单入口图标好触发（按 ESC 打开菜单就能看到），并且它登记为形状匹配
（`MATCH_SHAPE`），可以用它把「识别 → 点击 → 确认 → 回主界面」整条链路走一遍。
阈值默认 0.80：`setting_icon` 的探针实测负样本 ≤ 0.28、正样本 0.75–0.95。

手动步骤：
  1. 打开游戏，停在能看到测试图的界面（默认用法：ESC 菜单，能看到设置齿轮）
  2. 运行本脚本；需要管理员权限时会自动申请提权（主程序 fhoe.py 也是提权运行的，
     权限低于游戏进程时 `SetCursorPos` 会被 Windows 拒绝），提权后的新窗口里
     `--delay` 秒后开始
  3. 看输出与日志：当前匹配度 / 是否识别到 / `back_to_main` 是否成功

退出码：
  0  通过（识别命中并执行了领取点击，且回到了主界面）
  2  没认到测试图（可调 `--threshold` 或换图；`back_to_main` 本身正常）
  1  `back_to_main` 超时或执行出错

真实界面复验：每天早上 4 点刷新后停在「今日补给」界面，用
`--picture monthly_pass_pic --threshold 0.91` 跑一遍即可。
"""

import argparse
import os
import sys
import time

# 按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，不补就 import 不到 utils。
# 本工具多个函数都要用 utils，所以和 match_probe.py 一样放在模块级（不碰任何设备）。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from utils.core.exceptions import CustomException
from utils.flows.handle import Handle
from utils.flows.monthly_pass import MonthlyPass
from utils.vision import assets

#: 默认测试图：设置菜单入口（按 ESC 就能看到，形状匹配）
DEFAULT_PICTURE = "setting_icon"
#: 默认阈值：setting_icon 形状匹配的探针下沿（负样本 ≤ 0.28）
DEFAULT_THRESHOLD = 0.80

#: 提权后的子进程会继承这个环境变量 —— 用来在结束时停住窗口，别一闪而过
ELEVATED_CHILD_ENV = "FHOE_FLOW_TEST_ELEVATED"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="月卡领取流程测试（手动运行）")
    parser.add_argument(
        "--picture",
        default=DEFAULT_PICTURE,
        help=f"用哪张图代替月卡图（assets.py 里的 key），默认 {DEFAULT_PICTURE}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"识别阈值，默认 {DEFAULT_THRESHOLD}",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="激活窗口后等几秒再开始，留时间把游戏摆到目标界面，默认 3",
    )
    parser.add_argument(
        "--no-switch", action="store_true", help="不主动激活游戏窗口"
    )
    return parser.parse_args(argv)


def _relaunch_command():
    """提权重启的命令行（保留 --picture / --threshold 等参数）。"""
    return [sys.executable, os.path.abspath(__file__)] + sys.argv[1:]


def ensure_admin():
    """以管理员权限重新启动本程序；返回 True 表示已交给子进程，当前进程应退出。

    和 fhoe.py 的 `_ensure_admin` 同理：游戏的注入输入对权限敏感 —— 调用进程
    权限低于游戏进程时，`win32api.SetCursorPos` 会以
    `(0, 'SetCursorPos', 'No error message is available')` 失败（pywinauto
    记录过的症状）。主程序一直是提权运行的，本工具注入真实键鼠，也必须提权。
    """
    if sys.platform != "win32":
        return False
    import pyuac

    if pyuac.isUserAdmin():
        return False
    print("需要管理员权限才能给游戏注入鼠标（主程序 fhoe.py 也是提权运行的）。")
    print("正在申请提权，确认 UAC 后测试会在新窗口里重新开始……")
    os.environ[ELEVATED_CHILD_ENV] = "1"
    pyuac.runAsAdmin(cmdLine=_relaunch_command())
    return True


def main(argv=None):
    args = parse_args(argv)

    if ensure_admin():
        return 0

    if not 0 < args.threshold <= 1:
        print("--threshold 必须在 (0, 1] 之间")
        return 2

    # key 拼错要当场炸，而不是拿一个不存在的路径去识图
    try:
        picture_path = assets.path(args.picture)
    except KeyError as e:
        print(e)
        return 2

    handle = Handle()  # 构造时会找窗口；游戏没开时它自己会尝试启动
    if not args.no_switch:
        handle.window.switch_window()

    # 只换掉「识别图 + 阈值」，流程本身仍然是生产代码
    # （back_to_main → pre_esc 的 match_frame / claim_match）
    monthly = MonthlyPass(
        pass_pictures=((args.picture, f"流程测试图 {args.picture}"),),
        pass_threshold=args.threshold,
    )
    handle.monthly_pass = monthly

    print(f"测试图：{args.picture}（{picture_path}），阈值 {args.threshold}")
    print(
        f"请把游戏停在能看见这张图的界面（默认用法：打开 ESC 菜单看到设置齿轮），"
        f"{args.delay:g} 秒后开始……"
    )
    print(
        "提示：识别命中后会走完整的「点击 → 等动画 → 确认领取」流程，确认阶段会在"
        "(50%,75%) 点一次；用非月卡图测试时这一下可能落在别的 UI 上，测完看一眼游戏设置。"
    )
    time.sleep(max(args.delay, 0.0))

    if handle.img.on_main_interface(timeout=0.0, allow_log=False):
        print("当前已经是主界面：back_to_main 会直接返回，不会走到月卡识别。")
        print("请先把游戏摆到目标界面（比如按 ESC 打开菜单）再运行本测试。")
        return 2

    # 先单独量一次分，方便调阈值；这一步只读，不点击
    try:
        template = handle.img.get_img(picture_path)
        if template is None:
            print(f"图片加载失败：{picture_path}")
            return 2
        score = handle.img.scan_screenshot(template)["max_val"]
        print(f"当前画面匹配度：{score:.3f}（阈值 {args.threshold}）")
    except Exception as e:
        print(f"预扫描失败：{e}")

    print("开始执行 handle.back_to_main() …")
    started = time.time()
    try:
        handle.back_to_main()
    except CustomException as e:
        print(f"失败：back_to_main 未能在超时内回到主界面 —— {e}")
        return 1
    except Exception as e:
        if "SetCursorPos" in str(e):
            print(
                "失败：SetCursorPos 被系统拒绝 —— 调用进程的权限低于游戏进程时"
                "Windows 会这样拒绝鼠标移动。确认 UAC 提权成功，或把游戏和本工具"
                "都用管理员身份运行后重试。"
            )
        else:
            print(f"失败：执行中出错 —— {e}")
        return 1
    elapsed = time.time() - started

    if monthly.have_monthly_pass:
        print(
            f"通过：识别命中并执行了领取点击（月卡状态 CLAIMED），"
            f"回到主界面用时 {elapsed:.1f}s"
        )
        return 0

    print(f"未命中：{args.picture} 没达到阈值 {args.threshold}。")
    print(f"back_to_main 已回到主界面，用时 {elapsed:.1f}s。")
    print("可调低 --threshold，或换一张更稳的测试图后重跑。")
    return 2


if __name__ == "__main__":
    _exit_code = main()
    # 提权后的子进程是新开的一个控制台；不停一下会一闪而过，看不到结果
    if os.environ.get(ELEVATED_CHILD_ENV) == "1":
        try:
            input("测试结束，按回车关闭窗口……")
        except EOFError:
            pass
    sys.exit(_exit_code)
