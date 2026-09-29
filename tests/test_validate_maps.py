"""tools/validate_maps.py —— 地图校验器的入口，以及它作为 CI 门的行为。

要钉住的两件事：

1. **它必须能在非 UTF-8 的 stdout 下跑完。** GitHub 的 Windows runner 上 stdout
   默认是 cp1252，中文编不出来会 `UnicodeEncodeError` —— 这一步会在 CI 里直接红掉
   （2026-09-30 就这么红过一次）。注意这不是"输出难看"，是**进程崩掉**。
2. **它是门**：有 error 时必须退出码 1，并在输出里点明是哪个文件、哪一处。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import tools.validate_maps as validate_maps

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNonUtf8Console:
    """CI 的 Windows runner 上 stdout 是 cp1252 —— 打印中文会 UnicodeEncodeError。"""

    def test_survives_a_cp1252_stdout(self):
        """用子进程 + `PYTHONIOENCODING=cp1252` 忠实复现 runner 的条件。

        （不能在本进程里测：pytest 的捕获会把 sys.stdout 换掉，模拟不出"启动时就是
        cp1252"这件事。）
        """
        env = {**os.environ, "PYTHONIOENCODING": "cp1252"}

        proc = subprocess.run(
            [sys.executable, "tools/validate_maps.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            env=env,
        )

        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert b"UnicodeEncodeError" not in proc.stderr, stderr
        assert proc.returncode == 0, stderr
        # 不只是"没崩"：中文摘要要真的打出来（掰成 UTF-8 才算修好，
        # 靠 errors="replace" 把中文换成问号不算）
        assert "校验".encode("utf-8") in proc.stdout, proc.stdout[:200]


class TestItIsAGate:
    """有 error 时退出码 1 —— 这一步能接进 CI 全靠这个约定。"""

    def test_error_exits_nonzero_and_points_at_the_step(self, isolated_cwd, capsys):
        folder = isolated_cwd / "map" / "default"
        folder.mkdir(parents=True)
        # 修饰键写在第一个位置：分发表会把 "drag" 当步骤键，静默走错分支
        (folder / "map_1-1_0.json").write_text(
            json.dumps(
                {
                    "name": "1-1 空间站「黑塔」",
                    "author": "tester",
                    "start": [{"drag": 1.5, "picture\\x.png": 1.0}],
                    "map": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        code = validate_maps.main(["default"])

        out = capsys.readouterr().out
        assert code == 1
        assert "map_1-1_0.json" in out, "要点名是哪个文件"
        assert "修饰键" in out, "要说清是哪一处错"

    def test_clean_map_passes(self, isolated_cwd, capsys):
        folder = isolated_cwd / "map" / "default"
        folder.mkdir(parents=True)
        (folder / "map_1-1_0.json").write_text(
            json.dumps(
                {"name": "1-1 空间站「黑塔」", "author": "tester", "start": [], "map": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        assert validate_maps.main(["default"]) == 0
        assert "0 个有错误" in capsys.readouterr().out
