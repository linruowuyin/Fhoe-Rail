"""校验图片资源 —— 独立脚本，按路径运行。

    python tools/validate_pictures.py

退出码：有 error 则 1，全通过则 0。可以直接接进 CI。

检查两件事（CLAUDE.md R25）：

1. **文件名（stem）全局唯一**（大小写不敏感，`new_pic/` 除外）。地图 JSON 里的
   `picture\\xxx.png` 是资源 ID，解析时忽略目录、按 stem 查索引 —— 两个同名文件
   会让"指向哪一个"取决于遍历顺序。目录只是分类，名字才是身份。
2. **地图 JSON 里的每处 `picture\\...` 引用都能解析到文件**。以前拼错一个图片名，
   要跑图跑到那一步才炸；现在 CI 就拦。

重名与缺失都是 error；没有 warning。
"""

import json
import sys
from pathlib import Path

MAP_DIR = "map"
#: 引用前缀：地图数据里统一写 `picture\\xxx.png`（JSON 里是双反斜杠）。
PICTURE_PREFIXES = ("picture\\", "picture/")


def load_modules():
    """import 资源模块。

    按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，所以要显式补上。
    放在函数里而不是模块级 —— `utils.vision.images` 会连锁 import `core.log`
    （import 时建 logs/），模块级副作用会被 tests/test_architecture.py 拦下。
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.vision import assets
    from utils.vision import images

    return assets, images


def iter_map_files(map_dir=MAP_DIR):
    """所有地图版本下的 JSON 文件。"""
    root = Path(map_dir)
    if not root.is_dir():
        print(f"找不到地图目录：{root.resolve()}")
        return
    for path in sorted(root.glob("*/*.json")):
        yield path


def _iter_strings(node):
    """递归取出 JSON 里所有字符串（键和值）。"""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_strings(key)
            yield from _iter_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_strings(item)


def picture_refs(data):
    """一张地图里所有 `picture\\...` 引用（去重、排序）。"""
    return sorted(
        {
            text
            for text in _iter_strings(data)
            if text.startswith(PICTURE_PREFIXES)
        }
    )


def check(map_dir=MAP_DIR):
    """执行全部检查，返回 `(errors, stats)`。

    :param map_dir: 地图目录，默认仓库根的 `map/`
    :return: `(错误信息列表, 统计字典)`
    """
    assets, images = load_modules()

    errors = []
    index, duplicates = assets.scan_picture_files()
    for stem, paths in sorted(duplicates.items()):
        errors.append(f"文件名重名：{stem!r} 出现在多个目录：{'；'.join(paths)}")

    map_count = 0
    ref_count = 0
    missing = {}
    for path in iter_map_files(map_dir):
        map_count += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"读不出地图 {path}：{error}")
            continue
        for ref in picture_refs(data):
            ref_count += 1
            if not Path(images.resolve_path(ref)).is_file():
                missing.setdefault(ref, []).append(path.name)

    for ref, files in sorted(missing.items()):
        errors.append(
            f"图片引用无法解析：{ref}（出现在 {len(files)} 张地图，如 {files[0]}）"
        )

    stats = {
        "images": len(index),
        "maps": map_count,
        "refs": ref_count,
    }
    return errors, stats


def main() -> int:
    # 中文输出先掰成 UTF-8：GitHub 的 Windows runner 默认 cp1252，
    # 与 tools/validate_maps.py 的处理一致。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass

    errors, stats = check()
    print(
        f"图片资源 {stats['images']} 张；地图 {stats['maps']} 张，"
        f"图片引用 {stats['refs']} 处"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"共 {len(errors)} 个错误")
        return 1
    print("检查通过：文件名唯一，全部图片引用可解析")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
