"""按用途把 `picture/` 分类到子目录 —— 一次性迁移工具（可反复 dry-run）。

    python tools/classify_pictures.py            # 只打印映射与数量
    python tools/classify_pictures.py --write    # 执行 git mv，并改写 assets.py

为什么可以随便搬：地图 JSON 里的 `picture\\xxx.png` 是资源 ID，解析按 stem
（文件名去掉后缀）查递归索引（CLAUDE.md R25）。所以**只移动、不改名**，
JSON 与代码里的引用都不用动。唯一性由 `tools/validate_pictures.py` 在 CI 守。

分类规则见 `target_folder()`；`new_pic/` 是采样产物，不动。
"""

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

PICTURE_ROOT = "./picture"
ASSETS_FILE = Path(__file__).resolve().parent.parent / "utils" / "vision" / "assets.py"

#: 地图界面类：传送、楼层、返回、索引、开图。其余未识别的都落到 `ui/`。
MAP_UI = {
    "transfer",
    "fanhui_1",
    "fanhui_2",
    "1floor",
    "2floor",
    "3floor",
    "4floor",
    "first_floor",
    "second_floor",
    "third_floor",
    "b1floor",
    "b2floor",
    "b3floor",
    "b4floor",
    "map_back",
    "map_load",
    "map_shrink",
    "map_index",
    "map_index_1",
    "map_index_2",
    "map_index_3",
    "index",
    "index_2",
    "index_3",
    "index_4",
    "kaituoli_1",
    "contraction",
    "2",
}

#: 不在 `map_<星球>-<区>` 命名里的地图资产
MAP_POINT_EXTRA = {"token", "parcel"}
#: 视角/小地图
ORIENTATION_EXTRA = {"screenshot_arrow", "loc_arrow"}

#: 允许作为 map_points 子目录的星球编号；其余进 other/
PLANETS = {"1", "2", "3", "4", "5", "6", "9"}


def target_folder(stem):
    """文件名 stem → 目标子目录（相对 `picture/`，用 `/` 分隔）。"""
    s = stem.lower()
    if s.startswith("role_") or s == "silver_wolf_lv999_e":
        return "role"
    if s.startswith("f_") or s == "sw":
        return "f_icon"
    if s.startswith("orientation") or s in ORIENTATION_EXTRA:
        return "orientation"
    match = re.match(r"^map_(\d+)-\d+(_point_\d+)?$", s)
    if match:
        planet = match.group(1)
        return f"map_points/{planet if planet in PLANETS else 'other'}"
    match = re.match(r"^map_(\d+)(_point)?$", s)
    if match:
        planet = match.group(1)
        return f"map_points/{planet if planet in PLANETS else 'other'}"
    if re.match(r"^check_4-1_point_\d+$", s):
        return "map_points/4"
    if s in MAP_POINT_EXTRA:
        return "map_points/other"
    if s in MAP_UI:
        return "map_ui"
    return "ui"


def load_assets():
    """import 资源模块（函数里 import，避免被架构测试当成 import 期副作用）。"""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.vision import assets

    return assets


def build_plan(picture_root=PICTURE_ROOT):
    """返回 `[(源路径, 目标路径)]`；已经在目标目录里的文件不出现。"""
    assets = load_assets()
    plan = []
    for source in assets.iter_picture_files(picture_root):
        stem = os.path.splitext(os.path.basename(source))[0]
        folder = target_folder(stem)
        destination = os.path.join(picture_root, folder, os.path.basename(source))
        if os.path.normpath(source) != os.path.normpath(destination):
            plan.append((os.path.normpath(source), os.path.normpath(destination)))
    return plan


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0].lower()


def _registry_literal_updates(plan):
    """登记表里的旧路径字面量 → 新路径字面量。

    按 **stem** 匹配目标路径：登记表里写的是逻辑后缀（多为 `.png`），磁盘上
    往往是 `.webp`，所以不能拿旧路径字符串去计划表里找。目标路径用实际文件
    （含真实后缀），这样 `.png` 登记项也能写对。
    """
    assets = load_assets()
    moves = {os.path.normpath(source): destination for source, destination in plan}
    destination_by_stem = {_stem(destination): destination for _, destination in plan}
    updates = {}
    for asset in assets.ASSETS.values():
        old = os.path.normpath(asset.path)
        destination = moves.get(old) or destination_by_stem.get(_stem(asset.path))
        if destination is None:
            continue
        new = "./" + Path(destination).as_posix()
        if new != asset.path:
            updates[asset.path] = new
    return updates


def write_assets_file(updates):
    """把 assets.py 里的旧路径字面量替换成新路径，逐条校验出现次数。"""
    text = ASSETS_FILE.read_text(encoding="utf-8")
    for old, new in updates.items():
        needle = f'"{old}"'
        if text.count(needle) != 1:
            raise SystemExit(
                f"assets.py 里 {old} 出现了 {text.count(needle)} 次（预期 1 次），"
                "拒绝自动改写"
            )
        text = text.replace(needle, f'"{new}"')
    ASSETS_FILE.write_text(text, encoding="utf-8")


def _git_mv(source, destination):
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", source, destination], check=True)


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass

    assets = load_assets()
    _, duplicates = assets.scan_picture_files(PICTURE_ROOT)
    if duplicates:
        print("存在重名文件，拒绝迁移（先跑 tools/validate_pictures.py）：")
        for stem, paths in sorted(duplicates.items()):
            print(f"  {stem}: {'；'.join(paths)}")
        return 1

    plan = build_plan()
    counts = Counter(target_folder(os.path.splitext(os.path.basename(src))[0]) for src, _ in plan)
    print(f"待移动 {len(plan)} 个文件：")
    for folder, count in sorted(counts.items()):
        print(f"  {folder:20s} {count:3d}")
    if "--write" not in argv:
        for source, destination in plan:
            print(f"  {source} -> {destination}")
        print("（dry-run；加 --write 执行）")
        return 0

    updates = _registry_literal_updates(plan)
    for _, destination in plan:
        if os.path.exists(destination):
            print(f"目标已存在，拒绝迁移：{destination}")
            return 1
    write_assets_file(updates)  # 先改登记表：即使接下来 git mv 失败也不会两头不一致
    for source, destination in plan:
        _git_mv(source, destination)
    print(f"已移动 {len(plan)} 个文件，登记表改写 {len(updates)} 条。")
    print("接着跑：python tools/validate_pictures.py && python -m pytest tests/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
