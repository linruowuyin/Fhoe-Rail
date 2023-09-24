import os
import pyautogui
from win32com import client
import time
import random

def switch_window(title='崩坏：星穹铁道'):
    lnk_started = False  # 添加一个标志，用于记录lnk文件是否已经启动
    
    while True:
        if not lnk_started:  # 如果lnk文件未启动，继续查找窗口
            ws = pyautogui.getWindowsWithTitle(title)

            if len(ws) >= 1:
                for w in ws:
                    # 避免其他窗口也包含崩坏：星穹铁道，比如正好开着github脚本页面
                    # print(w.title)
                    if w.title == title:
                        client.Dispatch("WScript.Shell").SendKeys('%')
                        w.activate()
                        return  # 找到窗口后直接返回函数

            print(f'没有找到窗口【{title}】')
        
        # 尝试查找并启动lnk文件
        lnk_files = find_lnk_files("./map")  # 指定lnk文件所在的目录
        if len(lnk_files) == 1 and not lnk_started:
            start_lnk_file(lnk_files[0])
            print("程序启动成功！")
            lnk_started = True  # 设置标志为True
            time.sleep(25)  # 等待25秒
            
            end_time = time.time() + 30  # 执行点击操作的总时间为30秒
            last_5_seconds = end_time - 5  # 最后5秒
            
            while time.time() < end_time:
                if time.time() >= last_5_seconds:
                    # 在最后5秒内至少点击5次
                    for _ in range(5):
                        x, y = (1167, 732)  # 修改点击坐标为(1167, 732)
                        pyautogui.click(x, y)
                        time.sleep(random.uniform(0.1, 5))  # 随机点击频率
                else:
                    x, y = (1167, 732)  # 修改点击坐标为(1167, 732)
                    pyautogui.click(x, y)
                    time.sleep(random.uniform(0.1, 5))  # 随机点击频率
        
        if lnk_started:
            # 如果lnk文件已经启动成功，不再等待用户按下回车键，直接退出
            return

        # 等待用户按下回车键后继续
        input("按下回车键继续查找窗口...")

def find_lnk_files(folder_path):
    lnk_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.lnk'):
                lnk_files.append(os.path.join(root, file))
    return lnk_files

def start_lnk_file(lnk_path):
    os.system(f'start "" "{lnk_path}"')

if __name__ == '__main__':
    switch_window()
