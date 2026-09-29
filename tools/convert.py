import os
import json
import sys

# 系统语言兼容（issue #428 同类问题）：日文系统 cp932 代码页下中文 print 会崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass

def find_json_files_with_character(directory, character):
    json_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))

    found_files = []
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = f.read()
            if character in data:
                found_files.append(json_file)

    return found_files

def load_dumps_map():
    """取地图写盘用的序列化器（CLAUDE.md R22）。

    按路径运行时 sys.path[0] 是 tools/ 而不是仓库根，所以要显式补上；补 sys.path
    是模块级副作用，会被 tests/test_architecture.py 的棘轮拦下，所以和
    tools/validate_maps.py 一样放在函数里。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from utils.core.json_io import dumps_map

    return dumps_map


def replace_word_in_json_files(files, original_word, replacement_word):
    dumps_map = load_dumps_map()
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with open(file, 'w', encoding='utf-8') as f:
            # 替换发生在整段文本上，所以要先按规范序列化再 replace
            f.write(dumps_map(data).replace(original_word, replacement_word))

if __name__ == "__main__":
    search_character = input("请输入旧字段：")
    replace_character = input("请输入新字段：")
    
    current_directory = os.path.dirname(os.path.abspath(__file__))
    parent_directory = os.path.dirname(current_directory)  # 获取上一级目录的路径
    
    result = find_json_files_with_character(parent_directory, search_character)

    if result:
        print(f"包含字段 '{search_character}' 的JSON文件有：")
        for file_path in result:
            print(os.path.basename(file_path))
        
        confirmation = input("是否要替换字段？(Y/N): ").strip().lower()
        if confirmation == 'y':
            replace_word_in_json_files(result, search_character, replace_character)
            print(f"已将所有包含字段 '{search_character}' 的JSON文件中的 '{search_character}' 替换为 '{replace_character}'。")
        else:
            print("未进行替换操作。")
    else:
        print(f"在当前目录的上一级目录下没有找到包含字段 '{search_character}' 的JSON文件。")
