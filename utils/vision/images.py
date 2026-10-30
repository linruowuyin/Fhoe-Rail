"""图片资源的加载与缓存。

模板图是**被代码消费的资源**，不是测试数据，所以放在 vision 层随代码版本化。
带 mtime 缓存：同一张图在一次运行里只 `imread` 一次，文件更新后自动失效。

注意：加载回来的图是 **BGR 序**（`cv2.imread` 的约定），与 `drivers.screen`
取出的帧一致 —— 两边任一改了通道序，模板匹配就会静默失准。
"""

import os

import cv2

from utils.core.log import log
from utils.vision import assets

#: 运行时默认加载的 UI 图。键名即 `Img` 实例上的属性名，路径从登记表取。
DEFAULT_IMAGE_PATHS = {
    "main_ui": assets.path("finish_fighting"),
    "doubt_ui": assets.path("doubt"),
    "warn_ui": assets.path("warn"),
    "finish2_ui": assets.path("finish_fighting2"),
    "finish2_1_ui": assets.path("finish_fighting2_1"),
    "finish2_2_ui": assets.path("finish_fighting2_2"),
    "finish3_ui": assets.path("finish_fighting3"),
    "finish4_ui": assets.path("finish_fighting4"),
    "finish5_ui": assets.path("finish_fighting5"),
    "battle_esc_check": assets.path("battle_esc_check"),
    "switch_run": assets.path("switch_run"),
}

#: 图片加载缓存：{(路径): (文件mtime, ndarray)}，文件更新后自动失效
_IMG_CACHE = {}

#: stem 索引缓存：{小写 stem: 路径}，由 `assets.scan_picture_files()` 构建。
#: 懒构建，`clear_cache()` 是唯一清理点（R15）。运行期不会新增资源；
#: 若将来重新启用 `update_file` 在进程内下载图片，下载完要调一次 `clear_cache()`。
_STEM_INDEX = None

#: `id(ndarray) → 解析后的路径`，用来从一张**已经加载过的**图反查它来自哪个文件。
#: 匹配那一层只拿得到 ndarray（`Matcher.match_screenshot` 的签名里没有路径），所以靠对象
#: 身份认回来。注意键是 `resolve_path` 之后的**原样路径**：`./picture/x.png` 与
#: `picture\x.png` 是两个不同的键、各占一条缓存（同一个文件被加载两次是既有行为），
#: 但两者的 `basename` 一样 —— 收集器用的正是 basename，不受影响。
#: 只登记缓存里那些：缓存持有强引用，`id` 不会被回收复用。
#: 反色（`cv2.bitwise_not`）与旋转造出来的新数组不在表里，反查返回 None。
_PATH_BY_ID = {}


def _stem_index():
    """懒构建 stem 索引（见 `assets.scan_picture_files`）。"""
    global _STEM_INDEX
    if _STEM_INDEX is None:
        _STEM_INDEX, _ = assets.scan_picture_files()
    return _STEM_INDEX


def _is_picture_ref(path):
    """这个字符串是不是指向 `picture/` 的资源 ID。

    兼容三种写法：`picture\\x.png`（地图 JSON）、`./picture/x.png`（代码旧写法）、
    以及 `picture/` 的绝对路径（WebUI 传进来的 `os.path.join(BASE_DIR, "picture", ...)`）。
    不在 `picture/` 下的路径不参与 stem 回退 —— 避免 `./assets/foo/x.png` 找不到时
    误解析到 `picture/` 里的同名图。
    """
    normalized = path.replace("\\", "/")
    if normalized.startswith(assets.PICTURE_REF_PREFIXES):
        return True
    try:
        root = os.path.abspath(assets.PICTURE_ROOT).replace("\\", "/")
        return os.path.abspath(path).replace("\\", "/").startswith(root + "/")
    except (OSError, ValueError):
        return False


def _stem_of(path):
    """取去掉目录与后缀的文件名（同时兼容 `/` 与 `\\` 分隔符）。"""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return os.path.splitext(name)[0]


def resolve_path(img_path):
    """解析图片路径 → 实际文件路径。

    两步：

    1. 按字面路径找，后缀按 `.webp > .png > .jpg` 回退。
    2. 字面路径不存在、且这是 `picture/` 下的引用时，按 **stem（文件名去掉后缀）
       查递归索引**。地图 JSON 里的 `picture\\xxx.png` 是资源 ID 而不是物理路径
       （R25）：文件搬进哪个子目录都不影响解析，前提是 stem 全局唯一
       （`tools/validate_pictures.py` 在 CI 拦重名）。

    两种情况都找不到时返回原路径，由调用方处理文件不存在。
    """
    base, ext = os.path.splitext(img_path)
    if ext.lower() in (".webp", ".png", ".jpg"):
        for cand_ext in (".webp", ".png", ".jpg"):
            cand = base + cand_ext
            if os.path.isfile(cand):
                return cand
        if _is_picture_ref(img_path):
            found = _stem_index().get(_stem_of(img_path).lower())
            if found is not None:
                return found
    return img_path


def get_img(img_path):
    """获取图片（带 mtime 缓存）。

    :param img_path: 图片路径
    :return: BGR ndarray；加载失败返回 None（调用方必须处理 None）
    """
    # 延迟 import：samples 要拿 cv2 编码 webp，而 images 被 matcher 依赖 ——
    # 模块级互相 import 会成环。这里只在真正加载时用一次，代价可以忽略。
    from utils.vision import samples

    img_path = resolve_path(img_path)

    try:
        mtime = os.path.getmtime(img_path)
    except OSError:
        log.error(f"加载图片时发生错误: 路径不存在或文件损坏: {img_path}")
        return None

    cached = _IMG_CACHE.get(img_path)
    if cached is not None and cached[0] == mtime:
        samples.note_loaded(img_path)
        return cached[1]

    try:
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"图片加载失败，路径不存在或文件损坏: {img_path}")
        _IMG_CACHE[img_path] = (mtime, img)
        _PATH_BY_ID[id(img)] = img_path
        samples.note_loaded(img_path)
        return img
    except Exception as e:
        log.error(f"加载图片时发生错误: {e}")
        return None


def path_of(image):
    """反查一张图来自哪个文件；不是本模块加载的就返回 None。

    给「匹配那一层」用 —— 它只拿得到 ndarray。反色 / 旋转造出来的新数组返回 None。
    """
    return _PATH_BY_ID.get(id(image)) if image is not None else None


def strategy_of(image):
    """一张模板 → 匹配策略（`assets.MATCH_COLOR` / `MATCH_SHAPE`）。

    未登记、或反色/旋转造出来的临时数组按颜色匹配。
    """
    path = path_of(image)
    if not path:
        return assets.MATCH_COLOR
    return assets.strategy_for_path(path)


def search_offset_of(image):
    """一张模板 → 调用点登记的搜索区域；未登记时 None（调用点全屏搜索）。"""
    path = path_of(image)
    if not path:
        return None
    return assets.search_offset_for_path(path)


def threshold_of(image):
    """一张模板 → 探针默认阈值（登记表里主要检测用途的值）；未登记时 None。"""
    path = path_of(image)
    if not path:
        return None
    return assets.threshold_for_path(path)


def load_all(image_paths=None) -> dict:
    """按 {属性名: 路径} 批量加载，加载失败的只告警、不进结果。

    :param image_paths: 默认用 DEFAULT_IMAGE_PATHS
    :return: {属性名: ndarray}
    """
    loaded = {}
    for name, path in (image_paths or DEFAULT_IMAGE_PATHS).items():
        img = get_img(path)
        if img is not None:
            loaded[name] = img
        else:
            log.warning(f"警告: 图片 {name} 加载失败，路径为 {path}")
    return loaded


def clear_cache():
    """清空缓存。测试用；生产环境靠 mtime 自动失效。

    身份表跟着一起清 —— 它只对缓存里那些活着的数组有意义（R15 的清理点）。
    stem 索引也在这里清：目录结构变了（如重命名 / 搬迁）之后必须重建。
    """
    global _STEM_INDEX
    _IMG_CACHE.clear()
    _PATH_BY_ID.clear()
    _STEM_INDEX = None
