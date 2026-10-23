"""黄泉地图批量转换：读 `map/HuangQuan`，输出一份新版本到 `map/SilverWolfLv999`。

    python tools/convert_huangquan_check_e.py
        # 交互：输入目录、输出目录、模式、起止序号（输出目录已有文件时必须显式选起始）
    python tools/convert_huangquan_check_e.py --list
        # 只打印按路线顺序编号的清单（序号 / 文件名 / e 条数 / 输出是否存在）
    python tools/convert_huangquan_check_e.py --mode with-e --from 195 --to 210 --write
        # 只导出第 195–210 个文件（含两端），其它文件一个字节都不动
    python tools/convert_huangquan_check_e.py --mode with-e --from 195 --write
        # 结束序号省略 = 从第 195 个一直到最后一个

**为什么按序号导出**：输出目录（`map/SilverWolfLv999/`）会被人工微调，甚至刻意
删掉某些图。如果每次都全量重写，微调会被覆盖，删掉的图也会被加回来。按「第 N 到
第 M 个」导出，就只影响你选中的区间；区间外的文件（包括你删掉的）完全不碰。
结束序号省略时一直导出到最后。序号按 `utils/core/map_info.py::MapInfo.sort_json_files`
的路线顺序排：先星球、再区块、再序号，是游戏里实际跑图的顺序。若担心以后中间插入
新图导致序号后移，可以用 `--from-map <文件名>` 代替起始序号。

两种模式：

    with-e（默认）  只给确实含有 `{"e": 2}` 的地图删 e 并插 `{"lv999_e": 1}`
    always          区间内**所有**地图都插 `{"lv999_e": 1}`（不管有没有 e 步骤）

转换规则（只动 `data["map"]`，`start` 原样保留）：

  * 只删除**单键且值恰好为 2** 的 `{"e": 2}` —— `map_3-4_7.json` 里的
    `{"e": 1}` 保留。
  * `with-e` 模式下，没有 e 步骤的文件 map 原样保留，不插 `lv999_e`。
  * 插入时保证 `map` 最前面有且只有一条 `{"lv999_e": 1}`：已有条目会被收掉重插，
    值统一成 1，因此重复转换是幂等的。
  * 区间内的文件都会写入输出目录（无需改动的也写，保证目录完整）；区间外的文件
    不读不写。

写盘一律走 `utils/core/json_io.dumps_map`（CLAUDE.md R22）：4 空格缩进 + 短数组
内联 + 末尾不加换行。`{"lv999_e": 1}` 与其它步骤同构，不会内联成一行。

退出码：有文件读不了 / 解析失败 / 结构不对时 1；参数或输入输出目录有问题时 2；
其余 0。
"""

import json
import os
import sys
from pathlib import Path

#: 默认输入 / 输出目录（相对仓库根）。SilverWolfLv999 是 config.py 里预置的
#: 地图版本目录，原仓库还没有这张文件夹（CLAUDE.md R24）。
DEFAULT_INPUT = ("map", "HuangQuan")
DEFAULT_OUTPUT = ("map", "SilverWolfLv999")

MODE_WITH_E = "with-e"
MODE_ALWAYS = "always"
MODE_LABELS = {MODE_WITH_E: "有E才加", MODE_ALWAYS: "无E也加"}
MODE_PROMPT = {"": MODE_WITH_E, "1": MODE_WITH_E, "2": MODE_ALWAYS}

#: 插入到 `map` 最前面的步骤。写盘时和其它步骤走同一个 `dumps_map`，
#: 因此格式与既有条目完全一致：单独一行 `{`、12 空格缩进的 `"lv999_e": 1`、
#: 单独一行 `},` —— 不要手工拼字符串，也不要把对象内联。
LV999_E_STEP = {"lv999_e": 1}

# 系统语言兼容（issue #428 同类问题）：日文系统 cp932 代码页下中文 print 会崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def default_repo_root():
    """按脚本位置推仓库根。"""
    return Path(__file__).resolve().parent.parent


def load_dumps_map():
    """取地图写盘用的序列化器（CLAUDE.md R22）。

    按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，所以要显式补上；补 sys.path
    是模块级副作用，会被 tests/test_architecture.py 的棘轮拦下，所以和
    tools/validate_maps.py 一样放在函数里。
    """
    root = str(default_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core.json_io import dumps_map

    return dumps_map


def parse_args(argv):
    opts = {
        "write": False,
        "input": None,
        "output": None,
        "mode": None,
        "from": None,
        "to": None,
        "from_map": None,
        "list": False,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--write":
            opts["write"] = True
        elif arg == "--list":
            opts["list"] = True
        elif arg.startswith("--input="):
            opts["input"] = arg.split("=", 1)[1] or None
        elif arg == "--input":
            i += 1
            opts["input"] = (argv[i] if i < len(argv) else "") or None
        elif arg.startswith("--output="):
            opts["output"] = arg.split("=", 1)[1] or None
        elif arg == "--output":
            i += 1
            opts["output"] = (argv[i] if i < len(argv) else "") or None
        elif arg.startswith("--mode="):
            opts["mode"] = arg.split("=", 1)[1] or None
        elif arg == "--mode":
            i += 1
            opts["mode"] = (argv[i] if i < len(argv) else "") or None
        elif arg.startswith("--from="):
            opts["from"] = arg.split("=", 1)[1] or None
        elif arg == "--from":
            i += 1
            opts["from"] = (argv[i] if i < len(argv) else "") or None
        elif arg.startswith("--to="):
            opts["to"] = arg.split("=", 1)[1] or None
        elif arg == "--to":
            i += 1
            opts["to"] = (argv[i] if i < len(argv) else "") or None
        elif arg.startswith("--from-map="):
            opts["from_map"] = arg.split("=", 1)[1] or None
        elif arg == "--from-map":
            i += 1
            opts["from_map"] = (argv[i] if i < len(argv) else "") or None
        else:
            raise SystemExit(f"未知参数：{arg}（用法见文件头）")
        i += 1

    if opts["from"] is not None and opts["from_map"] is not None:
        raise SystemExit("--from 和 --from-map 只能给一个")
    return opts


# ---------------------------------------------------------------------------
# 地图步骤转换（纯逻辑）
# ---------------------------------------------------------------------------


def is_e2_step(entry):
    """是不是要删的那一步：单键、键为 `e`、值为 2（2.0 也算）。"""
    if not isinstance(entry, dict) or len(entry) != 1:
        return False
    key, value = next(iter(entry.items()))
    return key == "e" and value == 2


def is_lv999_e_step(entry):
    """是不是 `lv999_e` 步骤（不管值是多少，统一收掉重插）。"""
    if not isinstance(entry, dict) or len(entry) != 1:
        return False
    return next(iter(entry)) == "lv999_e"


def strip_e2(steps):
    """删除所有 `{"e": 2}`，返回 (保留的步骤, 删除条数)。"""
    kept = [step for step in steps if not is_e2_step(step)]
    return kept, len(steps) - len(kept)


def ensure_lv999_e(steps):
    """保证最前面有且只有一条 `{"lv999_e": 1}`。

    返回 (新步骤列表, 是否有改动)。已有条目在别处 / 值不是 1 时也会被统一，
    所以同一份地图转换两次，第二次返回的列表与输入完全相同。
    """
    body = [step for step in steps if not is_lv999_e_step(step)]
    new_steps = [dict(LV999_E_STEP)] + body
    return new_steps, new_steps != steps


def transform_map(data, mode=MODE_WITH_E):
    """对一份已解析的地图做转换，返回 (新数据, 删除条数, 是否插入/调整了 lv999_e)。

    `with-e` 模式：没有 `{"e": 2}` 的地图完全不碰（不插 lv999_e）。
    `always` 模式：不论有没有 e，都在最前面插 `lv999_e`。
    不修改传入的 `data`；只动 `data["map"]`，`start` 原样保留。
    """
    steps = data["map"]
    stripped, removed = strip_e2(steps)
    new_data = dict(data)
    if mode == MODE_WITH_E and not removed:
        return new_data, 0, False
    new_steps, inserted = ensure_lv999_e(stripped)
    new_data["map"] = new_steps
    return new_data, removed, inserted


# ---------------------------------------------------------------------------
# 文件序号（与 MapInfo.sort_json_files 同一顺序）
# ---------------------------------------------------------------------------


def route_sort_key(name):
    """`map_1-2_10.json` → (0, (1, 2, 10))，与 `MapInfo.sort_json_files` 一致。

    文件名不符合形状时排到最后，按名字排 —— 不让一个怪文件打断整批导出。
    """
    try:
        parts = name.replace("-", "_").replace(".", "_").split("_")[1:-1]
        return (0, tuple(int(part) for part in parts))
    except ValueError:
        return (1, (name,))


def ordered_map_files(input_dir):
    """输入目录下的 JSON，按路线顺序排好（序号就是这个列表的下标 + 1）。"""
    return sorted(Path(input_dir).glob("*.json"), key=lambda p: route_sort_key(p.name))


def count_e2(path):
    """数一张图里有多少条 `{"e": 2}`；读不了返回 None。清单里用来帮助选序号。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("map"), list):
        return None
    return sum(1 for step in data["map"] if is_e2_step(step))


def print_index(files, output_dir):
    """打印编号清单：序号 / 文件名 / e 条数 / 输出目录里的状态。"""
    print(f"{'序号':>4}  {'文件':<24} {'e=2':>4}  输出")
    for index, path in enumerate(files, 1):
        e_count = count_e2(path)
        shown = "?" if e_count is None else str(e_count)
        state = "已存在" if (output_dir / path.name).exists() else "缺失"
        print(f"{index:>4}  {path.name:<24} {shown:>4}  {state}")


# ---------------------------------------------------------------------------
# 目录 / 模式 / 起始序号的选择
# ---------------------------------------------------------------------------


def _resolve_folder(value, root):
    """把用户输入 / 参数解析成绝对路径；相对路径按仓库根解析，不按当前工作目录。"""
    path = Path(value)
    return path if path.is_absolute() else root / path


def _display(path, root):
    """给日志看的路径：在仓库内就显示相对路径，否则原样显示。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _same_folder(a, b):
    """Windows 下路径大小写不敏感，统一 normcase 再比。"""
    return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def _choose_folder(value, ask, label, default, root):
    """参数优先；没给就交互问一次。直接回车 / EOF 都退回默认目录。"""
    if value:
        return _resolve_folder(value, root)
    try:
        answer = ask(f"{label}（回车默认 {_display(default, root)}）：")
    except EOFError:  # 非交互环境（管道 / CI）不该卡住
        answer = ""
    answer = (answer or "").strip()
    return _resolve_folder(answer, root) if answer else default


def _choose_mode(value, ask):
    """参数优先；没给就交互问一次。直接回车 / EOF 默认「有E才加」。"""
    if value:
        if value not in MODE_LABELS:
            raise SystemExit(
                f"未知模式：{value!r}；可选 {MODE_WITH_E}（有E才加）或 "
                f"{MODE_ALWAYS}（无E也加）"
            )
        return value
    try:
        answer = ask("模式：1 有E才加（默认） / 2 无E也加：")
    except EOFError:
        answer = ""
    answer = (answer or "").strip()
    if answer not in MODE_PROMPT:
        raise SystemExit(f"未知模式选项：{answer!r}（1 / 2）")
    return MODE_PROMPT[answer]


def _parse_start(text, total):
    """起始序号：`all` / `全部` 表示 1；非法返回 None。"""
    text = (text or "").strip().lower()
    if text in ("all", "全部"):
        return 1
    try:
        number = int(text)
    except ValueError:
        return None
    return number if 1 <= number <= total else None


def _parse_end(text, total):
    """结束序号：空值 / `all` / `last` / `全部` 表示最后一个；非法返回 None。"""
    text = (text or "").strip().lower()
    if text in ("", "all", "last", "全部", "最后"):
        return total
    try:
        number = int(text)
    except ValueError:
        return None
    return number if 1 <= number <= total else None


def _prompt_number(ask, prompt, total, parser, default):
    """最多问 3 次；空输入返回 default，连续无效返回 None。"""
    for _ in range(3):
        try:
            answer = ask(prompt)
        except EOFError:
            answer = ""
        answer = (answer or "").strip()
        if not answer:
            return default
        number = parser(answer, total)
        if number is not None:
            return number
        print(f"序号无效：{answer!r}，请输入 1–{total}。")
    print("已取消：连续 3 次输入无效。")
    return None


def _choose_range(opts, files, output_dir, ask):
    """决定导出区间 `[start, end]`（1 基、含两端）。返回 None 表示取消。

    输出目录里已经有文件时，起始序号**不提供默认值**：直接回车 = 取消，避免
    误覆盖人工微调过的输出。结束序号默认就是最后一个，省略不影响前面的文件。
    """
    total = len(files)
    prompted_start = False

    if opts["from_map"]:
        names = [path.name for path in files]
        if opts["from_map"] not in names:
            raise SystemExit(f"--from-map 找不到文件：{opts['from_map']}")
        start = names.index(opts["from_map"]) + 1
    elif opts["from"] is not None:
        start = _parse_start(opts["from"], total)
        if start is None:
            raise SystemExit(
                f"--from 的值无效：{opts['from']!r}（应为 1–{total} 或 all）"
            )
    elif not any(output_dir.glob("*.json")):
        start = 1  # 输出目录还是空的，默认从第一个开始
    else:
        print()
        print_index(files, output_dir)
        print()
        print("输出目录里已有文件：只会覆盖你选中的区间，区间外的文件一个字节都不动。")
        start = _prompt_number(
            ask,
            f"从第几个文件开始导出（1–{total}，含该序号；all=全部；回车取消）：",
            total,
            _parse_start,
            default=None,
        )
        if start is None:
            print("已取消：没有指定起始序号，未写盘。")
            return None
        prompted_start = True

    if opts["to"] is not None:
        end = _parse_end(opts["to"], total)
        if end is None:
            raise SystemExit(
                f"--to 的值无效：{opts['to']!r}（应为 1–{total} 或 all）"
            )
    elif prompted_start:
        end = _prompt_number(
            ask,
            f"到第几个结束（1–{total}，含该序号；回车={total}）：",
            total,
            _parse_end,
            default=total,
        )
        if end is None:
            print("已取消：结束序号无效，未写盘。")
            return None
    else:
        end = total

    if start > end:
        raise SystemExit(f"起始序号 {start} 大于结束序号 {end}，区间为空")
    return start, end


def _span(start, end):
    """序号区间的人类可读写法：单个序号不写成 `第 3–3 个`。"""
    return f"第 {start} 个" if start == end else f"第 {start}–{end} 个"


def main(argv, repo_root=None, ask=input):
    opts = parse_args(argv)
    root = Path(repo_root) if repo_root else default_repo_root()

    default_in = root.joinpath(*DEFAULT_INPUT)
    default_out = root.joinpath(*DEFAULT_OUTPUT)

    input_dir = _choose_folder(opts["input"], ask, "输入文件夹", default_in, root)
    output_dir = _choose_folder(opts["output"], ask, "输出文件夹", default_out, root)

    if _same_folder(input_dir, output_dir):
        print("！输入目录和输出目录是同一个 —— 本工具不修改源文件，请换一个输出目录")
        return 2

    files = ordered_map_files(input_dir)
    if not files:
        print(f"！在 {_display(input_dir, root)} 下没有找到 JSON 地图")
        return 0

    if opts["list"]:
        print_index(files, output_dir)
        return 0

    mode = _choose_mode(opts["mode"], ask)
    selection = _choose_range(opts, files, output_dir, ask)
    if selection is None:
        return 2
    start, end = selection

    selected = files[start - 1 : end]
    if (start > 1 or end < len(files)) and not any(output_dir.glob("*.json")):
        print(
            f"！输出目录目前是空的：只导出第 {start}–{end} 个会让目录缺少其余文件，"
            "确认这是你要的"
        )

    dumps_map = load_dumps_map() if opts["write"] else None
    if opts["write"]:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"！创建输出目录失败：{e}")
            return 1

    total_removed = 0
    changed = []
    unchanged_count = 0
    skipped = []

    for path in selected:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            skipped.append(f"{path.name}（读取 / 解析失败：{e}）")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("map"), list):
            skipped.append(f"{path.name}（顶层不是对象，或缺少 map 数组）")
            continue

        new_data, removed, inserted = transform_map(data, mode)

        if opts["write"]:
            try:
                (output_dir / path.name).write_text(
                    dumps_map(new_data), encoding="utf-8"
                )
            except OSError as e:
                skipped.append(f"{path.name}（写入输出目录失败：{e}）")
                continue

        total_removed += removed
        if removed or inserted:
            changed.append((path.name, removed, inserted))
        else:
            unchanged_count += 1

    for note in skipped:
        print(f"！跳过 {note}")

    if start == 1 and end == len(files):
        range_text = f"全部 {len(files)} 个"
        untouched = ""
    else:
        range_text = f"{_span(start, end)}（共 {len(selected)} 个）"
        parts = []
        if start > 1:
            parts.append(_span(1, start - 1))
        if end < len(files):
            parts.append(_span(end + 1, len(files)))
        untouched = "，".join(parts) + " 未触碰"
    head = f"模式：{MODE_LABELS[mode]}；本次导出{range_text}"
    if untouched:
        head += f"，{untouched}"
    print(head)

    if not changed and not unchanged_count:
        print("没有可导出的文件")
        return 1 if skipped else 0

    if changed:
        action = "已写出" if opts["write"] else "需要转换"
        print(f"{action} {len(changed)} 个，共删除 {total_removed} 条 \"e\": 2")
        for name, removed, inserted in changed:
            detail = f"删除 {removed} 条 \"e\": 2"
            if inserted:
                detail += "，插入 lv999_e"
            print(f"  {name}: {detail}")
    if unchanged_count:
        verb = "已原样写出" if opts["write"] else "会原样写出"
        print(f"另有 {unchanged_count} 个文件无需改动，{verb}")

    target = _display(output_dir, root)
    if not opts["write"]:
        print()
        print(f"预览模式：没有写盘。输出目录将是 {target}")
        print("确认后运行：")
        print(
            f"    python tools/convert_huangquan_check_e.py "
            f"--input {_display(input_dir, root)} --output {target} "
            f"--mode {mode} --from {start} --to {end} --write"
        )
        return 0

    print(f"完成：{len(selected) - len(skipped)} 个文件已按 R22 规范写入 {target}")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
