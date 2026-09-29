"""校验地图 JSON —— 独立脚本，按路径运行。

    python tools/validate_maps.py              # 校验全部地图版本
    python tools/validate_maps.py default      # 只校验某个版本
    python tools/validate_maps.py --errors-only

退出码：有 error 则 1，只有 warning 或全通过则 0。可以直接接进 CI。

除了单张地图的结构，还会检查**展示名的覆盖**（CLAUDE.md R23）：磁盘上出现的版本目录
与星球编号，必须在 `utils/core/map_names.py` 里登记中文名 —— 以前 `default_lite`
就是漏登记的，图鉴一直显示裸目录名。
"""

import json
import re
import sys
from pathlib import Path

MAP_DIR = "map"
#: 地图文件名里的星球主号，如 map_1-2_3.json -> 1
PLANET_IN_FILENAME = re.compile(r"map_(\d+)-\d+_\d+\.json")
#: 地图名里的「区域-序号」，如「主控舱段-1」——区域层就是从它派生的
AREA_IN_NAME = re.compile(r"^.*-\d+$")


def load_schema():
    """import 校验器。

    直接按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，所以要显式补上。
    放在函数里而不是模块级 —— 模块级副作用会被 tests/test_architecture.py
    的棘轮拦下（那是给独立脚本定的规则）。
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core import schema

    return schema


def load_map_names():
    """import 展示名表（版本 / 星球），同 load_schema 的理由放在函数里。"""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core import map_names

    return map_names


def iter_map_files(version=None):
    root = Path(MAP_DIR)
    if not root.is_dir():
        print(f"找不到地图目录：{root.resolve()}")
        return
    versions = (
        [version] if version else sorted(p.name for p in root.iterdir() if p.is_dir())
    )
    for name in versions:
        folder = root / name
        if not folder.is_dir():
            print(f"找不到地图版本：{name}")
            continue
        for path in sorted(folder.glob("*.json")):
            yield name, path


def main(argv) -> int:
    # 打印中文前先把 stdout/stderr 掰成 UTF-8：GitHub 的 Windows runner 上它默认是
    # cp1252，中文编不出来会直接 UnicodeEncodeError、让整个 CI 步骤红掉；用户的
    # 日文/其它非 UTF-8 控制台同理（见 issue #428，utils/core/log.py 与 fhoe.py
    # 里有同样的处理）。
    # 放在 main 里而不是模块级：import 期副作用会被 tests/test_architecture.py 拦。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass

    schema = load_schema()
    names = load_map_names()

    only_errors = "--errors-only" in argv
    args = [a for a in argv if not a.startswith("--")]
    version = args[0] if args else None

    total = 0
    failed = 0
    reported = []
    seen_versions = set()
    seen_planets = set()
    odd_names = []

    for name, path in iter_map_files(version):
        total += 1
        seen_versions.add(name)
        match = PLANET_IN_FILENAME.match(path.name)
        if match:
            seen_planets.add(match.group(1))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            reported.append((path, [schema.Issue("error", path.name, f"JSON 解析失败: {e}")]))
            failed += 1
            continue

        map_name = data.get("name", "") if isinstance(data, dict) else ""
        if not AREA_IN_NAME.match(map_name or ""):
            odd_names.append((path, map_name))

        issues = schema.validate_map(data, filename=path.name)
        if only_errors:
            issues = [i for i in issues if i.level == "error"]
        if issues:
            if any(i.level == "error" for i in issues):
                failed += 1
            reported.append((path, issues))

    for path, issues in reported:
        print(f"\n{path.relative_to(Path(MAP_DIR).parent)}")
        for issue in issues:
            print(f"    {issue}")

    missing_versions = sorted(v for v in seen_versions if v not in names.VERSION_NAMES)
    missing_planets = sorted(p for p in seen_planets if p not in names.PLANET_NAMES)

    if odd_names:
        print()
        print("以下地图名不是「区域-序号」，图鉴里会自成一类区域（只是提醒，不算错误）：")
        for path, map_name in odd_names[:20]:
            print(f"    {path.name}: {map_name!r}")

    print()
    print("=" * 60)
    print(f"校验 {total} 个地图文件，{failed} 个有错误")
    if total:
        print(f"通过率 {(total - failed) / total * 100:.1f}%")

    if missing_versions or missing_planets:
        print()
        print("以下版本/星球没有登记中文名（图鉴会显示裸目录名，见 CLAUDE.md R23）：")
        for v in missing_versions:
            print(f"    map/{v}/  —— 去 utils/core/map_names.py 的 VERSION_NAMES 补一条")
        for p in missing_planets:
            print(f"    星球 {p}  —— 去 utils/core/map_names.py 的 PLANET_NAMES 补一条")

    return 1 if (failed or missing_versions or missing_planets) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
