"""检查 / 重写地图 JSON 的写盘格式 —— 独立脚本，按路径运行（CLAUDE.md R22）。

    python tools/format_maps.py                        # 只查本次改动过的地图（CI 用这个）
    python tools/format_maps.py --base origin/master   # 指定 diff 基线
    python tools/format_maps.py --all                  # 查全库 633 张（别接进 CI，见下）
    python tools/format_maps.py --write                # 把查出来的文件按规范重写

退出码：有文件不是规范形式则 1，全通过（或没有改动过的地图）则 0。

**为什么默认只查改动的**：全库 633 张里有 471 张是历史格式（4 / 2 / 顶格 / 7 空格
四种缩进，221 张还混着 Tab），它们大多来自上游。卡全库等于要求一次性重排 471 个
文件：PR 会被空白淹没，而且以后上游每改一张图都跟本地冲突。所以这里只拦「本次改动
的地图」；要重排全库是显式的 `--all --write`。

行尾符不算格式问题（`core.autocrlf=true`，提交时会归一），只比缩进 / 数组内联 /
末尾换行。JSON 都解析不了的图不在这里判，交给 `tools/validate_maps.py`。
"""

import json
import subprocess
import sys
from pathlib import Path
from pathlib import PurePosixPath

MAP_DIR = "map"

# 系统语言兼容（issue #428 同类问题）：日文系统 cp932 代码页下中文 print 会崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def load_json_io():
    """import 序列化器。

    直接按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，所以要显式补上；
    放在函数里而不是模块级 —— 模块级副作用会被 tests/test_architecture.py
    的棘轮拦下（同 tools/validate_maps.py）。
    """
    root = str(default_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core import json_io

    return json_io


def default_repo_root():
    """按脚本位置推仓库根。"""
    return Path(__file__).resolve().parent.parent


def parse_args(argv):
    opts = {"all": False, "write": False, "base": None}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--all":
            opts["all"] = True
        elif arg == "--write":
            opts["write"] = True
        elif arg.startswith("--base="):
            opts["base"] = arg.split("=", 1)[1] or None
        elif arg == "--base":
            i += 1
            opts["base"] = (argv[i] if i < len(argv) else "") or None
        else:
            raise SystemExit(f"未知参数：{arg}（用法见文件头）")
        i += 1
    return opts


def _git(repo_root, *args):
    """跑一条 git 命令；失败返回 None。"""
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def is_map_json(rel_path):
    """只认 map/<版本>/xxx.json 这个形状，跟 validate_maps 的范围一致。"""
    parts = PurePosixPath(rel_path).parts
    return len(parts) == 3 and parts[0] == MAP_DIR and parts[2].endswith(".json")


def pick_base(repo_root, explicit):
    """挑一个能用的 diff 基线，返回 (ref, 说明给日志看的名字)。

    CI 传的是 `github.event.before`：新分支首次推送时它是 40 个 0，取不到；
    这时退回默认分支的 merge-base —— 语义正好是「这条分支相对默认分支改了什么」。
    """
    candidates = ([explicit] if explicit else []) + [
        "origin/master",
        "origin/main",
        "master",
        "main",
    ]
    for ref in candidates:
        out = _git(repo_root, "merge-base", ref, "HEAD")
        if out and out.strip():
            return out.strip(), ref
    if _git(repo_root, "rev-parse", "--verify", "HEAD~1"):
        return "HEAD~1", "HEAD~1"
    return None, None


def changed_map_files(repo_root, base):
    """相对 base 改动过（含工作区未提交、含未跟踪）的地图文件，仓库相对路径。

    对 base 用一次 diff（不写 HEAD，这样未提交的改动也算「改动」）——
    本地「提交前先查一遍」的用法才成立。
    """
    names = set()
    out = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", base, "--", MAP_DIR)
    if out is None:
        return None
    names.update(out.splitlines())
    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard", "--", MAP_DIR)
    if untracked:
        names.update(untracked.splitlines())
    return sorted(n for n in names if is_map_json(n))


def all_map_files(repo_root):
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / MAP_DIR).glob("*/*.json")
    )


def main(argv, repo_root=None):
    opts = parse_args(argv)
    root = Path(repo_root) if repo_root else default_repo_root()
    json_io = load_json_io()

    if opts["all"]:
        targets = all_map_files(root)
        print(f"检查全库 {len(targets)} 个地图文件")
        if opts["write"]:
            print("！--all --write 会重排全库：PR 里会出现大量纯空白改动，确认这是你要的")
    else:
        base, how = pick_base(root, opts["base"])
        if base is None:
            print("！拿不到 git 基线（origin/master、HEAD~1 都不存在），本次不检查任何文件")
            return 0
        targets = changed_map_files(root, base)
        if targets is None:
            print(f"！git diff 失败（基线 {how}），本次不检查任何文件")
            return 0
        print(f"检查本次改动的地图（基线 {how}）：{len(targets)} 个文件")

    bad, fixed, skipped = [], [], []
    for rel in targets:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            skipped.append(f"{rel}（读不了：{e}）")
            continue
        if json_io.is_canonical(text):
            continue
        try:
            data = json.loads(text)
        except ValueError as e:
            skipped.append(f"{rel}（JSON 解析失败，交给 tools/validate_maps.py：{e}）")
            continue
        if opts["write"]:
            path.write_text(json_io.dumps_map(data), encoding="utf-8")
            fixed.append(rel)
        else:
            bad.append(rel)

    for note in skipped:
        print(f"！跳过 {note}")

    if opts["write"]:
        for rel in fixed:
            print(f"  重排 {rel}")
        print(f"已按规范重排 {len(fixed)} 个文件")
        return 0

    if bad:
        print()
        print("以下地图不是规范形式（R22：4 空格 + 短数组内联 + 末尾不加换行）：")
        for rel in bad:
            print(f"    {rel}")
        print()
        print("修法：python tools/format_maps.py --write")
        print("     （在 webui 里把这张图保存一次也等效）")
        return 1

    checked = len(targets) - len(skipped)
    if not checked:
        print("没有需要检查的地图文件")
        return 0
    print(f"{checked} 个文件都是规范形式")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
