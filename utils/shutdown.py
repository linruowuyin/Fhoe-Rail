import tkinter as tk
from tkinter import messagebox
import os
from PIL import Image, ImageTk

window = tk.Tk()
window.title("倒计时强制关机程序")

background_image = Image.open("./picture/2.png")
background_photo = ImageTk.PhotoImage(background_image)

background_label = tk.Label(window, image=background_photo)
background_label.place(relwidth=1, relheight=1)

font_style = ("SimSun", 25)

countdown_minutes = tk.StringVar()
countdown_minutes.set("240")

counting_down = False

timer_id = [None]

def start_countdown():
    global counting_down
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
                    str(countdown_seconds // 60) + "分" + str(countdown_seconds % 60) + "秒"
                )
                timer_id[0] = window.after(1000, update_countdown)
            else:
                if counting_down:
                    os.system("shutdown /s /t 1")
        
        update_countdown()
    except ValueError:
        messagebox.showerror("错误", "请输入一个有效的正整数分钟数")

def cancel_countdown():
    global counting_down
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

minutes_entry = tk.Entry(window, textvariable=countdown_minutes, font=font_style, width=11, justify='center')
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
