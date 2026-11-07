"""
Author: linruowuyin
Description: 运行遥测：run_id + JSONL 事件流。

每次运行生成唯一 run_id；关键节点（run 开始/结束、每张地图开始/结束、
地图加载用时、wait 结果）追加一行 JSON 到 logs/telemetry.jsonl。
webui 的 /api/stats 与后续复盘工具读该文件即可拿到机器可读的运行数据。

设计约束：
- 纯标准库、无 import 副作用（R16）；
- 写失败静默吞掉 —— 遥测埋在跑图热路径上，任何异常都不能冒出去
  （get_ver 的教训：patcher 里的异常会从每个日志调用点冒出来）；
- 单文件按行追加，每行自带 run_id，跨午夜轮转/多轮运行互不干扰。
"""

import datetime
import json
import os
import secrets
import threading

TELEMETRY_PATH = os.path.join("logs", "telemetry.jsonl")

_lock = threading.Lock()
_run_id = ""


def new_run_id() -> str:
    """时间戳 + 4 位随机后缀，同秒内多次启动/跨进程都不撞。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def current_run_id() -> str:
    """当前 run 的 id；未开始运行时为空串。"""
    return _run_id


def start_run(**fields) -> str:
    """开始一次运行：生成 run_id 并写 run_start 事件。返回 run_id。"""
    global _run_id
    _run_id = new_run_id()
    event("run_start", **fields)
    return _run_id


def end_run(**fields) -> None:
    """结束当前运行（不清理 run_id，结束后的事件仍归属本次运行）。"""
    event("run_end", **fields)


def event(kind, **fields) -> None:
    """追加一条遥测事件。任何失败都静默吞掉。"""
    row = {
        "ts": datetime.datetime.now().isoformat(timespec="milliseconds"),
        "run_id": _run_id,
        "kind": kind,
    }
    row.update(fields)
    try:
        line = json.dumps(row, ensure_ascii=False, default=str)
        with _lock:
            os.makedirs(os.path.dirname(TELEMETRY_PATH), exist_ok=True)
            with open(TELEMETRY_PATH, "a", encoding="utf-8") as file:
                file.write(line + "\n")
    except Exception:
        # 遥测失败不能影响跑图，也不在这里打日志（log.py 反向依赖本模块）。
        pass
