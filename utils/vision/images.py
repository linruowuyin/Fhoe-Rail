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

#: `id(ndarray) → 解析后的路径`，用来从一张**已经加载过的**图反查它来自哪个文件。
#: 匹配那一层只拿得到 ndarray（`Matcher.match_screenshot` 的签名里没有路径），所以靠对象
#: 身份认回来。注意键是 `resolve_path` 之后的**原样路径**：`./picture/x.png` 与
#: `picture\x.png` 是两个不同的键、各占一条缓存（同一个文件被加载两次是既有行为），
#: 但两者的 `basename` 一样 —— 收集器用的正是 basename，不受影响。
#: 只登记缓存里那些：缓存持有强引用，`id` 不会被回收复用。
#: 反色（`cv2.bitwise_not`）与旋转造出来的新数组不在表里，反查返回 None。
_PATH_BY_ID = {}


def resolve_path(img_path):
    """解析图片路径，按优先级查找同名文件：.webp > .png > .jpg。

    若原路径后缀为图片格式（webp/png/jpg），则依次尝试同名文件的其他后缀，
    返回第一个实际存在的文件路径；所有候选都不存在时返回原路径，
    由调用方处理文件不存在的情况。
    """
    base, ext = os.path.splitext(img_path)
    if ext.lower() in (".webp", ".png", ".jpg"):
        for cand_ext in (".webp", ".png", ".jpg"):
            cand = base + cand_ext
            if os.path.isfile(cand):
                return cand
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
    """
    _IMG_CACHE.clear()
    _PATH_BY_ID.clear()
