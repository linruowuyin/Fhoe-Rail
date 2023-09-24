import os
import subprocess
import time

def find_requirements_file():
    # 尝试在当前目录查找requirements.txt
    current_dir = os.path.dirname(__file__)
    requirements_file = os.path.join(current_dir, "requirements.txt")
    if os.path.exists(requirements_file):
        return requirements_file

    # 如果在当前目录中找不到，尝试在上一级目录查找
    parent_dir = os.path.dirname(current_dir)
    requirements_file = os.path.join(parent_dir, "requirements.txt")
    if os.path.exists(requirements_file):
        return requirements_file

    # 如果都找不到，返回None
    return None

def test_speed(source):
    try:
        start_time = time.time()
        subprocess.check_call(["ping", "-n", "5", source])
        end_time = time.time()
        return end_time - start_time
    except subprocess.CalledProcessError:
        return float('inf')  # 返回无穷大表示测试失败

def set_fastest_proxy():
    aliyun_time = test_speed("mirrors.aliyun.com")
    tuna_time = test_speed("pypi.tuna.tsinghua.edu.cn")

    if aliyun_time < tuna_time:
        print("阿里云源延迟较低，设置为代理源...")
        subprocess.check_call(["pip", "config", "set", "global.index-url", "https://mirrors.aliyun.com/pypi/simple"])
    else:
        print("上海交通大学源延迟较低，设置为代理源...")
        subprocess.check_call(["pip", "config", "set", "global.index-url", "https://pypi.tuna.tsinghua.edu.cn/simple"])

def check_and_install_dependencies():
    requirements_file = find_requirements_file()

    if requirements_file:
        try:
            subprocess.check_call(["pip", "show", "-r", requirements_file])
            print("依赖已经存在！")
        except subprocess.CalledProcessError:
            print("安装依赖中，请稍等...")
            set_fastest_proxy()
            subprocess.check_call(["pip", "install", "-r", requirements_file])
            subprocess.check_call(["pip", "config", "unset", "global.index-url"])  # 恢复默认源
            print("安装完成！")
    else:
        print("无法找到requirements.txt文件！")

if __name__ == "__main__":
    check_and_install_dependencies()
