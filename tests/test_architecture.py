"""架构约束测试。

分两部分：

**第一部分是硬规则**（`TestLayerDirection`、`TestLibraryIsolation` 里的 core 一条）——
它们今天就是成立的，不需要名单，违反即失败。这是真正的架构契约。

**第二部分是棘轮**（ratchet）——`utils/` 的分层刚建立，还有历史遗留的越界
（业务层直接用 `win32api`、多处直接 `import cv2`、import 期副作用等）。
这些用"只减不增"的名单登记：现有违规放过，新增违规立刻失败。
名单每缩短一行，就是一次成功的迁移。

目标态与迁移顺序见仓库根目录 CLAUDE.md。
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

CORE = "utils/core"
CONFIG = "utils/config"
DRIVERS = "utils/drivers"
VISION = "utils/vision"
UI = "utils/ui"
FLOWS = "utils/flows"
TOOLS = "tools"

# --- 硬规则：每一层允许依赖的层（含自身）-------------------------------------
#
# 依赖单向向下：flows → vision | drivers → core，config 是被各层共用的横切包。
# core 可以依赖 config（配置读取），但 config 也只依赖 core，二者同在底层。
# ui 是顶层（和 flows 平级）：它要展示识别结果、响应热键，所以可以依赖 vision/drivers。
ALLOWED_LAYER_IMPORTS = {
    CORE: {CORE, CONFIG},
    CONFIG: {CONFIG, CORE},
    DRIVERS: {DRIVERS, CORE, CONFIG},
    VISION: {VISION, DRIVERS, CORE, CONFIG},
    UI: {UI, VISION, DRIVERS, CORE, CONFIG},
    FLOWS: {FLOWS, UI, VISION, DRIVERS, CORE, CONFIG},
    TOOLS: {TOOLS, CORE, CONFIG, DRIVERS, VISION, UI, FLOWS},
}

# --- 硬规则：core 必须是纯的 -----------------------------------------------
#
# core 能在没有游戏、没有屏幕的机器上跑单测，这是整个测试策略的地基。
FORBIDDEN_IN_CORE = {
    "win32api", "win32gui", "win32con", "win32ui", "win32process",
    "pyautogui", "pynput", "keyboard", "cv2",
}

# --- 棘轮名单：只减不增 ------------------------------------------------------

OS_INPUT_LIBS = {
    "win32api", "win32gui", "win32con", "win32ui", "win32process",
    "pyautogui", "pynput", "keyboard",
}
VISION_LIBS = {"cv2"}

# 理想态：只有 drivers/ 直接碰 OS 输入与窗口。
# 现状：flows/ 与 vision/、ui/ 里还有直接调用，迁移顺序见 CLAUDE.md §2.3。
# 注意：drivers/ 下的模块不算"债务" —— 那层存在的理由就是碰 OS，所以不登记。
# 名单只登记**跨层**违规。
OS_INPUT_ALLOWLIST = {
    "fhoe.py",
    f"{VISION}/get_angle.py",
    f"{UI}/pause.py",
    f"{UI}/record.py",
}

# 理想态：只剩 core/log.py（日志初始化必须最早执行）。
SIDE_EFFECT_ALLOWLIST = {
    "fhoe.py",
    f"{UI}/text_window.py",  # import 时启动默认调试窗口线程
    f"{CORE}/log.py",  # 配置 loguru handler，合法的启动期副作用
    f"{UI}/map_selector.py",  # 构造 cfg / Setting()
    f"{TOOLS}/update_file.py",  # 构造 cfg
}

# 理想态：空。
STAR_IMPORT_ALLOWLIST = {f"{TOOLS}/update_file.py"}

# 构造代价高、或在游戏未启动时会抛异常的构造函数。
EXPENSIVE_CONSTRUCTORS = (
    "ConfigurationManager()", "MapInfo()", "Setting()",
    "Window()", "Img()", "Pause(", "tk.Tk()",
)


def source_files():
    """所有参与架构约束的源码文件，返回 (仓库相对路径, 源码)。"""
    paths = sorted((REPO_ROOT / "utils").rglob("*.py"))
    paths += sorted((REPO_ROOT / "tools").rglob("*.py"))
    entry = REPO_ROOT / "fhoe.py"
    if entry.exists():
        paths.append(entry)
    for path in paths:
        yield path.relative_to(REPO_ROOT).as_posix(), path.read_text(encoding="utf-8")


LAYER_DIRS = {CORE, CONFIG, DRIVERS, VISION, UI, FLOWS}


def layer_of(rel_path):
    """把 `utils/vision/img.py`、`utils.vision`、`tools/x.py` 都映射到所属层。

    注意要处理两段形式：`from utils.vision import images` 给出的模块名是
    `utils.vision`，按分隔符切只有两段，容易被误判成 `utils` 自身。
    """
    parts = rel_path.split("/")
    if parts[0] == "utils":
        if len(parts) >= 2 and f"utils/{parts[1]}" in LAYER_DIRS:
            return f"utils/{parts[1]}"
        return "utils"
    return parts[0]


def imported_utils_layers(source):
    """源码里引用到的 utils/tools 层名集合。"""
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    layers = set()
    for module in modules:
        if not (module.startswith("utils") or module.startswith("tools")):
            continue
        layers.add(layer_of(module.replace(".", "/")))
    return layers


def imported_top_level_modules(source):
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def has_module_level_side_effect(source):
    """检测 import 时就执行的语句：顶层裸调用，或顶层赋值里调用了重构造函数。"""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return True
        if isinstance(node, ast.Assign):
            if any(c in ast.unparse(node.value) for c in EXPENSIVE_CONSTRUCTORS):
                return True
    return False


def star_imports(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    yield node.lineno


class TestLayerDirection:
    """依赖必须单向向下。这条今天就是成立的，没有名单。"""

    def test_layers_only_import_layers_they_are_allowed_to(self):
        violations = []
        for path, source in source_files():
            layer = layer_of(path)
            allowed = ALLOWED_LAYER_IMPORTS.get(layer)
            if allowed is None:
                continue  # fhoe.py 是入口，可以用全部
            for imported in imported_utils_layers(source):
                if imported not in allowed:
                    violations.append(f"{path}: {layer} 不该 import {imported}")
        assert violations == [], (
            "依赖方向被打破。规则：flows → vision|drivers → core，"
            "config 与 core 同在底层被共用。\n" + "\n".join(sorted(violations))
        )

    def test_every_layer_directory_exists(self):
        for layer in (CORE, CONFIG, DRIVERS, VISION, UI, FLOWS):
            assert (REPO_ROOT / layer).is_dir(), f"{layer}/ 不存在"

    def test_layers_have_empty_init_files(self):
        """__init__.py 保持为空：不要在包里做 re-export 或初始化。"""
        for layer in (CORE, CONFIG, DRIVERS, VISION, UI, FLOWS, "utils"):
            init_file = REPO_ROOT / layer / "__init__.py"
            assert init_file.exists(), f"{layer}/__init__.py 缺失"
            assert init_file.read_text(encoding="utf-8").strip() == "", (
                f"{layer}/__init__.py 应为空"
            )


class TestCoreIsPure:
    """core 层必须能在没有游戏、没有屏幕的机器上跑单测。"""

    def test_core_does_not_import_os_or_vision_libraries(self):
        violations = []
        for path, source in source_files():
            if layer_of(path) != CORE:
                continue
            found = imported_top_level_modules(source) & FORBIDDEN_IN_CORE
            if found:
                violations.append(f"{path}: {sorted(found)}")
        assert violations == [], (
            "core/ 不允许依赖窗口、输入、图像库。需要屏幕数据时，"
            "通过 core/ports.py 定义的接口注入。\n" + "\n".join(violations)
        )


class TestOsCouplingRatchet:
    """棘轮：理想态是只有 drivers/ 直接碰 OS。"""

    def test_no_new_module_touches_the_os_directly(self):
        offenders = sorted(
            path
            for path, source in source_files()
            if imported_top_level_modules(source) & OS_INPUT_LIBS
            and layer_of(path) != DRIVERS
            and path not in OS_INPUT_ALLOWLIST
        )
        assert offenders == [], (
            "这些模块新增了对 win32/pyautogui/pynput/keyboard 的直接依赖。\n"
            "请把它们放到 drivers/ 层，或通过注入的接口调用。\n"
            f"违规文件：{offenders}"
        )

    def test_allowlist_has_no_stale_entries(self):
        violating = {
            path
            for path, source in source_files()
            if imported_top_level_modules(source) & OS_INPUT_LIBS
            and layer_of(path) != DRIVERS
        }
        stale = sorted(OS_INPUT_ALLOWLIST - violating)
        assert stale == [], f"这些文件已不再直接依赖 OS 输入库，请从名单中移除：{stale}"


class TestVisionIsolation:
    """cv2 只允许出现在 vision/ —— 这条已经从棘轮升级成硬规则。

    2026-09：所有跨层的 cv2 调用都收口完毕，名单清空后就不再需要豁免机制。
    识别是最容易被游戏更新打碎的一层，让它的依赖面收在一处，才能单独回归。
    """

    def test_only_vision_imports_cv2(self):
        offenders = sorted(
            path
            for path, source in source_files()
            if imported_top_level_modules(source) & VISION_LIBS
            and layer_of(path) != VISION
        )
        assert offenders == [], (
            "这些模块在 vision/ 之外直接 import cv2。\n"
            "图像处理请放进 vision/，业务代码只消费「匹配结果对象」。\n"
            f"违规文件：{offenders}"
        )


class TestImportTimeSideEffects:
    """import 一个模块不应该启动线程、弹窗、建文件、连游戏。"""

    def test_no_new_modules_with_import_time_side_effects(self):
        offenders = sorted(
            path
            for path, source in source_files()
            if has_module_level_side_effect(source) and path not in SIDE_EFFECT_ALLOWLIST
        )
        assert offenders == [], (
            "这些模块在 import 时执行了副作用（裸调用，或顶层构造单例）。\n"
            "副作用请移入函数，由入口显式调用；单例请改为惰性获取。\n"
            f"违规文件：{offenders}"
        )

    def test_allowlist_has_no_stale_entries(self):
        violating = {
            path for path, source in source_files() if has_module_level_side_effect(source)
        }
        stale = sorted(SIDE_EFFECT_ALLOWLIST - violating)
        assert stale == [], f"这些文件已无 import 期副作用，请从名单中移除：{stale}"


class TestStarImports:
    def test_no_new_star_imports(self):
        offenders = sorted(
            f"{path}:{lineno}"
            for path, source in source_files()
            for lineno in star_imports(source)
            if path not in STAR_IMPORT_ALLOWLIST
        )
        assert offenders == [], (
            "星号导入会污染命名空间、让依赖关系不可见，也会让静态检查失效。\n"
            f"违规位置：{offenders}"
        )


class TestStandaloneScripts:
    """tools/ 是按路径调用或独立运行的脚本，不走包导入。"""

    def test_path_invoked_scripts_are_main_guarded(self):
        """被 `python tools/xxx.py` 调用的脚本必须有 __main__ 守卫。

        shutdown.py 曾经是反例（模块级跑 GUI，导入即阻塞），
        2026-09 修好后并入本规则。它的导入安全另有 tests/test_shutdown.py 专门覆盖。
        """
        for name in ("convert.py", "install_requirements.py", "shutdown.py"):
            source = (REPO_ROOT / TOOLS / name).read_text(encoding="utf-8")
            assert '__name__ == "__main__"' in source, (
                f"tools/{name} 缺少 __main__ 守卫：它会被按路径调用，"
                "但没有守卫时 import 就会执行脚本主体"
            )

    def test_tools_is_not_a_package(self):
        """tools/ 里的脚本按路径调用；变成包会诱导别人 import 它们。"""
        assert not (REPO_ROOT / TOOLS / "__init__.py").exists()

    def test_tools_sits_at_the_same_depth_as_utils(self):
        """这两个目录都在仓库根下一级。

        `install_requirements.py` / `convert.py` 用 `dirname(__file__)` 的上一级
        当仓库根去 requirements.txt 和地图 JSON。它们从 utils/ 挪到 tools/ 后
        结论不变；如果哪天再挪深一层，这条会先失败。
        """
        assert (REPO_ROOT / TOOLS).parent == REPO_ROOT
        assert (REPO_ROOT / "utils").parent == REPO_ROOT


@pytest.mark.parametrize("layer", [CORE, DRIVERS, VISION, UI, FLOWS])
def test_layers_are_not_empty(layer):
    assert list((REPO_ROOT / layer).glob("*.py")), f"{layer} 下没有任何模块"
