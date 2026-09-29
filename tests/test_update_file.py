"""tools/update_file.py —— 资源文件校验、解压与更新流程。"""

import asyncio
import hashlib
import zipfile

import pytest

import tools.update_file as update_file_module
from tools.update_file import (
    move_file,
    remove_file,
    unzip,
    update_file,
    verify_file_hash,
)


def run(coro):
    return asyncio.run(coro)


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


class TestVerifyFileHash:
    def test_all_hashes_match(self, tmp_path):
        target = tmp_path / "a.bin"
        target.write_bytes(b"payload")
        entries = [{"path": str(target), "hash": md5(b"payload")}]

        ok, bad = run(verify_file_hash(entries))

        assert ok is True
        assert bad is None

    def test_missing_file_reports_the_path(self, tmp_path):
        missing = tmp_path / "gone.bin"
        entries = [{"path": str(missing), "hash": "irrelevant"}]

        ok, bad = run(verify_file_hash(entries))

        assert ok is False
        assert bad == missing

    def test_hash_mismatch_reports_the_path(self, tmp_path):
        target = tmp_path / "a.bin"
        target.write_bytes(b"tampered")
        entries = [{"path": str(target), "hash": md5(b"expected")}]

        ok, bad = run(verify_file_hash(entries))

        assert ok is False
        assert bad == target

    def test_keep_file_skips_verification(self, tmp_path):
        target = tmp_path / "a.bin"
        target.write_bytes(b"tampered")
        entries = [{"path": str(target), "hash": md5(b"expected")}]

        ok, bad = run(verify_file_hash(entries, keep_file=[str(target)]))

        assert ok is True, "用户保留的文件不应参与校验"

    def test_empty_manifest_passes(self):
        assert run(verify_file_hash([])) == (True, None)

    def test_non_mapping_entry_raises(self):
        """远程清单结构不对时没有防御，直接抛 TypeError。"""
        with pytest.raises(TypeError):
            run(verify_file_hash(["not-a-dict"]))


class TestUnzip:
    def make_zip(self, path, members):
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return path

    def test_extracts_only_matching_prefix(self, isolated_cwd, monkeypatch):
        monkeypatch.setattr(update_file_module, "tmp_dir", "tmp")
        archive = self.make_zip(
            isolated_cwd / "pack.zip",
            {"map/a.txt": "A", "other/b.txt": "B"},
        )

        run(unzip(archive, "map"))

        assert (isolated_cwd / "tmp" / "map" / "a.txt").read_text() == "A"
        assert not (isolated_cwd / "tmp" / "other" / "b.txt").exists()

    def test_empty_prefix_extracts_everything(self, isolated_cwd, monkeypatch):
        monkeypatch.setattr(update_file_module, "tmp_dir", "tmp")
        archive = self.make_zip(
            isolated_cwd / "pack.zip", {"a.txt": "A", "b/c.txt": "C"}
        )

        run(unzip(archive, ""))

        assert (isolated_cwd / "tmp" / "a.txt").exists()
        assert (isolated_cwd / "tmp" / "b" / "c.txt").exists()

    def test_prefix_match_is_not_directory_aware(self, isolated_cwd, monkeypatch):
        """前缀是纯字符串比较，'map' 也会命中 'map_evil/...'。"""
        monkeypatch.setattr(update_file_module, "tmp_dir", "tmp")
        archive = self.make_zip(
            isolated_cwd / "pack.zip", {"map_evil/x.txt": "X"}
        )

        run(unzip(archive, "map"))

        assert (isolated_cwd / "tmp" / "map_evil" / "x.txt").exists()


class TestRemoveFile:
    def test_removes_files_and_folders(self, isolated_cwd):
        (isolated_cwd / "work").mkdir()
        (isolated_cwd / "work" / "f.txt").write_text("x")
        (isolated_cwd / "work" / "sub").mkdir()

        run(remove_file(isolated_cwd / "work"))

        assert list((isolated_cwd / "work").iterdir()) == []

    def test_keep_folder_and_file_are_preserved(self, isolated_cwd):
        (isolated_cwd / "work").mkdir()
        (isolated_cwd / "work" / "keep.txt").write_text("x")
        (isolated_cwd / "work" / "drop.txt").write_text("y")
        (isolated_cwd / "work" / "keepdir").mkdir()

        run(remove_file(isolated_cwd / "work", keep_folder=["keepdir"], keep_file=["keep.txt"]))

        assert sorted(p.name for p in (isolated_cwd / "work").iterdir()) == [
            "keep.txt",
            "keepdir",
        ]

    def test_missing_folder_is_a_noop(self, isolated_cwd):
        run(remove_file(isolated_cwd / "nope"))


class TestMoveFile:
    @pytest.mark.xfail(
        strict=True,
        reason="get_file 产出的路径用反斜杠，而 move_file 用 rsplit('/') 拆目录，"
        "拆不开时不会创建目标目录，shutil.copy 直接抛 FileNotFoundError",
    )
    def test_preserves_relative_structure(self, isolated_cwd):
        (isolated_cwd / "src" / "sub").mkdir(parents=True)
        (isolated_cwd / "src" / "sub" / "a.txt").write_text("payload")

        run(move_file("src", "src"))

        assert (isolated_cwd / "sub" / "a.txt").read_text() == "payload"


class TestUpdateFile:
    @pytest.fixture
    def no_sleep(self, monkeypatch):
        async def fake_sleep(seconds):
            return None

        monkeypatch.setattr(update_file_module.asyncio, "sleep", fake_sleep)

    def make_response(self, payload):
        return type("Response", (), {"json": staticmethod(lambda: payload)})()

    def test_skips_download_when_version_matches(self, isolated_cwd, monkeypatch, no_sleep):
        downloaded = []

        async def fake_get(url, **kwargs):
            return self.make_response({"version": "0"})

        async def fake_download(url, path):
            downloaded.append(url)

        monkeypatch.setattr(update_file_module, "get", fake_get)
        monkeypatch.setattr(update_file_module, "download", fake_download)

        result = run(
            update_file(
                type="picture", version="v1", url_zip="https://example.invalid/a.zip",
                unzip_path="picture",
            )
        )

        assert result is True
        assert downloaded == [], "版本已是最新时不应下载"

    @pytest.mark.xfail(
        strict=True,
        reason="重试循环用 except BaseException 捕获，KeyboardInterrupt 会被当成网络失败重试，"
        "长时间下载无法用 Ctrl-C 中断",
    )
    def test_keyboard_interrupt_is_not_swallowed(self, isolated_cwd, monkeypatch, no_sleep):
        async def fake_get(url, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(update_file_module, "get", fake_get)

        with pytest.raises(KeyboardInterrupt):
            run(
                update_file(
                    type="picture", version="v1",
                    url_zip="https://example.invalid/a.zip", unzip_path="picture",
                )
            )

    def test_network_failure_exhausts_retries(self, isolated_cwd, monkeypatch, no_sleep):
        async def fake_get(url, **kwargs):
            raise OSError("网络不可达")

        monkeypatch.setattr(update_file_module, "get", fake_get)

        with pytest.raises(Exception, match="重试次数已达上限"):
            run(
                update_file(
                    type="picture", version="v1",
                    url_zip="https://example.invalid/a.zip", unzip_path="picture",
                )
            )


class TestModuleDefaults:
    def test_default_parameters_are_not_shared_mutable_state(self):
        """可选列表参数默认值是 []，当前实现没有原地修改，属于随时会踩的坑。"""
        import inspect

        for func in (verify_file_hash, remove_file, move_file, update_file):
            signature = inspect.signature(func)
            for name, parameter in signature.parameters.items():
                if parameter.default is inspect.Parameter.empty:
                    continue
                if isinstance(parameter.default, list):
                    assert parameter.default == [], name
