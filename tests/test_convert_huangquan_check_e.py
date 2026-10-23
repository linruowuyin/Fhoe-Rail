"""tools/convert_huangquan_check_e.py —— 黄泉地图批量转换工具。

钉住：**e:2 → 0.8 秒同向移动**（同向前缀用双键保疾跑）、**e:1 → lv999_fighting**、
`lv999_e` 永远在最前面且只有一条、**按序号区间导出**、**源目录只读**、
写盘必须走 R22 的规范序列化。
"""

import json

import pytest

import tools.convert_huangquan_check_e as convert
from utils.core.json_io import is_canonical

BASE = [
    "--input",
    "map/HuangQuan",
    "--output",
    "map/SilverWolfLv999",
    "--mode",
    convert.MODE_WITH_E,
]


def write_map(path, steps, start=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": "测试-1",
        "author": "tester",
        "start": [{"map": 1}] if start is None else start,
        "map": steps,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def boom(_prompt):
    raise AssertionError("显式传了 --input/--output/--mode，不该再交互提问")


@pytest.fixture
def repo(tmp_path):
    """临时仓库：只有 map/HuangQuan，输出目录还不存在。"""
    root = tmp_path / "repo"
    (root / "map" / "HuangQuan").mkdir(parents=True)
    return root


def read_map(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestTransformMap:
    def test_e2_at_map_start_gets_w_and_lv999_e(self):
        data, e2, e1, inserted = convert.transform_map({"map": [{"e": 2}]})

        assert data["map"] == [{"lv999_e": 1}, {"w": 0.8}]
        assert (e2, e1) == (1, 0)
        assert inserted

    def test_e2_after_same_direction_uses_double_key(self):
        data, e2, _, _ = convert.transform_map({"map": [{"a": 2}, {"e": 2}]})

        assert data["map"] == [{"lv999_e": 1}, {"a": 2}, {"aa": 0.8}]
        assert e2 == 1

    def test_every_e_in_a_block_is_replaced(self):
        data, e2, _, _ = convert.transform_map(
            {"map": [{"a": 2}, {"e": 2}, {"e": 2}, {"e": 2}]}
        )

        assert data["map"] == [
            {"lv999_e": 1},
            {"a": 2},
            {"aa": 0.8},
            {"aa": 0.8},
            {"aa": 0.8},
        ]
        assert e2 == 3

    def test_await_looks_back_to_the_last_direction_but_uses_single_key(self):
        data, _, _, _ = convert.transform_map(
            {"map": [{"s": 2}, {"await": 1.5}, {"e": 2}]}
        )

        assert data["map"] == [
            {"lv999_e": 1},
            {"s": 2},
            {"await": 1.5},
            {"s": 0.8},
        ]

    def test_e1_becomes_lv999_fighting(self):
        data, e2, e1, _ = convert.transform_map(
            {"map": [{"s": 2}, {"e": 1}]}
        )

        assert data["map"] == [{"lv999_e": 1}, {"s": 2}, {"lv999_fighting": 1}]
        assert (e2, e1) == (0, 1)

    def test_mixed_e2_and_e1(self):
        data, e2, e1, _ = convert.transform_map(
            {"map": [{"s": 2}, {"e": 2}, {"e": 1}]}
        )

        assert data["map"] == [
            {"lv999_e": 1},
            {"s": 2},
            {"ss": 0.8},
            {"lv999_fighting": 1},
        ]
        assert (e2, e1) == (1, 1)

    def test_with_e_leaves_map_without_e_alone(self):
        steps = [{"w": 1}, {"fighting": 2}]
        data, e2, e1, inserted = convert.transform_map({"map": steps})

        assert data["map"] == steps
        assert (e2, e1, inserted) == (0, 0, False)

    def test_always_mode_inserts_lv999_e_even_without_e(self):
        data, _, _, inserted = convert.transform_map(
            {"map": [{"w": 1}]}, convert.MODE_ALWAYS
        )

        assert data["map"] == [{"lv999_e": 1}, {"w": 1}]
        assert inserted

    def test_existing_lv999_e_is_normalized_when_converting(self):
        data, _, _, inserted = convert.transform_map(
            {"map": [{"w": 1}, {"lv999_e": 5}, {"e": 2}]}
        )

        assert data["map"] == [{"lv999_e": 1}, {"w": 1}, {"w": 0.8}]
        assert inserted

    def test_is_idempotent(self):
        once, _, _, _ = convert.transform_map({"map": [{"a": 2}, {"e": 2}]})
        twice, e2, e1, inserted = convert.transform_map(once)

        assert (e2, e1, inserted) == (0, 0, False)
        assert twice == once

    def test_start_is_untouched(self):
        start = [{"map": 1}, {"e": 2}]
        data, _, _, _ = convert.transform_map({"start": start, "map": [{"e": 2}]})
        assert data["start"] == start, "只改 map，start 一个字节都不动"

    def test_does_not_mutate_input(self):
        original = {"map": [{"a": 2}, {"e": 2}]}
        convert.transform_map(original)
        assert original == {"map": [{"a": 2}, {"e": 2}]}


class TestOrdering:
    def test_numeric_parts_not_lexicographic(self):
        names = [
            "map_1-2_10.json",
            "map_1-2_2.json",
            "map_3-10_1.json",
            "map_1-1_0.json",
            "map_2-1_1.json",
        ]
        assert sorted(names, key=convert.route_sort_key) == [
            "map_1-1_0.json",
            "map_1-2_2.json",
            "map_1-2_10.json",
            "map_2-1_1.json",
            "map_3-10_1.json",
        ]

    def test_order_matches_map_info_sort(self):
        from utils.core.map_info import MapInfo

        names = [
            "map_3-10_1.json",
            "map_1-2_10.json",
            "map_1-1_0.json",
            "map_1-2_2.json",
            "map_2-1_1.json",
        ]
        assert sorted(names, key=convert.route_sort_key) == MapInfo.sort_json_files(
            names
        )

    def test_malformed_name_sorts_last(self):
        names = ["map_1-1_0.json", "map_backup.json", "map_1-1_1.json"]
        assert sorted(names, key=convert.route_sort_key)[-1] == "map_backup.json"


class TestParseArgs:
    def test_defaults(self):
        assert convert.parse_args([]) == {
            "write": False,
            "input": None,
            "output": None,
            "mode": None,
            "from": None,
            "to": None,
            "from_map": None,
            "list": False,
        }

    def test_flags(self):
        opts = convert.parse_args(
            [
                "--input",
                "a",
                "--output=b",
                "--mode",
                "always",
                "--from",
                "3",
                "--to",
                "5",
                "--write",
            ]
        )
        assert opts["input"] == "a"
        assert opts["output"] == "b"
        assert opts["mode"] == "always"
        assert opts["from"] == "3"
        assert opts["to"] == "5"
        assert opts["write"] is True

    def test_from_map_flag(self):
        opts = convert.parse_args(["--from-map=map_1-1_0.json"])
        assert opts["from_map"] == "map_1-1_0.json"

    def test_from_and_from_map_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            convert.parse_args(["--from", "1", "--from-map", "map_1-1_0.json"])

    def test_unknown_argument_is_refused(self):
        with pytest.raises(SystemExit):
            convert.parse_args(["--nope"])


class TestDefaultsAndPrompts:
    def test_empty_answers_use_defaults(self, repo, capsys):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])
        prompts = []

        def ask(prompt):
            prompts.append(prompt)
            return ""

        code = convert.main([], repo_root=repo, ask=ask)

        out = capsys.readouterr().out
        assert code == 0
        assert len(prompts) == 3, "输入、输出、模式各问一次"
        assert "map/HuangQuan" in prompts[0]
        assert "map/SilverWolfLv999" in prompts[1]
        assert "模式" in prompts[2]
        assert "输出目录将是 map/SilverWolfLv999" in out
        assert "模式：有E才加" in out

    def test_custom_answers_override_defaults(self, repo, capsys):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])
        answers = iter(["map/HuangQuan", "out_dir", "2"])

        assert convert.main([], repo_root=repo, ask=lambda _p: next(answers)) == 0
        out = capsys.readouterr().out
        assert "输出目录将是 out_dir" in out
        assert "模式：无E也加" in out

    def test_eof_falls_back_to_defaults(self, repo, capsys):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])

        def eof(_prompt):
            raise EOFError

        assert convert.main([], repo_root=repo, ask=eof) == 0
        assert "map/SilverWolfLv999" in capsys.readouterr().out

    def test_explicit_args_do_not_prompt(self, repo):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])
        assert convert.main(BASE, repo_root=repo, ask=boom) == 0


class TestPreview:
    def test_preview_does_not_create_output_or_touch_source(self, repo, capsys):
        source = repo / "map" / "HuangQuan" / "map_1-1_1.json"
        write_map(source, [{"e": 2}, {"w": 1}])
        before = source.read_text(encoding="utf-8")

        code = convert.main(BASE, repo_root=repo, ask=boom)

        out = capsys.readouterr().out
        assert code == 0
        assert "需要转换 1 个" in out
        assert "替换 1 条" in out
        assert "没有写盘" in out
        assert source.read_text(encoding="utf-8") == before
        assert not (repo / "map" / "SilverWolfLv999").exists(), "预览不该建输出目录"

    def test_preview_suggests_the_write_command(self, repo, capsys):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])

        convert.main(BASE, repo_root=repo, ask=boom)

        out = capsys.readouterr().out
        assert "--write" in out
        assert "--mode with-e" in out
        assert "--from 1" in out
        assert "--to 1" in out


class TestWrite:
    def test_writes_to_output_and_leaves_source_untouched(self, repo):
        source = repo / "map" / "HuangQuan" / "map_1-1_1.json"
        write_map(source, [{"e": 2}, {"w": 1}, {"e": 1}])
        before = source.read_text(encoding="utf-8")

        code = convert.main(BASE + ["--write"], repo_root=repo, ask=boom)

        assert code == 0
        assert source.read_text(encoding="utf-8") == before, "源文件一个字节都不该动"

        output = repo / "map" / "SilverWolfLv999" / "map_1-1_1.json"
        data = read_map(output)
        assert data["map"] == [
            {"lv999_e": 1},
            {"w": 0.8},
            {"w": 1},
            {"lv999_fighting": 1},
        ]
        assert is_canonical(output.read_text(encoding="utf-8")), (
            "写盘必须走 utils/core/json_io.py（CLAUDE.md R22）"
        )

    def test_lv999_e_is_written_like_a_normal_step(self, repo):
        """lv999_e 必须和既有步骤同一个写法：多行对象 + `": "` + 4 空格缩进。"""
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"w": 1}, {"e": 2}])

        convert.main(BASE + ["--write"], repo_root=repo, ask=boom)

        text = (repo / "map" / "SilverWolfLv999" / "map_1-1_1.json").read_text(
            encoding="utf-8"
        )
        assert (
            '    "map": [\n'
            "        {\n"
            '            "lv999_e": 1\n'
            "        },\n"
            "        {\n"
            '            "w": 1\n'
            "        }"
        ) in text
        assert '"lv999_e":1' not in text, "冒号后要有空格，与其它键一致"
        assert '{"lv999_e": 1}' not in text, "对象不能内联成一行"

    def test_map_without_e_is_copied_without_lv999_e(self, repo):
        write_map(
            repo / "map" / "HuangQuan" / "map_no_e.json",
            [{"w": 1}, {"fighting": 2}],
        )

        convert.main(BASE + ["--write"], repo_root=repo, ask=boom)

        output = repo / "map" / "SilverWolfLv999" / "map_no_e.json"
        assert read_map(output)["map"] == [{"w": 1}, {"fighting": 2}]

    def test_always_mode_adds_lv999_e_to_every_file(self, repo):
        write_map(repo / "map" / "HuangQuan" / "map_1-1_0.json", [{"w": 1}])
        write_map(repo / "map" / "HuangQuan" / "map_1-1_1.json", [{"e": 2}])

        args = BASE[:]
        args[args.index("--mode") + 1] = convert.MODE_ALWAYS
        convert.main(args + ["--write"], repo_root=repo, ask=boom)

        output = repo / "map" / "SilverWolfLv999"
        assert read_map(output / "map_1-1_0.json")["map"] == [
            {"lv999_e": 1},
            {"w": 1},
        ]
        assert read_map(output / "map_1-1_1.json")["map"] == [
            {"lv999_e": 1},
            {"w": 0.8},
        ]

    def test_unchanged_maps_are_copied_too(self, repo):
        write_map(
            repo / "map" / "HuangQuan" / "map_done.json",
            [{"lv999_e": 1}, {"w": 1}],
        )
        write_map(repo / "map" / "HuangQuan" / "map_todo.json", [{"e": 2}])

        convert.main(BASE + ["--write"], repo_root=repo, ask=boom)

        output = repo / "map" / "SilverWolfLv999"
        assert (output / "map_done.json").exists()
        assert (output / "map_todo.json").exists()

    def test_input_equal_to_output_is_refused(self, repo, capsys):
        source = repo / "map" / "HuangQuan" / "map_1-1_1.json"
        write_map(source, [{"e": 2}])
        before = source.read_text(encoding="utf-8")

        code = convert.main(
            ["--input", "map/HuangQuan", "--output", "./map/HuangQuan", "--write"],
            repo_root=repo,
            ask=boom,
        )

        assert code == 2
        assert "同一个" in capsys.readouterr().out
        assert source.read_text(encoding="utf-8") == before

    def test_broken_json_is_skipped_and_reported(self, repo, capsys):
        (repo / "map" / "HuangQuan" / "map_bad.json").write_text(
            "{ nope", encoding="utf-8"
        )
        good = repo / "map" / "HuangQuan" / "map_good.json"
        write_map(good, [{"e": 2}])

        code = convert.main(BASE + ["--write"], repo_root=repo, ask=boom)

        out = capsys.readouterr().out
        assert code == 1
        assert "跳过 map_bad.json" in out
        output = repo / "map" / "SilverWolfLv999" / "map_good.json"
        assert read_map(output)["map"][0] == {"lv999_e": 1}
        assert not (repo / "map" / "SilverWolfLv999" / "map_bad.json").exists()

    def test_missing_map_array_is_skipped(self, repo, capsys):
        (repo / "map" / "HuangQuan" / "map_wrong.json").write_text(
            '{"name": "x"}', encoding="utf-8"
        )

        code = convert.main(BASE, repo_root=repo, ask=boom)
        assert code == 1
        assert "缺少 map 数组" in capsys.readouterr().out

    def test_ignores_non_json_files(self, repo, capsys):
        (repo / "map" / "HuangQuan" / "note.txt").write_text(
            '{"map": [{"e": 2}]}', encoding="utf-8"
        )

        code = convert.main(BASE, repo_root=repo, ask=boom)
        assert code == 0
        assert "没有找到 JSON 地图" in capsys.readouterr().out


class TestRangeExport:
    """核心：只导出第 N 个及之后；前面的文件（包括被删掉的）一个字节都不碰。"""

    def _three_maps(self, repo):
        base = repo / "map" / "HuangQuan"
        write_map(base / "map_1-1_0.json", [{"e": 2}, {"w": 1}])
        write_map(base / "map_1-1_1.json", [{"e": 2}, {"w": 2}])
        write_map(base / "map_1-2_1.json", [{"e": 2}, {"w": 3}])

    def test_from_only_writes_selected_tail(self, repo):
        self._three_maps(repo)

        assert (
            convert.main(BASE + ["--from", "2", "--write"], repo_root=repo, ask=boom)
            == 0
        )

        output = repo / "map" / "SilverWolfLv999"
        assert not (output / "map_1-1_0.json").exists(), "区间之前的文件不该被创建"
        assert (output / "map_1-1_1.json").exists()
        assert (output / "map_1-2_1.json").exists()

    def test_from_2_does_not_touch_tuned_or_deleted_earlier_files(self, repo):
        self._three_maps(repo)
        output = repo / "map" / "SilverWolfLv999"
        output.mkdir(parents=True)
        tuned = output / "map_1-1_0.json"
        tuned.write_text('{"name": "我手动调过的"}', encoding="utf-8")
        before = tuned.read_text(encoding="utf-8")

        convert.main(BASE + ["--from", "2", "--write"], repo_root=repo, ask=boom)

        assert tuned.read_text(encoding="utf-8") == before

    def test_deleted_earlier_file_is_not_recreated(self, repo):
        self._three_maps(repo)
        convert.main(BASE + ["--from", "1", "--write"], repo_root=repo, ask=boom)
        output = repo / "map" / "SilverWolfLv999"
        (output / "map_1-1_0.json").unlink()

        convert.main(BASE + ["--from", "2", "--write"], repo_root=repo, ask=boom)

        assert not (output / "map_1-1_0.json").exists(), (
            "用户刻意删掉的图不能在下次区间导出时被加回来"
        )

    def test_to_limits_the_range(self, repo):
        self._three_maps(repo)

        convert.main(BASE + ["--from", "1", "--to", "2", "--write"],
                     repo_root=repo, ask=boom)

        output = repo / "map" / "SilverWolfLv999"
        assert (output / "map_1-1_0.json").exists()
        assert (output / "map_1-1_1.json").exists()
        assert not (output / "map_1-2_1.json").exists(), "结束序号之后的文件不该写"

    def test_from_and_to_are_both_inclusive(self, repo):
        self._three_maps(repo)

        convert.main(BASE + ["--from", "2", "--to", "3", "--write"],
                     repo_root=repo, ask=boom)

        output = repo / "map" / "SilverWolfLv999"
        assert not (output / "map_1-1_0.json").exists()
        assert (output / "map_1-1_1.json").exists()
        assert (output / "map_1-2_1.json").exists()

    def test_invalid_to_is_refused(self, repo):
        self._three_maps(repo)
        for value in ("0", "4", "abc"):
            with pytest.raises(SystemExit):
                convert.main(
                    BASE + ["--from", "1", "--to", value, "--write"],
                    repo_root=repo,
                    ask=boom,
                )

    def test_from_greater_than_to_is_refused(self, repo):
        self._three_maps(repo)
        with pytest.raises(SystemExit):
            convert.main(
                BASE + ["--from", "3", "--to", "1", "--write"],
                repo_root=repo,
                ask=boom,
            )

    def test_from_map_selects_by_filename(self, repo):
        self._three_maps(repo)

        convert.main(
            BASE + ["--from-map", "map_1-1_1.json", "--write"],
            repo_root=repo,
            ask=boom,
        )

        output = repo / "map" / "SilverWolfLv999"
        assert not (output / "map_1-1_0.json").exists()
        assert (output / "map_1-1_1.json").exists()

    def test_from_map_unknown_file_is_refused(self, repo):
        self._three_maps(repo)
        with pytest.raises(SystemExit):
            convert.main(
                BASE + ["--from-map", "nope.json", "--write"],
                repo_root=repo,
                ask=boom,
            )

    def test_invalid_from_is_refused(self, repo):
        self._three_maps(repo)
        for value in ("0", "4", "abc"):
            with pytest.raises(SystemExit):
                convert.main(
                    BASE + ["--from", value, "--write"], repo_root=repo, ask=boom
                )

    def test_all_value_means_everything(self, repo):
        self._three_maps(repo)
        convert.main(BASE + ["--from", "all", "--write"], repo_root=repo, ask=boom)
        assert len(list((repo / "map" / "SilverWolfLv999").glob("*.json"))) == 3

    def test_existing_output_requires_explicit_start(self, repo, capsys):
        self._three_maps(repo)
        output = repo / "map" / "SilverWolfLv999"
        output.mkdir(parents=True)
        existing = output / "map_1-1_0.json"
        existing.write_text('{"tuned": true}', encoding="utf-8")

        code = convert.main(BASE, repo_root=repo, ask=lambda _p: "")

        out = capsys.readouterr().out
        assert code == 2
        assert "已取消" in out
        assert existing.read_text(encoding="utf-8") == '{"tuned": true}'

    def test_interactive_start_and_end_are_honored(self, repo):
        self._three_maps(repo)
        output = repo / "map" / "SilverWolfLv999"
        output.mkdir(parents=True)
        (output / "map_1-1_0.json").write_text("{}", encoding="utf-8")

        answers = iter(["2", "2"])  # 从第 2 个到第 2 个
        convert.main(BASE + ["--write"], repo_root=repo, ask=lambda _p: next(answers))

        assert (output / "map_1-1_1.json").exists()
        assert not (output / "map_1-2_1.json").exists(), "结束序号之后的文件不该写"
        assert (output / "map_1-1_0.json").read_text(encoding="utf-8") == "{}"

    def test_interactive_end_defaults_to_last(self, repo):
        self._three_maps(repo)
        output = repo / "map" / "SilverWolfLv999"
        output.mkdir(parents=True)
        (output / "map_1-1_0.json").write_text("{}", encoding="utf-8")

        answers = iter(["2", ""])  # 结束序号回车 = 最后一个
        convert.main(BASE + ["--write"], repo_root=repo, ask=lambda _p: next(answers))

        assert (output / "map_1-1_1.json").exists()
        assert (output / "map_1-2_1.json").exists()

    def test_list_prints_numbered_files_without_writing(self, repo, capsys):
        self._three_maps(repo)

        code = convert.main(
            ["--list", "--input", "map/HuangQuan", "--output", "map/SilverWolfLv999"],
            repo_root=repo,
            ask=boom,
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "map_1-1_0.json" in out
        assert "map_1-1_1.json" in out
        assert "map_1-2_1.json" in out
        assert not (repo / "map" / "SilverWolfLv999").exists()

    def test_list_uses_route_order(self, repo, capsys):
        base = repo / "map" / "HuangQuan"
        write_map(base / "map_1-2_10.json", [{"e": 2}])
        write_map(base / "map_1-2_2.json", [{"e": 2}])

        convert.main(
            ["--list", "--input", "map/HuangQuan", "--output", "map/SilverWolfLv999"],
            repo_root=repo,
            ask=boom,
        )

        out = capsys.readouterr().out
        assert out.index("map_1-2_2.json") < out.index("map_1-2_10.json")
