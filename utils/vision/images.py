"""图片资源的加载与缓存。

模板图是**被代码消费的资源**，不是测试数据，所以放在 vision 层随代码版本化。
带 mtime 缓存：同一张图在一次运行里只 `imread` 一次，文件更新后自动失效。

注意：加载回来的图是 **BGR 序**（`cv2.imread` 的约定），与 `drivers.screen`
取出的帧一致 —— 两边任一改了通道序，模板匹配就会静默失准。
"""

import os

import cv2
import numpy as np

from utils.core.log import log

#: 运行时默认加载的 UI 图。键名即 `Img` 实例上的属性名。
DEFAULT_IMAGE_PATHS = {
    "main_ui": "./picture/finish_fighting.png",
    "doubt_ui": "./picture/doubt.png",
    "warn_ui": "./picture/warn.png",
    "finish2_ui": "./picture/finish_fighting2.png",
    "finish2_1_ui": "./picture/finish_fighting2_1.png",
    "finish2_2_ui": "./picture/finish_fighting2_2.png",
    "finish3_ui": "./picture/finish_fighting3.png",
    "finish4_ui": "./picture/finish_fighting4.png",
    "finish5_ui": "./picture/finish_fighting5.png",
    "battle_esc_check": "./picture/battle_esc_check.png",
    "switch_run": "./picture/switch_run.png",
}

#: 图片加载缓存：{(路径): (文件mtime, ndarray)}，文件更新后自动失效
_IMG_CACHE = {}


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
    img_path = resolve_path(img_path)

    try:
        mtime = os.path.getmtime(img_path)
    except OSError:
        log.error(f"加载图片时发生错误: 路径不存在或文件损坏: {img_path}")
        return None

    cached = _IMG_CACHE.get(img_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"图片加载失败，路径不存在或文件损坏: {img_path}")
        _IMG_CACHE[img_path] = (mtime, img)
        return img
    except Exception as e:
        log.error(f"加载图片时发生错误: {e}")
        return None


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
    """清空缓存。测试用；生产环境靠 mtime 自动失效。"""
    _IMG_CACHE.clear()
