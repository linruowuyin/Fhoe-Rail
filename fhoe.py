# -*- coding: utf-8 -*-
import os
import sys

# 强制控制台使用UTF-8编码，防止cp932等非中文编码导致UnicodeEncodeError
os.environ["PYTHONIOENCODING"] = "utf-8"
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name)
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import subprocess
import time
import traceback

import pyuac

# 日文系统(cp932)下中文输出会崩,统一把 stdout/stderr 改成 UTF-8
# 要在 import utils.core.log 之前执行
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # 部分环境（如某些重定向场景）不支持 reconfigure，忽略即可


def _is_webui_server_mode(argv=None):
    """命令行里是否带 `--webui-server`（单入口 WebUI 模式）。"""
    return "--webui-server" in (sys.argv[1:] if argv is None else argv)


def _run_webui_server():
    """`Fhoe-Rail.exe --webui-server`：用同一个 exe 启动 WebUI 服务。

    必须在导入产品代码之前处理：WebUI 只依赖标准库和少量 utils，不需要主程序的
    装配（`Setting()` / `MapInfo()` / `Notify()` 在模块级就会读配置和地图目录）。
    以前 WebUI 是独立的 `webui-server.exe`，图片探针上线后它也要带 cv2 / numpy，
    等于把同一套库在发布包里打了两份（约 +50MB）。单入口后只保留主程序这一份。
    """
    if sys.platform == "win32" and not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
        sys.exit(0)
    from webui.server import main as webui_main

    sys.exit(webui_main())


if _is_webui_server_mode():
    _run_webui_server()

from get_width import check_mult_screen
from utils.config.config import ConfigurationManager
from utils.core.log import fetch_php_file_content, log
from utils.flows.map_operations import MapOperations
from utils.core.map_info import MapInfo
from utils.ui.map_selector import choose_map, choose_map_debug
from utils.core.notify import Notify, get_error_summary
from utils.core.ports import SYSTEM_CLOCK
from utils.ui.setting import Setting
from utils.core.time_utils import TimeUtils
from utils.drivers.window import Window

cfg = ConfigurationManager()

cfg = ConfigurationManager()
time_mgr = TimeUtils()
map_info_instance = MapInfo()
setting = Setting()
notify = Notify()


def filter_content(content, keyword):
    # 将包含指定关键词的部分替换为空字符串
    return content.replace(keyword, "")


def print_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as file:
            version = file.read().strip()
            log.info(f"当前版本：{version}")
        log.info(f"{cfg.CONFIG_FILE_NAME}")
        ConfigurationManager.modify_json_file(
            ConfigurationManager.CONFIG_FILE_NAME, "version", version
        )
        cfg.config_file.get("version", "")
    except (FileNotFoundError, IOError) as e:
        log.error(f"版本文件读取错误: {e}")


def print_info():
    log.info("")  # 添加一行空行
    php_content = fetch_php_file_content()  # 获取PHP文件的内容
    filtered_content = filter_content(php_content, "舔狗日记")  # 过滤关键词
    log.info("\n" + filtered_content)  # 将过滤后的内容输出到日志
    log.info("")  # 添加一行空行
    log.info("=" * 60)
    log.info("开始运行")
    print_version()


def print_end():
    log.info("结束运行")
    log.info("=" * 60)
    # 清理 keyboard 全局监听（Pause 注册的 F7-F10 监听线程非 daemon，
    # 不清理会导致进程结束后无法退出）
    try:
        import keyboard

        keyboard.unhook_all()
    except Exception:
        pass


def parse_map_arg():
    """解析 --map <地图ID> 参数：非交互单图运行（WebUI 单图运行/开发者单图运行）。
    例如: fhoe.py --map 3-5_1
    """
    if "--map" in sys.argv:
        idx = sys.argv.index("--map")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def parse_range_arg():
    """解析 --range <起点地图ID> <终点地图ID>：区间运行（按地图列表顺序，含两端）。

    例如: fhoe.py --range 3-5_1 3-5_2
    """
    if "--range" not in sys.argv:
        return None
    idx = sys.argv.index("--range")
    values = [value for value in sys.argv[idx + 1: idx + 3] if not value.startswith("--")]
    return (
        values[0] if values else None,
        values[1] if len(values) > 1 else None,
    )


def parse_map_version_arg():
    """解析 --map-version <版本名> 参数：临时覆盖地图版本（供 WebUI 选图运行使用）"""
    if "--map-version" in sys.argv:
        idx = sys.argv.index("--map-version")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


# 录制 / 测试模式自己就把事情做完了，不产生起始地图
_MODE_DONE = object()


def _start_for_mode(mode, map_arg, range_arg=None):
    """按启动模式决定怎么开局，返回 `(start, dev)`。

    `start` 是 `choose_map*` 的产出（也可能是 `(地图, start_in_mid)` 元组）；
    `_MODE_DONE` 表示这个模式已经做完、不用再跑图。

    各模式的差别只有三件事 —— **准备配置的方式**、**怎么挑起始地图**、**是不是开发者模式**：

        --map     单图运行：用 --map 给的那张图开局
        --range   区间运行：用 --range 给的起点开局（终点由 run_once 传给 process_map）
        --debug   三级菜单选图（同时给了 --map 就直接用）
        --dev     同 --debug，另外跑完自动重选地图
        --config  先走一遍配置重写，再三级菜单选图
        --white   按配置直接开局，并开启一次白名单模式
        --record  进录制模式（不跑图）
        --test    只切一次窗口（不跑图）
        其他/无   按配置直接开局
    """
    if mode == "--record":
        from utils.ui.record import record_main

        record_main()
        return _MODE_DONE, False

    if mode == "--test":
        cfg.main_start()
        Window().switch_window()
        return _MODE_DONE, False

    if mode == "--config":
        cfg.main_start_rewrite(setting)
        return choose_map_debug(map_info_instance), False

    cfg.main_start()  # 其余模式都以「补全默认配置」开场，原先在 7 个分支里各写了一遍
    if mode == "--range":
        start = (range_arg[0], False)
    elif mode == "--map":
        start = (map_arg, False)
    elif mode in ("--debug", "--dev"):
        start = (
            choose_map_debug(map_info_instance) if not map_arg else (map_arg, False)
        )
    else:  # --white / 未知参数 / 没带参数
        start = choose_map(map_info_instance)

    if mode == "--white":
        # 启用一次白名单模式
        cfg.modify_json_file(cfg.CONFIG_FILE_NAME, "allowlist_mode_once", True)
    return start, mode == "--dev"


def main():

    start_in_mid = False  # 是否为优先地图，优先地图完成后自动从1-1_0开始
    map_arg = parse_map_arg()  # --map：单图运行
    range_arg = parse_range_arg()  # --range 起点 终点：区间运行

    if range_arg is not None:
        range_start, range_end = range_arg
        if not range_start or not range_end:
            log.error(
                "区间运行（--range）需要两个参数：起点地图ID 和 终点地图ID，"
                "例如 --range 3-5_1 3-5_2"
            )
            return
        if map_arg:
            log.error("单图运行（--map）与区间运行（--range）不能同时使用，请只选一种")
            return
    range_end = range_arg[1] if range_arg is not None else None
    single_map_mode = map_arg is not None or range_arg is not None

    # WebUI 单图/区间运行：若指定了 --map-version，临时切换地图版本（进程退出前恢复）
    map_version_arg = parse_map_version_arg()
    old_map_version = cfg.swap_map_version(map_version_arg)
    if old_map_version is not None:
        # 直接同步 MapInfo 单例缓存，避免 property 延迟检测
        map_info_instance._map_version = map_version_arg
        cfg._config = None
        log.info(f"[单次运行] 临时切换地图版本: {map_version_arg}")

    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if range_arg is not None:
        # --range 可能出现在 argv 的任意位置；区间运行本身就是一次跑图，
        # 与其它启动模式同时给出时以它为准，并明确提示被忽略的模式。
        if mode and mode != "--range":
            log.warning(f"检测到 --range，忽略启动模式 {mode}，按区间运行处理")
        mode = "--range"
    start, dev = _start_for_mode(mode, map_arg, range_arg)
    if start is _MODE_DONE:  # 录制 / 测试模式：自己干完了，不再跑图
        return

    if isinstance(start, tuple):
        start_in_mid, start = start[1], start[0]

    if start:
        try:
            run_once(
                start,
                start_in_mid,
                dev=dev,
                single_map_mode=single_map_mode,
                range_end=range_end,
            )
            if dev:  # 开发者模式自动重选地图
                main()
        finally:
            if old_map_version is not None:
                try:
                    cfg.modify_json_file(
                        cfg.CONFIG_FILE_NAME, "map_version", old_map_version
                    )
                    map_info_instance._map_version = old_map_version
                    cfg._config = None
                    log.info(f"[单次运行] 恢复地图版本: {old_map_version}")
                except Exception:
                    pass
    else:
        log.info("前面的区域，以后再来探索吧")
        main()


def shutdown_computer(shutdown_type):
    if shutdown_type == 0:
        pass
    elif shutdown_type == 1:
        log.info("下班喽！I'm free!")
        os.system("shutdown /s /f /t 10")
    elif shutdown_type == 2:
        log.info("10秒后注销")
        time.sleep(10)
        os.system("shutdown /l /f")
    elif shutdown_type == 3:
        log.info("关闭指定进程")
        taskkill_name = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
            "taskkill_name", None
        )
        if taskkill_name:
            subprocess.call(["taskkill", "/im", taskkill_name, "/f"])
    else:
        log.info("shutdown_type参数不正确")


def _cross_day(
    map_instance,
    start_map,
    start_in_mid,
    dev,
    start_time,
    end_time,
    *,
    single_map_mode=False,
    cfg=cfg,
    time_mgr=time_mgr,
    clock=SYSTEM_CLOCK,
):
    """跨日连锄：这一趟跑完之后，要不要等到刷新点再跑一趟。

    三种结局：

      * 这一趟已经把刷新点跨过去了 → 体力已经刷新，立刻从头再跑
      * 还没到刷新点 → 回主界面，等到刷新点再跑
      * 要等超过 `CROSS_DAY_MAX_WAIT`（4 小时）→ 放弃

    「要不要等、等多久」是纯时间计算，在 `TimeUtils.cross_day_wait` 里；这里只负责把它
    接到 map_instance 和时钟上。
    """
    if single_map_mode or not cfg.read_json_file(
        cfg.CONFIG_FILE_NAME, False
    ).get("allow_run_next_day", False):
        return

    log.info("开始执行跨日连锄")
    if time_mgr.has_crossed_refresh(start=start_time, end=end_time):
        log.info("检测到换日，即将从头开锄")
        map_instance.process_map(start_map, start_in_mid, dev=dev)
        return

    map_instance.handle.back_to_main(delay=2.0)
    # back_to_main 之后再取「现在」—— 它本身要花两秒，顺序反过来等待时长会差两秒
    wait_time = time_mgr.cross_day_wait(
        clock.now(),
        cfg.config_file.get("refresh_hour", 4),
        cfg.config_file.get("refresh_minute", 0),
    )
    if wait_time is None:
        log.info("等待时间过久，结束跨日连锄，等待时间需要 < 4小时")
        return
    log.info(f"等待 {wait_time:.0f} 秒后游戏换日重锄")
    clock.sleep(wait_time)
    map_instance.process_map(start_map, start_in_mid, dev=dev)


def _summary_value(source, *path):
    """按属性路径读一个统计值；路径上任何一层缺失都返回 None，不抛。

    Handle 拆分后战斗计数在 `handle.combat`、疾跑/卡顿在 `handle.movement`，
    不能再直接读 `handle.total_fight_cnt` —— 那样会 AttributeError，被外层
    的 except 吞掉，结束通知就再也不会发出去。
    """
    for attr in path:
        source = getattr(source, attr, None)
        if source is None:
            return None
    return source


def run_once(
    start,
    start_in_mid,
    *,
    dev=False,
    single_map_mode=False,
    range_end=None,
    cfg=cfg,
    time_mgr=time_mgr,
    notify=notify,
    clock=SYSTEM_CLOCK,
    window_factory=Window,
    map_ops_factory=MapOperations,
    check_screens=check_mult_screen,
    shutdown=shutdown_computer,
):
    """跑一趟：装配 → 切窗口 → 跑图 → 跨日连锄 → 关机/注销。

    `range_end` 非空时是**区间运行**：只跑 `start` 到 `range_end` 之间的地图
    （含两端）；它和 `single_map_mode` 一样属于「跑完就停」，不触发再次运行 /
    跨日连锄。

    从 `main()` 抽出来是为了可测。`main()` 一跑就会切窗口、启动游戏窗口，单测驱动不
    了；这里所有会碰外部世界的东西（窗口、地图流程、时钟、分辨率检查、关机）都是参数，
    测试传替身进来就能断言编排顺序 —— 例如「关机必须排在跨日连锄之后」。

    默认值在**函数定义时**就绑定了模块级对象：测试要替换请显式传参，
    monkeypatch `fhoe.Window` 之类不会改变这里的默认值。
    """
    cfg.config_fix()
    log.info(f"config.json:{cfg.load_config()}")
    log.info("切换至游戏窗口，请确保1号位角色普攻为远程，黄泉地图1号位为黄泉，银狼LV.999地图1号位为银狼LV.999")
    check_screens()
    window_factory().switch_window()

    map_instance = map_ops_factory()
    clock.sleep(0.5)
    log.info("开始运行，请勿移动鼠标和键盘.向着星...呃串台了")
    log.info("黑塔：7128；雅利洛：19440；罗浮：42596；匹诺康尼：30996")
    log.info("2.0版本单角色锄满100160经验（fhoe当前做不到）")
    log.info("免费软件，倒卖的曱甴冚家铲，请尊重他人的劳动成果")
    start_time = clock.now()
    notify.send_start(start)
    map_instance.process_map(
        start, start_in_mid, dev=dev, single_map=single_map_mode, end=range_end
    )  # 读取配置
    start_map = "1-1_0"
    allow_run_again = not single_map_mode and cfg.read_json_file(
        cfg.CONFIG_FILE_NAME, False
    ).get("allow_run_again", False)
    if allow_run_again:
        map_instance.process_map(start_map, start_in_mid, dev=dev)
    end_time = clock.now()

    # 结束通知（含统计摘要）
    try:
        summary = {
            "总计用时": _summary_value(map_instance, "map_statu", "total_time"),
            "战斗次数": _summary_value(
                map_instance, "handle", "combat", "total_fight_cnt"
            ),
            "未战斗次数": _summary_value(
                map_instance, "handle", "combat", "total_no_fight_cnt"
            ),
            "疾跑节约": _summary_value(
                map_instance, "handle", "movement", "tatol_save_time"
            ),
            "系统卡顿": _summary_value(
                map_instance, "handle", "movement", "time_error_cnt"
            ),
        }
        summary = {k: v for k, v in summary.items() if v is not None}
        notify.send_end(summary)
    except Exception as e:
        log.warning(f"结束通知发送失败: {e}")
    # cfg / time_mgr / clock 要显式传下去：_cross_day 的默认值是模块级的那几个，
    # 不传的话 run_once 收到的替身（测试注入的）就到不了跨日这一段
    _cross_day(
        map_instance,
        start_map,
        start_in_mid,
        dev,
        start_time,
        end_time,
        single_map_mode=single_map_mode,
        cfg=cfg,
        time_mgr=time_mgr,
        clock=clock,
    )
    # 关机/注销必须排在跨日连锄之后：两者同时开启时，先关机等于把跨日等待整段废掉
    shutdown_type = cfg.read_json_file(cfg.CONFIG_FILE_NAME, False).get(
        "auto_shutdown", 0
    )
    shutdown(shutdown_type)


if __name__ == "__main__":
    try:
        if not pyuac.isUserAdmin():
            pyuac.runAsAdmin()
        else:
            print_info()
            main()
            print_end()
    except BaseException:
        print(traceback.format_exc())
        log.error(traceback.format_exc())
        # 出错通知
        try:
            notify.send_error(get_error_summary(sys.exc_info()[1]))
        except Exception:
            pass
        print("请重新运行")
        try:
            input("按回车键退出")
        except EOFError:
            pass  # WebUI 等无 stdin 环境下不阻塞退出
