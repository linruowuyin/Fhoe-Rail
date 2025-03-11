#!/usr/bin/env python3
# Author AlisaCat
# -*- encoding:utf-8 -*-
# Created by AlisaCat at 2023/5/7

import builtins
import time
from collections import defaultdict
from datetime import datetime
import os
import sys
import ctypes

import orjson
import win32api
import win32con
from pynput import keyboard
from pynput import mouse
from pynput.mouse import Controller as mouseController

from utils.config.config import ConfigurationManager

def record_main():
    cfg = ConfigurationManager()

    def timestamped_print(*args, **kwargs):
        currentDT = datetime.now().strftime('%H:%M:%S')
        builtins.print(str(currentDT), *args, **kwargs)

    print = timestamped_print

    def run_as_admin():
        try:
            # 检查是否已经有管理员权限
            if ctypes.windll.shell32.IsUserAnAdmin():
                return
            # 如果没有管理员权限，则使用管理员权限重新启动脚本
            script_path = os.path.abspath(sys.argv[0])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, script_path, None, 1)
            return  # 修改这里，使用return退出函数而不是sys.exit(0)
        except Exception as e:
            print(f"Failed to run as admin: {e}")
            sys.exit(1)

    # 在这里运行获取管理员权限的函数
    run_as_admin()

    print("3s后开启录制,F9终止保存")
    time.sleep(3)
    print("start")
    # 获取到游戏中心点坐标
    cen_mouse_pos = mouseController().position
    print("中心点坐标", cen_mouse_pos)
    mouse_watch = True

    key_list = ['w', 's', 'a', 'd', 'f', 'x', 'r', 'e', 'v']  # 匹配锄大地
    # 输出列表
    event_list = []
    # 不同操作间延迟记录
    last_time = time.time()
    # 按键按下的时间字典
    # key_down_time = {}
    # 创建一个默认值为0的字典
    key_down_time = defaultdict(int)

    # 控制是否输出调试信息的开关
    debug_mode = True

    mouse_move_pos_list = []

    mouse_val = 200  # 每次视角移动距离


    def Click(points):
        x, y = points
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.5)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    real_width = cfg.read_json_file("config.json")['real_width']

    def on_press(key):
        nonlocal last_time, key_down_time
        try:
            if key.char in key_list and key.char in key_down_time:
                pass
            elif key.char in key_list:
                save_mouse_move_by_key()
                key_down_time[key.char] = time.time()
                if debug_mode:
                    print("捕捉按键按下:", key.char, time.time())
        except AttributeError:
            pass

        # 检查是否按下空格键
        if key == keyboard.Key.space:
            save_mouse_move_by_key()
            event_list.append(
                {'key': 'space', 'time_sleep': time.time() - last_time})
            last_time = time.time()
            print("捕捉: space")

        # 检查是否按下Esc键
        if key == keyboard.Key.esc:
            save_mouse_move_by_key()
            event_list.append(
                {'key': 'esc', 'time_sleep': time.time() - last_time})
            last_time = time.time()
            print("捕捉: esc")


    def on_release(key):
        nonlocal last_time, key_down_time, mouse_move_pos_list, cen_mouse_pos, mouse_watch
        current_time = time.time()
        try:
            if key.char in key_list and key.char in key_down_time:
                event_list.append(
                    {'key': key.char, 'time_sleep': key_down_time[key.char] - last_time,
                     'duration': round(time.time() - key_down_time[key.char], 2)})  # Round the duration to 2 decimal places
                last_time = time.time()
                del key_down_time[key.char]
                if debug_mode:
                    print("捕捉:", event_list[-1])
                if key.char == "x":
                    if debug_mode:
                        print("捕捉X进入战斗")
                    mouse_watch = False
                    Click(cen_mouse_pos)
                    mouse_watch = True
        except AttributeError:
            pass
        if key == keyboard.Key.left:
            x = mouse_val * -1
            dx = int(x * 1295 / real_width)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, 0)  # 进行视角移动
            mouse_move_pos_list.append(
                {"mouse_move_dxy": (x, 0), "time_sleep": round(current_time - last_time, 2)})  # Round the time_sleep to 2 decimal places
            last_time = current_time
            if debug_mode:
                print("捕捉M:", "mouse_move_dxy", (x, 0), "MExec:", dx)
        elif key == keyboard.Key.right:
            x = mouse_val  # 200
            dx = int(x * 1295 / real_width)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, 0)  # 进行视角移动
            mouse_move_pos_list.append(
                {"mouse_move_dxy": (x, 0), "time_sleep": round(current_time - last_time, 2)})  # Round the time_sleep to 2 decimal places
            last_time = current_time
            if debug_mode:
                print("捕捉M:", "mouse_move_dxy", (x, 0), "MExec:", dx)
        if key == keyboard.Key.f9:
            save_mouse_move_by_key()
            save_json()
            if debug_mode:
                print("保存")
            return False


    def on_click(x, y, button, pressed):
        nonlocal mouse_watch, last_time
        if mouse_watch:
            save_mouse_move_by_key()
            if pressed:
                event_list.append(
                    {'key': 'click', 'time_sleep': round(time.time() - last_time, 2)})  # Round the time_sleep to 2 decimal places
                print("捕捉:", event_list[-1])
        else:
            pass

    def save_mouse_move_by_key():
        nonlocal mouse_move_pos_list
        if mouse_move_pos_list:
            element = None
            mouse_dx = 0
            mouse_dy = 0
            for element in mouse_move_pos_list:
                mouse_dx += element["mouse_move_dxy"][0]
                mouse_dy += element["mouse_move_dxy"][1]
            event_list.append(
                {"mouse_move_dxy": (mouse_dx, mouse_dy), "time_sleep": round(element["time_sleep"], 2)})  # Round the time_sleep to 2 decimal places
            # Round the time_sleep to 2 decimal places
            print("视角相对距离计算完成:", mouse_dx, mouse_dy,
                  round(element["time_sleep"], 2))
        mouse_move_pos_list.clear()

    def save_json():
        normal_save_dict = {
            "name": "地图-编号",
            "author": "作者",
            "start": [],
            "map": []
        }
        for element_save in event_list:
            if 'key' in element_save:
                if element_save['key'] == "click":
                    normal_save_dict["map"].append({"fighting": 2})
                elif element_save['key'] == "x":
                    normal_save_dict["map"].append({"fighting": 1})  # 进战斗
                elif element_save['key'] == "e":
                    normal_save_dict["map"].append({"e": 2})  # 黄泉E
                elif element_save['key'] == "f":
                    normal_save_dict["map"].append({"f": 15})  # F交互，默认15秒
                elif element_save['key'] == "v":
                    key_duration = element_save.get(
                        'duration', 1)  # 获取按键持续时间，默认为1秒
                    normal_save_dict["map"].append(
                        {"await": round(key_duration, 2)})  # 等待N秒
                else:
                    key_duration = element_save.get(
                        'duration', 1)  # 获取按键持续时间，默认为1秒
                    normal_save_dict["map"].append(
                        {element_save['key']: round(key_duration, 2)})  # Round the duration to 2 decimal places
            elif 'mouse_move_dxy' in element_save:
                normal_save_dict["map"].append(
                    {"mouse_move": round(element_save['mouse_move_dxy'][0], 2)})  # Round the mouse_move to 2 decimal places

        with open(f'output{datetime.now().strftime("%Y_%m_%d_%H_%M_%S")}.json', 'wb') as f:
            f.write(orjson.dumps(normal_save_dict, option=orjson.OPT_INDENT_2))

    mouse_listener = mouse.Listener(on_click=on_click)  # , on_move=on_move
    mouse_listener.start()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:  # 创建按键监听线程
        listener.join()  # 等待按键监听线程结束

    mouse_listener.stop()
