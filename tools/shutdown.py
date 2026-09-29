"""倒计时强制关机 GUI —— 独立脚本，按路径运行。

    python tools/shutdown.py

⚠️  这个模块**不允许被 import**（tests/test_shutdown.py 有守护）。
    GUI 必须推迟到 `main()` 里创建：Tk 根窗口一旦在模块级建立，
    `import tools.shutdown` 就会建窗口、调用 `mainloop()` 永久阻塞，
    而且 30 秒后会自动启动关机倒计时（终点是 `os.system("shutdown /s /t 1")`）。
    这正是它曾经的样子 —— 见 CLAUDE.md 的 R16。

    新增功能时请继续留在 `main()` 内部，不要在模块级碰 tk。
"""

import os
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk


def _resolve_image(path):
    """按 webp > png > jpg 优先级查找实际存在的文件"""
    base, _ = os.path.splitext(path)
    for ext in (".webp", ".png", ".jpg"):
        cand = base + ext
        if os.path.isfile(cand):
            return cand
    return path


def main():
    """创建窗口并进入事件循环。所有 GUI 状态都是本函数的局部变量。"""
    window = tk.Tk()
    window.title("倒计时强制关机程序")

    background_image = Image.open(_resolve_image("./picture/2.png"))
    # 注意：PhotoImage 必须被引用着，否则会被 GC 回收、背景变空白。
    # 它是 main() 的局部变量，而 mainloop() 在本函数内运行，生命周期正好覆盖。
    background_photo = ImageTk.PhotoImage(background_image)

    background_label = tk.Label(window, image=background_photo)
    background_label.place(relwidth=1, relheight=1)

    font_style = ("SimSun", 25)

    countdown_minutes = tk.StringVar()
    countdown_minutes.set("240")

    counting_down = False

    timer_id = [None]

    def start_countdown():
        nonlocal counting_down
        try:
            minutes = int(countdown_minutes.get())
            if minutes <= 0:
                raise ValueError
            countdown_seconds = minutes * 60
            counting_down = True
            minutes_entry.config(state="disabled")
            start_button.config(state="disabled")
            cancel_button.config(state="normal")

            def update_countdown():
                nonlocal countdown_seconds
                if countdown_seconds > 0 and counting_down:
                    countdown_seconds -= 1
                    countdown_minutes.set(
                        str(countdown_seconds // 60)
                        + "分"
                        + str(countdown_seconds % 60)
                        + "秒"
                    )
                    timer_id[0] = window.after(1000, update_countdown)
                else:
                    if counting_down:
                        os.system("shutdown /s /t 1")

            update_countdown()
        except ValueError:
            messagebox.showerror("错误", "请输入一个有效的正整数分钟数")

    def cancel_countdown():
        nonlocal counting_down
        counting_down = False
        if timer_id[0]:
            window.after_cancel(timer_id[0])
        minutes_entry.config(state="normal")
        start_button.config(state="normal")
        cancel_button.config(state="disabled")

    def start_initial_countdown():
        initial_minutes = int(countdown_minutes.get())
        countdown_minutes.set(str(initial_minutes))
        start_countdown()

    window.after(30000, start_initial_countdown)

    countdown_label = tk.Label(window, textvariable=countdown_minutes, font=font_style)
    countdown_label.pack(pady=20)

    minutes_entry = tk.Entry(
        window, textvariable=countdown_minutes, font=font_style, width=11, justify="center"
    )
    minutes_entry.pack(pady=11)

    start_button = tk.Button(
        window,
        text="开始倒计时",
        command=start_countdown,
        font=("SimSun", 25),
        width=10,
    )
    start_button.pack(pady=10)

    cancel_button = tk.Button(
        window,
        text="取消倒计时",
        command=cancel_countdown,
        font=("SimSun", 25),
        width=10,
        state="disabled",
    )
    cancel_button.pack(pady=10)

    window.geometry("468x358")
    window.mainloop()


if __name__ == "__main__":
    main()
