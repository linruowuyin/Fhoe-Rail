"""tools/format_maps.py —— 地图写盘格式的门（只查改动的；CLAUDE.md R22）。

真正要钉住的不是「能不能发现非规范文件」，而是**只拦改动的那些**：全库 633 张里
471 张是上游带来的历史格式，门要是连它们一起拦，等于要求一次性重排全库。
"""

import subprocess

import pytest

import tools.format_maps as format_maps
from utils.core.json_io import dumps_map, is_canonical

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=tester", "-c", "commit.gpgsign=false"]

CANONICAL = dumps_map({"name": "x", "author": "y", "start": [], "map": []})
#: 非规范：2 空格缩进（仓库里 254 张是这样，都来自上游）
NOT_CANONICAL = '{\n  "name": "x",\n  "author": "y",\n  "start": [],\n  "map": []\n}'


def run_git(root, *args):
    subprocess.run([*GIT, *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """一个只有两张地图的临时仓库：一张规范、一张历史格式。"""
    root = tmp_path / "repo"
    (root / "map" / "default").mkdir(parents=True)
    (root / "map" / "default" / "map_1-1_0.json").write_text(CANONICAL, encoding="utf-8")
    (root / "map" / "default" / "map_9-9_0.json").write_text(NOT_CANONICAL, encoding="utf-8")
    run_git(root, "init")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-m", "base")
    return root


class TestIsMapJson:
    @pytest.mark.parametrize("path", ["map/default/map_1-1_0.json", "map/HuangQuan/map_2-2_2.json"])
    def test_accepts_map_files(self, path):
        assert format_maps.is_map_json(path)

    @pytest.mark.parametrize(
        "path",
        ["map/README.json", "map/default/sub/deep.json", "map/default/note.txt", "config.json"],
    )
    def test_rejects_everything_else(self, path):
        assert not format_maps.is_map_json(path)


class TestParseArgs:
    def test_defaults_to_changed_only(self):
        assert format_maps.parse_args([]) == {"all": False, "write": False, "base": None}

    def test_flags(self):
        opts = format_maps.parse_args(["--all", "--write"])
        assert opts["all"] and opts["write"]

    def test_base_accepts_both_forms(self):
        assert format_maps.parse_args(["--base=origin/master"])["base"] == "origin/master"
        assert format_maps.parse_args(["--base", "HEAD~1"])["base"] == "HEAD~1"

    def test_empty_base_falls_back_to_autodetect(self):
        # CI 里 workflow_dispatch 会传成空串
        assert format_maps.parse_args(["--base", ""])["base"] is None

    def test_unknown_argument_is_refused(self):
        with pytest.raises(SystemExit):
            format_maps.parse_args(["--nope"])


class TestChangedOnly:
    """门只拦改动的文件 —— 这条是整个工具能不能接进 CI 的关键。"""

    def test_untouched_non_canonical_file_is_not_reported(self, repo, capsys):
        # 工作区改坏一张（相对 HEAD 未提交），另一张历史格式原样不动
        (repo / "map" / "default" / "map_1-1_0.json").write_text(NOT_CANONICAL, encoding="utf-8")

        code = format_maps.main(["--base", "HEAD"], repo_root=repo)

        out = capsys.readouterr().out
        assert code == 1
        assert "map/default/map_1-1_0.json" in out
        assert "map/default/map_9-9_0.json" not in out, "没动过的历史格式不该被拦"

    def test_all_reports_the_whole_library(self, repo, capsys):
        code = format_maps.main(["--all"], repo_root=repo)
        out = capsys.readouterr().out
        assert code == 1
        assert "全库 2 个地图文件" in out
        assert "map/default/map_9-9_0.json" in out, "没人动过的历史格式文件只有 --all 才查"
        assert "map/default/map_1-1_0.json" not in out, "本来就规范的文件不该被列出来"

    def test_write_rewrites_only_the_changed_one(self, repo):
        (repo / "map" / "default" / "map_1-1_0.json").write_text(NOT_CANONICAL, encoding="utf-8")

        assert format_maps.main(["--base", "HEAD", "--write"], repo_root=repo) == 0

        touched = (repo / "map" / "default" / "map_1-1_0.json").read_text(encoding="utf-8")
        untouched = (repo / "map" / "default" / "map_9-9_0.json").read_text(encoding="utf-8")
        assert is_canonical(touched), "改动的文件应按规范重排"
        assert untouched == NOT_CANONICAL, "没动过的文件一个字节都不该碰"


class TestCleanAndEmptyCases:
    def test_canonical_change_passes(self, repo, capsys):
        # 改了这张图，但写出来就是规范形式 → 放行
        changed = dumps_map({"name": "改过的名字", "author": "y", "start": [], "map": []})
        (repo / "map" / "default" / "map_1-1_0.json").write_text(changed, encoding="utf-8")

        code = format_maps.main(["--base", "HEAD"], repo_root=repo)

        assert code == 0
        assert "1 个文件都是规范形式" in capsys.readouterr().out

    def test_no_base_yet_checks_nothing(self, tmp_path, capsys):
        # 没有提交、也没有 origin/master：拿不到基线，宁可什么都不查
        root = tmp_path / "empty"
        (root / "map").mkdir(parents=True)
        run_git(root, "init")
        assert format_maps.main([], repo_root=root) == 0
        assert "拿不到 git 基线" in capsys.readouterr().out

    def test_broken_json_is_skipped_not_a_format_failure(self, repo, capsys):
        (repo / "map" / "default" / "map_1-1_0.json").write_text("{ nope", encoding="utf-8")
        assert format_maps.main(["--base", "HEAD"], repo_root=repo) == 0
        assert "validate_maps" in capsys.readouterr().out

    def test_new_untracked_map_is_checked(self, repo, capsys):
        # 刚录出来放进 map/ 的新图还没 git add，也要算「改动」
        (repo / "map" / "default" / "map_3-3_0.json").write_text(NOT_CANONICAL, encoding="utf-8")
        assert format_maps.main(["--base", "HEAD"], repo_root=repo) == 1
        assert "map/default/map_3-3_0.json" in capsys.readouterr().out
