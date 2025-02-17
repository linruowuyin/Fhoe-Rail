import os
import pyautogui
from win32com import client
import time
import random
from .log import log

# 测试用
# all_titles = [win.title for win in pyautogui.getAllWindows()]
# print("当前所有窗口标题:", [t for t in all_titles if t.strip()])

def switch_window():
    lnk_started = False  # 添加一个标志，用于记录lnk文件是否已经启动
    
    while True:
        if not lnk_started:  # 如果lnk文件未启动，继续查找窗口
            def is_target_window(w):
                """智能窗口匹配规则"""
                # 精确匹配
                if w.title == '崩坏：星穹铁道':
                    return True
                # 模糊匹配网页
                if '云星穹铁道' in w.title.replace(' ', '').replace('·', ''):
                    return True
                return False

            all_windows = pyautogui.getAllWindows()
            for w in all_windows:
                if is_target_window(w):
                    log.info(f'激活窗口: {w.title}')
                    # client.Dispatch("WScript.Shell").SendKeys('%')  # 确保窗口可激活
                    try:
                        w.restore()  # 防止最小化状态
                        # w.maximize() # 最大化窗口确保可见
                        w.activate()
                        # 获取窗口的位置和尺寸
                        left, top, width, height = w.left, w.top, w.width, w.height
                        log.info(f'窗口位置和尺寸: {left}, {top}, {width}, {height}')

                        # 计算窗口中心坐标
                        center_x = left + width // 2
                        center_y = top + height // 2

                        # 移动鼠标到窗口中心
                        log.info(f'移动鼠标到窗口中心: {center_x}, {center_y}')
                        pyautogui.moveTo(center_x, center_y)
                        return
                    except Exception as e:
                        log.info(f'窗口激活失败: {e}')
                        continue
            log.debug(f'未找到目标窗口，已扫描{len(all_windows)}个窗口')
            log.debug('当前存在的窗口标题：')
            for w in pyautogui.getAllWindows():
                if w.title.strip():
                    log.debug(f' - "{w.title}"')
        
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
