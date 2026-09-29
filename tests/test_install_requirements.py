"""tools/install_requirements.py —— 依赖检测与 pip 源切换。"""

import subprocess
from pathlib import Path

import pytest

import tools.install_requirements as install_module
from tools.install_requirements import (
    check_and_install_dependencies,
    find_requirements_file,
    set_fastest_proxy,
)

# 注意：不要 `from tools.install_requirements import test_speed`，
# 名字以 test_ 开头的函数会被 pytest 当成测试用例收集并执行真实 ping。

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestFindRequirementsFile:
    def test_finds_repository_requirements(self):
        """脚本从 utils/ 挪到了 tools/，两边都在仓库根下一级，推导结果不变。"""
        found = find_requirements_file()
        assert found is not None
        assert Path(found).resolve() == REPO_ROOT / "requirements.txt"

    def test_returns_none_when_absent(self, monkeypatch):
        monkeypatch.setattr(install_module.os.path, "exists", lambda path: False)
        assert find_requirements_file() is None


class TestTestSpeed:
    """tools.install_requirements.test_speed —— 用 ping 测速。"""

    def test_measures_elapsed_time(self, monkeypatch):
        times = iter([0.0, 1.5])
        monkeypatch.setattr(install_module.time, "time", lambda: next(times))
        monkeypatch.setattr(install_module.subprocess, "check_call", lambda args: 0)

        assert install_module.test_speed("mirrors.aliyun.com") == pytest.approx(1.5)

    def test_returns_infinity_on_failure(self, monkeypatch):
        def boom(args):
            raise subprocess.CalledProcessError(1, args)

        monkeypatch.setattr(install_module.subprocess, "check_call", boom)

        assert install_module.test_speed("unreachable.invalid") == float("inf")

    def test_pings_the_given_host(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            install_module.subprocess, "check_call", lambda args: called.append(args)
        )
        install_module.test_speed("example.invalid")
        assert called == [["ping", "-n", "5", "example.invalid"]]


class TestSetFastestProxy:
    def test_picks_aliyun_when_faster(self, monkeypatch, capsys):
        monkeypatch.setattr(
            install_module,
            "test_speed",
            lambda source: 0.1 if "aliyun" in source else 0.9,
        )
        commands = []
        monkeypatch.setattr(
            install_module.subprocess, "check_call", lambda args: commands.append(args)
        )

        set_fastest_proxy()

        assert "mirrors.aliyun.com" in commands[0][-1]
        assert "阿里云" in capsys.readouterr().out

    def test_picks_tuna_when_faster(self, monkeypatch, capsys):
        monkeypatch.setattr(
            install_module,
            "test_speed",
            lambda source: 0.9 if "aliyun" in source else 0.1,
        )
        commands = []
        monkeypatch.setattr(
            install_module.subprocess, "check_call", lambda args: commands.append(args)
        )

        set_fastest_proxy()

        assert "tuna.tsinghua" in commands[0][-1]

    @pytest.mark.xfail(
        strict=True,
        reason="提示文案写“上海交通大学源”，实际设置的却是清华 TUNA 源",
    )
    def test_tuna_message_matches_tuna_source(self, monkeypatch, capsys):
        monkeypatch.setattr(
            install_module,
            "test_speed",
            lambda source: 0.9 if "aliyun" in source else 0.1,
        )
        monkeypatch.setattr(install_module.subprocess, "check_call", lambda args: 0)

        set_fastest_proxy()

        assert "上海交通大学" not in capsys.readouterr().out


class TestCheckAndInstallDependencies:
    @pytest.mark.xfail(
        strict=True,
        reason="`pip show` 不接受 -r/--requirement，这条检查必然抛 CalledProcessError，"
        "于是「依赖已经存在！」分支不可达，每次启动都会重装依赖并改写用户的全局 pip 源",
    )
    def test_uses_a_valid_pip_command(self, monkeypatch):
        commands = []
        monkeypatch.setattr(
            install_module.subprocess, "check_call", lambda args: commands.append(args)
        )

        check_and_install_dependencies()

        assert commands, "至少应执行一次依赖检查"
        assert "show" in commands[0]
        assert "-r" not in commands[0], "pip show 不支持 -r"

    def test_installs_when_check_fails(self, monkeypatch, capsys):
        commands = []

        def fake_check_call(args):
            commands.append(args)
            if "show" in args:
                raise subprocess.CalledProcessError(1, args)

        monkeypatch.setattr(install_module.subprocess, "check_call", fake_check_call)
        monkeypatch.setattr(install_module, "set_fastest_proxy", lambda: commands.append("proxy"))

        check_and_install_dependencies()

        assert "proxy" in commands
        assert any("install" in command for command in commands if isinstance(command, list))
        assert "安装完成！" in capsys.readouterr().out

    @pytest.mark.xfail(
        strict=True,
        reason="pip install 失败时不会执行 `pip config unset`，用户的全局 pip 源被永久改成镜像；"
        "还原语句应放在 try/finally 里",
    )
    def test_proxy_is_restored_when_install_fails(self, monkeypatch):
        commands = []

        def fake_check_call(args):
            commands.append(args)
            if "show" in args:
                raise subprocess.CalledProcessError(1, args)
            if "install" in args:
                raise subprocess.CalledProcessError(1, args)

        monkeypatch.setattr(install_module.subprocess, "check_call", fake_check_call)
        monkeypatch.setattr(install_module, "set_fastest_proxy", lambda: None)

        try:
            check_and_install_dependencies()
        except subprocess.CalledProcessError:
            pass

        assert any("unset" in command for command in commands if isinstance(command, list))

    def test_missing_requirements_file_is_reported(self, monkeypatch, capsys):
        monkeypatch.setattr(install_module, "find_requirements_file", lambda: None)

        check_and_install_dependencies()

        assert "无法找到requirements.txt文件！" in capsys.readouterr().out
