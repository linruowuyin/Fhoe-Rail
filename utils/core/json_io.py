"""地图 JSON 的写盘格式 —— 纯逻辑，不碰文件系统（CLAUDE.md R22）。

仓库里的地图文件格式是混的：实测 633 个文件里，用 `json.dump(indent=4)` 原样重写
只有 165 个（按行内容算）不变 —— 缩进有 4 / 2 / 顶格 / 7 空格四种，221 个文件里还
混着 Tab（手改留下的 `\\t\\t},`）。混排到这种程度，「保存时保留原格式」根本做不到：
没有任何一个缩进设置能还原「一半空格一半 Tab」。

所以写盘一律重排成下面这份规范，代价是某个文件**第一次**保存会重排整份，
收益是之后同一文件再改就只剩真正改动的那几行（实测：连存三次，后两次零 diff）。

规范形式：
    * 4 空格缩进
    * **短数组内联** —— 这是 633 个文件里唯一没有例外的写法（113 处）
    * 末尾不加换行（633 个里 621 个如此）

数组内联不是排版洁癖：`json.dump` 会把每个数组拆成一行一个元素，
`"click_offset": [60,0]` 变 5 行、`"floor": [[1,2,3],1]` 变 9 行，保存一次就
把没碰过的步骤也搅进 diff。内联后一个步骤始终是 1~2 行，编辑器里也看得清。
"""

import json

#: 缩进宽度
INDENT = 4
#: 内联数组的长度上限。仓库现有的内联数组最长 15 字符（`[0,1,2,3,4,5,6]`），
#: 留足余量；超过就还是拆行，免得将来某个长数组糊成一行没法读。
INLINE_MAX = 100


def _contains_dict(obj):
    if isinstance(obj, dict):
        return True
    if isinstance(obj, list):
        return any(_contains_dict(item) for item in obj)
    return False


def dumps_map(obj, level=0):
    """按上面的规范把地图数据序列化成字符串。

    `level` 只用于递归时算缩进，外部调用不用传。
    """
    pad = " " * (INDENT * level)
    inner = " " * (INDENT * (level + 1))
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [
            f"{inner}{json.dumps(k, ensure_ascii=False)}: {dumps_map(v, level + 1)}"
            for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list):
        # 内联候选：整段压成一行，且里面不能有对象（对象内联就没法读了）
        flat = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if len(flat) <= INLINE_MAX and not _contains_dict(obj):
            return flat
        items = [inner + dumps_map(v, level + 1) for v in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False)


def is_canonical(text):
    """判断一段文本是否已经是规范形式（给 `--check` 用，不抛异常）。"""
    try:
        return dumps_map(json.loads(text)) == text
    except (ValueError, TypeError):
        return False
