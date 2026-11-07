"""把地图 JSON 从 v1 批量迁移到 v2 —— 独立脚本，按路径运行（docs/MAP_FORMAT.md）。

    python tools/migrate_maps_v2.py map/default            # 只看会改什么（默认干跑）
    python tools/migrate_maps_v2.py map/default --write    # 真正写盘
    python tools/migrate_maps_v2.py map/default/map_1-1_1.json --write

做什么：
    * 顶层加 "v": 2
    * start 里的 `picture\\x.png` 键改写 `{"img": "x", "delay": <原值>}`
    * 相邻且完全相同的单键步骤合并成 rep=N（fighting 永不合并）
    * 写盘走 utils/core/json_io.py::dumps_map（CLAUDE.md R22 规范形式）

安全网：每个文件迁移后都做一次「归一化往返校验」——migrated 展开回运行时规范形
必须与 original 逐条相等（utils/core/map_format.py::verify_migration）。
任何一个文件过不了校验就拒绝写盘并在最后列出；已迁移（v:2）的文件自动跳过。
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_repo_modules():
    """import 纯逻辑模块；放函数里避免模块级副作用（tests/test_architecture.py）。"""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core import json_io, map_format

    return json_io, map_format


def iter_targets(paths):
    """展开命令行路径：目录按 map/<版本>/*.json 收，文件原样收。"""
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(path.glob("*/*.json"))
        elif path.is_file():
            yield path
        else:
            print(f"！路径不存在，跳过：{path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v1 → v2 地图格式迁移（默认干跑）")
    parser.add_argument("paths", nargs="+", help="地图目录（map/<版本>/）或单个地图文件")
    parser.add_argument("--write", action="store_true", help="真正写盘（缺省只报告）")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass

    json_io, map_format = load_repo_modules()

    changed = 0
    skipped_v2 = 0
    failed = []
    steps_before = steps_after = 0

    for path in iter_targets(args.paths):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            failed.append(f"{path}：读不出来（{e}）")
            continue
        if not isinstance(data, dict) or "map" not in data:
            failed.append(f"{path}：不像地图文件（没有 map 数组），跳过")
            continue
        if data.get("v") == map_format.V2_VERSION:
            skipped_v2 += 1
            continue

        migrated = map_format.migrate_map(data)
        if not map_format.verify_migration(data, migrated):
            failed.append(f"{path}：迁移后语义校验不过（往返展开不一致），拒绝迁移")
            continue

        steps_before += len(data.get("start", [])) + len(data.get("map", []))
        steps_after += len(migrated["start"]) + len(migrated["map"])

        text = json_io.dumps_map(migrated)
        if text == path.read_text(encoding="utf-8"):
            continue  # 数据没变化（本来就不可能，v1→v2 必有 v 字段；防御性保留）
        changed += 1
        if args.write:
            path.write_text(text, encoding="utf-8")
            print(f"  已迁移 {path}")
        else:
            print(f"  [干跑] {path}")

    saved = steps_before - steps_after
    print()
    print(
        f"{'迁移' if args.write else '检查'} {changed} 个文件"
        f"（跳过已是 v2：{skipped_v2}）；"
        f"步骤数 {steps_before} → {steps_after}（rep 合并省 {saved} 条）"
    )
    if failed:
        print(f"\n{len(failed)} 个文件有问题，未写盘：")
        for line in failed:
            print(f"  {line}")
        return 1
    if not args.write and changed:
        print("以上是干跑结果，加 --write 落盘")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
