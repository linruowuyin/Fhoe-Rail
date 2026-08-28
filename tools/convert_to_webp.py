"""
批量将 picture 目录下的 PNG 图片转换为无损 WebP 格式。
转换后删除原 PNG 文件。
"""

import os
import sys
from PIL import Image

PICTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "picture"
)


def convert():
    png_files = []
    for root, dirs, files in os.walk(PICTURE_DIR):
        for f in files:
            if f.lower().endswith(".png"):
                png_files.append(os.path.join(root, f))

    total_png_size = 0
    total_webp_size = 0
    failed = []

    print(f"Found {len(png_files)} PNG files in {PICTURE_DIR}")
    print("-" * 60)

    for i, png_path in enumerate(sorted(png_files), 1):
        rel_path = os.path.relpath(png_path, PICTURE_DIR)
        png_size = os.path.getsize(png_path)
        total_png_size += png_size

        webp_path = png_path[:-4] + ".webp"

        try:
            img = Image.open(png_path)
            # preserve mode: RGBA for transparency, RGB otherwise
            if img.mode == "P":
                img = img.convert("RGBA")
            img.save(webp_path, "WEBP", lossless=True)

            webp_size = os.path.getsize(webp_path)
            total_webp_size += webp_size

            # delete original png
            os.remove(png_path)

            ratio = (1 - webp_size / png_size) * 100 if png_size > 0 else 0
            print(
                f"[{i:3d}/{len(png_files)}] {rel_path:40s}  {png_size:>8d} -> {webp_size:>8d} B  ({ratio:+.0f}%)"
            )
        except Exception as e:
            failed.append((rel_path, str(e)))
            print(f"[{i:3d}/{len(png_files)}] {rel_path:40s}  FAILED: {e}")

    print("-" * 60)
    print(
        f"Total PNG size:    {total_png_size:>10,d} bytes ({total_png_size / 1024:.1f} KB)"
    )
    print(
        f"Total WebP size:   {total_webp_size:>10,d} bytes ({total_webp_size / 1024:.1f} KB)"
    )
    if total_png_size > 0:
        saved = (1 - total_webp_size / total_png_size) * 100
        print(
            f"Saved:             {total_png_size - total_webp_size:>10,d} bytes ({saved:.1f}%)"
        )
    if failed:
        print(f"\nFailed: {len(failed)} files")
        for path, err in failed:
            print(f"  {path}: {err}")
        sys.exit(1)
    else:
        print(f"\nAll {len(png_files)} files converted successfully.")


if __name__ == "__main__":
    convert()
