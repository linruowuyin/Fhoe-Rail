"""tools/convert.py —— 地图 JSON 批量查找与字段替换工具。"""

import json

import pytest

from tools.convert import find_json_files_with_character, replace_word_in_json_files
from utils.core.json_io import is_canonical


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestFindJsonFilesWithCharacter:
    def test_finds_files_containing_word(self, tmp_path):
        write_json(tmp_path / "hit.json", {"key": "picture\\map_1-1_point_1.png"})
        write_json(tmp_path / "miss.json", {"key": "other"})
        found = find_json_files_with_character(tmp_path, "map_1-1")
        assert [f.split("\\")[-1].split("/")[-1] for f in found] == ["hit.json"]

    def test_searches_recursively(self, tmp_path):
        nested = tmp_path / "map" / "default"
        nested.mkdir(parents=True)
        write_json(nested / "deep.json", {"key": "needle"})
        found = find_json_files_with_character(tmp_path, "needle")
        assert len(found) == 1

    def test_ignores_non_json_files(self, tmp_path):
        (tmp_path / "note.txt").write_text("needle", encoding="utf-8")
        assert find_json_files_with_character(tmp_path, "needle") == []

    def test_returns_empty_for_missing_directory(self, tmp_path):
        assert find_json_files_with_character(tmp_path / "nope", "x") == []

    def test_matches_inside_values_not_only_keys(self, tmp_path):
        write_json(tmp_path / "v.json", {"k": "a needle here"})
        assert len(find_json_files_with_character(tmp_path, "needle")) == 1


class TestReplaceWordInJsonFiles:
    def test_replaces_value_text(self, tmp_path):
        target = tmp_path / "m.json"
        write_json(target, {"key": "picture\\old_name.png"})
        replace_word_in_json_files([str(target)], "old_name", "new_name")
        assert json.loads(target.read_text(encoding="utf-8"))["key"] == (
            "picture\\new_name.png"
        )

    def test_rewrites_in_the_canonical_format(self, tmp_path):
        target = tmp_path / "m.json"
        write_json(target, {"name": "x", "start": [{"click_offset": [60, 0]}], "map": []})
        replace_word_in_json_files([str(target)], "unused", "unused")

        text = target.read_text(encoding="utf-8")
        assert is_canonical(text), "重写必须走 utils/core/json_io.py（CLAUDE.md R22）"
        assert '"click_offset": [60,0]' in text, "短数组不能拆行"

    def test_handles_empty_file_list(self):
        replace_word_in_json_files([], "a", "b")  # 不应抛出

    @pytest.mark.xfail(
        strict=True,
        reason="替换发生在 json.dumps 之后的整段文本上，会误伤键名和其它值的子串",
    )
    def test_does_not_touch_keys(self, tmp_path):
        target = tmp_path / "m.json"
        write_json(target, {"name": "cat"})
        replace_word_in_json_files([str(target)], "a", "X")
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"name": "cXt"}
