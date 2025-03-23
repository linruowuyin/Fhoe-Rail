# utils/config/text_window.py
import queue
import threading
import tkinter as tk
from typing import Any, Literal


class TextWindow:
    """透明文本窗口类，用于在屏幕上显示可穿透点击的文本。

    该类创建一个无边框、透明的窗口，可以显示带有描边效果的文本。
    窗口支持点击穿透，不会影响其他窗口的操作。
    """

    def __init__(self):
        # 初始化ready事件
        self.ready = threading.Event()
        """初始化TextWindow实例。

        创建一个透明的tkinter窗口，配置其属性使其支持点击穿透，
        并设置Canvas用于显示带描边效果的文本。
        """
        # 创建并配置主窗口
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # 移除窗口边框
        self.root.attributes("-alpha", 1.0)  # 设置窗口透明度
        self.root.attributes("-topmost", True)  # 窗口置顶
        self.root.wm_attributes("-disabled", True)  # 禁用窗口交互
        self.root.wm_attributes("-topmost", True)  # 确保窗口置顶
        self.root.lower()  # 将窗口置于底层，避免抢占焦点

        # 配置窗口的高级属性
        if hasattr(self.root, "attributes"):
            try:
                self.root.attributes("-toolwindow", 1)  # 设置为工具窗口
                self.root.attributes("-clickthrough", 1)  # 启用点击穿透
            except tk.TclError:
                pass

        # 创建并配置Canvas
        self.canvas = tk.Canvas(
            self.root,
            bg="#FFFFFF",
            highlightthickness=0
        )
        self.canvas.pack(pady=0, padx=0)

        # 初始时隐藏窗口
        self.root.withdraw()

        # 禁用所有鼠标事件
        self._disable_mouse_events()

        # 初始化消息队列
        self.queue = queue.Queue()

        # 启动窗口管理
        self._start_window_management()

    def _disable_mouse_events(self):
        """禁用Canvas的所有鼠标事件。"""
        events = ["<Button-1>", "<Button-2>", "<Button-3>",
                  "<Motion>", "<Enter>", "<Leave>"]
        for event in events:
            self.canvas.bind(event, lambda e: "break")

    def _start_window_management(self):
        """启动窗口管理，包括保持窗口置顶和处理消息队列。"""
        def keep_on_top():
            """保持窗口置顶。"""
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(1000, keep_on_top)

        def process_queue():
            """处理消息队列中的任务。"""
            try:
                while True:
                    task = self.queue.get_nowait()
                    task()
            except queue.Empty:
                pass
            self.root.after(100, process_queue)

        keep_on_top()
        process_queue()

    def show_text(self, text: str, x: int = 100, y: int = 100) -> None:
        """在指定位置显示或更新文字。

        Args:
            text: 要显示的文本内容
            x: 窗口左上角的x坐标
            y: 窗口左上角的y坐标
        """
        # 清除现有内容
        self.canvas.delete("all")

        # 确保窗口可见
        self.root.deiconify()

        # 计算文本尺寸
        font = ("TkDefaultFont", 14, "bold")
        text_width = self.canvas.create_text(
            0, 0,
            text=text,
            font=font,
            anchor="nw"
        )
        bbox = self.canvas.bbox(text_width)
        self.canvas.delete(text_width)

        # 设置Canvas尺寸
        if bbox:
            width = bbox[2] - bbox[0] + 30
            height = bbox[3] - bbox[1]
            self.canvas.configure(width=width, height=height)

        # 创建带描边效果的文本
        offset = 1
        for dx, dy in [(-offset, -offset), (-offset, offset),
                       (offset, -offset), (offset, offset)]:
            self.canvas.create_text(
                15 + dx, dy,
                text=text,
                font=font,
                fill="#D3D3D3",
                anchor="nw",
                width=width - 30
            )

        # 创建主文本
        self.canvas.create_text(
            15, 0,
            text=text,
            font=font,
            fill="black",
            anchor="nw",
            width=width - 30
        )

        # 设置窗口位置
        self.root.geometry(f"+{x}+{y}")


# 全局实例字典，用于存储多个TextWindow实例
TEXT_WINDOWS = {}
TKINTER_THREADS = {}


def create_tkinter_window(window_id: str = "default") -> None:
    """创建Tkinter窗口实例。

    Args:
        window_id: 窗口实例的唯一标识符

    创建TextWindow实例并启动主循环。
    设置ready事件，表示窗口初始化完成。
    """
    global TEXT_WINDOWS
    text_window = TextWindow()
    TEXT_WINDOWS[window_id] = text_window
    text_window.ready.set()
    text_window.root.mainloop()


def start_tkinter_thread(window_id: str = "default") -> None:
    """启动Tkinter线程。

    Args:
        window_id: 窗口实例的唯一标识符

    创建并启动一个守护线程来运行Tkinter窗口。
    """
    global TKINTER_THREADS
    thread = threading.Thread(
        target=create_tkinter_window,
        args=(window_id,),
        daemon=True
    )
    TKINTER_THREADS[window_id] = thread
    thread.start()


def show_text(text: Any, x: int = 100, y: int = 100,
              mode: Literal["nouid", "showuid"] = "nouid",
              window_id: str = "default") -> None:
    """显示或更新文本。

    Args:
        text: 要显示的文本内容
        x: 窗口左上角的x坐标
        y: 窗口左上角的y坐标
        mode: 显示模式
            - 'nouid': x坐标左移150像素
            - 'showuid': 保持原坐标
        window_id: 窗口实例的唯一标识符
    """
    if mode not in ["nouid", "showuid"]:
        mode = "nouid"

    adjusted_x = x - 150 if mode == "nouid" else x

    if window_id in TEXT_WINDOWS:
        text_window = TEXT_WINDOWS[window_id]
        text_window.queue.put(
            lambda: text_window.show_text(text, adjusted_x, y)
        )


# 启动默认Tkinter线程
start_tkinter_thread("default")
