"""地图 JSON 的写盘格式 —— CLAUDE.md R22。

地图 JSON 的格式在仓库里是混的（实测 633 个文件：4 / 2 / 顶格 / 7 空格四种缩进，
221 个还混着 Tab），所以写盘不做「保留原格式」，一律重排成规范形式：
4 空格缩进 + 短数组内联 + 末尾不加换行。

三个写入方（webui 保存 / 录制 / 批量字段替换）必须共用 `utils/core/json_io.py`
这一个序列化器 —— 各写一套的话格式会再次分叉。
"""

import json
from pathlib import Path

from utils.core.json_io import INLINE_MAX, dumps_map, is_canonical

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = REPO_ROOT / "map"

#: 会把地图 JSON 写到盘上的地方
WRITER_FILES = (
    "webui/server.py",  # webui 保存地图
    "utils/ui/record.py",  # --record 录制
    "tools/convert.py",  # 批量字段替换
)

#: 这三个表达式是分叉的根源：各自序列化、各自定缩进
RETIRED_SERIALIZERS = (
    "OPT_INDENT_2",  # record.py 原来用 orjson 写 2 空格
    "json.dumps(data, ensure_ascii=False, indent=4)",  # convert.py 原来写 4 空格但展开数组
    "json.dump(data, f, ensure_ascii=False, indent=4)",  # webui 原来写 4 空格但展开数组
)


class TestInlineRule:
    """短数组内联 —— 633 个地图文件里唯一没有例外的写法。"""

    def test_short_leaf_array_is_inline(self):
        out = dumps_map({"start": [{"picture.png": 1.5, "click_offset": [60, 0]}]})
        assert '"click_offset": [60,0]' in out
        assert "60,\n" not in out

    def test_nested_short_array_is_inline(self):
        # "floor": [[1,2,3],1] 是真实地图里的形状，也不能拆行
        out = dumps_map({"map": [{"floor": [[1, 2, 3], 1]}]})
        assert '"floor": [[1,2,3],1]' in out

    def test_string_array_is_inline(self):
        out = dumps_map({"start": [{"check": ["周一", "周三"]}]})
        assert '"check": ["周一","周三"]' in out

    def test_empty_containers_stay_compact(self):
        out = dumps_map({"start": [{"clicks": [], "x": {}}]})
        assert '"clicks": []' in out
        assert '"x": {}' in out

    def test_array_of_objects_is_expanded(self):
        # 数组里装着对象就不内联 —— 内联了没法读
        out = dumps_map({"start": [{"a": [{"x": 1}, {"y": 2}]}]})
        assert '"a": [\n' in out

    def test_long_array_is_expanded(self):
        out = dumps_map({"start": [{"a": list(range(200))}]})
        assert '"a": [\n' in out

    def test_inline_limit_boundary(self):
        # 上限之内内联、超一点就拆行
        just_fits = ["x" * 20] * 4
        too_long = ["x" * 20] * 5
        flat_ok = json.dumps(just_fits, separators=(",", ":"))
        flat_big = json.dumps(too_long, separators=(",", ":"))
        assert len(flat_ok) <= INLINE_MAX < len(flat_big)
        assert flat_ok in dumps_map({"a": just_fits})
        assert flat_big not in dumps_map({"a": too_long})


class TestCanonicalForm:
    def test_indent_is_four_spaces(self):
        out = dumps_map({"start": [{"map": 1}]})
        assert out == '{\n    "start": [\n        {\n            "map": 1\n        }\n    ]\n}'

    def test_no_trailing_newline(self):
        # 仓库 633 个文件里 621 个末尾没有换行，跟现状保持一致
        assert not dumps_map({"start": [], "map": []}).endswith("\n")

    def test_non_ascii_is_not_escaped(self):
        out = dumps_map({"name": "鸽川区-1"})
        assert "鸽川区-1" in out
        assert "u9e3f" not in out

    def test_key_order_is_preserved(self):
        # 步骤键必须排在修饰键前面（map_operations 依赖 keys[0]）
        out = dumps_map({"start": [{"map": 1, "click_offset": [60, 0]}]})
        assert out.index('"map"') < out.index('"click_offset"')


class TestIsCanonical:
    def test_accepts_canonical_text(self):
        assert is_canonical(dumps_map({"start": [{"click_offset": [60, 0]}]}))

    def test_rejects_two_space_text(self):
        assert not is_canonical('{\n  "start": []\n}')

    def test_rejects_expanded_array(self):
        assert not is_canonical('{\n    "a": [\n        1,\n        2\n    ]\n}')

    def test_broken_json_is_not_canonical(self):
        assert not is_canonical("{ nope")


class TestWritersShareOneSerializer:
    """三个写入方都走同一个序列化器，且没留下各写一套的旧代码。"""

    def test_all_writers_reference_the_shared_serializer(self):
        missing = [
            name
            for name in WRITER_FILES
            if "dumps_map" not in (REPO_ROOT / name).read_text(encoding="utf-8")
        ]
        assert missing == [], f"这些写入方没走 utils/core/json_io.py：{missing}"

    def test_no_retired_serializer_is_left(self):
        found = [
            (name, snippet)
            for name in WRITER_FILES
            for snippet in RETIRED_SERIALIZERS
            if snippet in (REPO_ROOT / name).read_text(encoding="utf-8")
        ]
        assert found == [], f"还留着各写一套的旧序列化：{found}"


class TestRoundTrip:
    def test_idempotent(self):
        data = {"start": [{"picture.png": 1.5, "click_offset": [60, 0]}], "map": [{"w": 2.5}]}
        once = dumps_map(data)
        assert dumps_map(json.loads(once)) == once

    def test_values_survive(self):
        data = {"name": "x", "author": "y", "start": [{"floor": [[1, 2, 3], 1]}], "map": [{"await": 1.5}]}
        assert json.loads(dumps_map(data)) == data


class TestShippedMapLibrary:
    """整库回归：重排绝不能改语义，且必须收敛（再排一次不再变）。"""

    @staticmethod
    def _maps():
        return sorted(MAP_DIR.glob("*/*.json"))

    def test_library_is_not_empty(self):
        assert len(self._maps()) > 600

    def test_reserialization_preserves_semantics_and_converges(self):
        bad = []
        for path in self._maps():
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            once = dumps_map(data)
            if json.loads(once) != data:
                bad.append(f"{path.name}: 内容变了")
            elif dumps_map(json.loads(once)) != once:
                bad.append(f"{path.name}: 不收敛（再排一次又变）")
        assert bad == [], "\n".join(bad[:10])
