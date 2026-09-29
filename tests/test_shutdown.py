"""tools/shutdown.py —— 倒计时关机 GUI 的导入安全。

这个脚本**故意不被 import**：它跑的是 Tk 事件循环。曾经它在模块级创建根窗口并
调用 `mainloop()`，于是任何 `import tools.shutdown` 都会永久阻塞，30 秒后还会
自动启动关机倒计时（终点是 `os.system("shutdown /s /t 1")`）。

修法是加 `__main__` 守卫、把 GUI 全部收进 `main()`。这里既用静态分析钉住
结构，也用子进程真正跑一次 import —— 后者才是当初出问题的那个行为。
"""

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHUTDOWN_PATH = REPO_ROOT / "tools" / "shutdown.py"
SOURCE = SHUTDOWN_PATH.read_text(encoding="utf-8")


def scanned_files():
    """会参与「谁 import 了 shutdown」扫描的所有源码。"""
    files = list((REPO_ROOT / "utils").rglob("*.py"))
    files += list((REPO_ROOT / "tools").rglob("*.py"))
    files += list((REPO_ROOT / "webui").rglob("*.py"))
    entry = REPO_ROOT / "fhoe.py"
    if entry.exists():
        files.append(entry)
    return files


def module_level_calls(tree):
    """模块顶层的裸调用表达式（不含函数体内部）。"""
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            yield ast.unparse(node.value)


def module_level_assignments(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            yield ast.unparse(node)


class TestImportIsSafe:
    def test_importing_the_module_returns_promptly(self):
        """真跑一次 import —— 这是当初出问题的行为本身。

        修复前这个子进程会挂死到超时；静态分析能看结构，但只有真正 import
        一次才能证明它不会再阻塞。
        """
        result = subprocess.run(
            [sys.executable, "-c", "import tools.shutdown"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode == 0, f"导入失败：{result.stderr[-400:]}"

    def test_mainloop_is_not_called_at_module_level(self):
        calls = list(module_level_calls(ast.parse(SOURCE)))
        assert not any("mainloop" in call for call in calls), (
            f"模块级调用了 mainloop，导入即阻塞：{calls}"
        )

    def test_tk_root_is_not_created_at_module_level(self):
        assignments = list(module_level_assignments(ast.parse(SOURCE)))
        assert not any("Tk()" in assignment for assignment in assignments), (
            f"模块级创建了 Tk 根窗口：{assignments}"
        )

    def test_tk_is_not_touched_at_module_level_at_all(self):
        """更宽的守卫：模块级不该出现任何 tk 调用。"""
        calls = list(module_level_calls(ast.parse(SOURCE)))
        assert not any(call.startswith("tk.") for call in calls), calls


class TestEntryPoint:
    def test_gui_is_behind_a_main_guard(self):
        assert '__name__ == "__main__"' in SOURCE

    def test_gui_lives_inside_main(self):
        """窗口创建必须发生在 main() 的函数体里。"""
        tree = ast.parse(SOURCE)
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        body = ast.unparse(main)
        assert "tk.Tk()" in body
        assert "mainloop" in body

    def test_source_still_contains_a_mainloop_somewhere(self):
        """如果哪天 GUI 循环被彻底删掉，前面的断言会变成空转。"""
        assert "mainloop" in SOURCE


class TestNobodyImportsIt:
    def test_module_is_not_imported_anywhere(self):
        """一旦有人 import 它，那条代码路径就会拉起一个 GUI 进程。"""
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in scanned_files()
            if path != SHUTDOWN_PATH
            and "tools.shutdown" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"这些文件 import 了 shutdown：{offenders}"

    def test_shutdown_is_never_re_exported(self):
        """tools/ 不是包，没有 __init__.py；utils/ 的也必须是空的。"""
        assert not (REPO_ROOT / "tools" / "__init__.py").exists(), (
            "tools/ 是按路径调用的脚本目录，不应变成可 import 的包"
        )
        init_file = REPO_ROOT / "utils" / "__init__.py"
        assert init_file.read_text(encoding="utf-8").strip() == ""
