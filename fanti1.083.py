import opencc
import re
import concurrent.futures
import os
from collections import defaultdict, OrderedDict
import threading
from tqdm import tqdm  # 导入tqdm库


# 遍历并修改，测试版。稳定版是1.065和1.081

def has_simplified_chinese(content):
    simplified_chars = set(re.findall(r'[\u4e00-\u9fa5]', content))
    return len(simplified_chars) > 0


def is_traditional_chinese_char(char, cc):
    converted_char = cc.convert(char)
    return char != converted_char


def process_line(file_path, line_num, char_list, cc, results, suggestions, printed_lines, lock):
    for index, char in enumerate(char_list):
        if is_traditional_chinese_char(char, cc):
            line_content = ''.join(char_list)
            key = (file_path, line_num, line_content)
            if line_num not in printed_lines[file_path]:
                results.append(key)
                printed_lines[file_path].add(line_num)
            suggestion = cc.convert(char)
            suggestions[key].add((suggestion, index))

            with lock:
                with open(file_path, 'r+', encoding='utf-8') as file:
                    lines = file.readlines()
                    line_to_modify = lines[line_num - 1]
                    line_to_modify = line_to_modify[:index] + suggestion + line_to_modify[index + 1:]
                    lines[line_num - 1] = line_to_modify
                    file.seek(0)
                    file.writelines(lines)
                    file.truncate()


def find_non_traditional_chinese_characters_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    has_simplified = has_simplified_chinese(content)
    if not has_simplified:
        return 0, 0, 0, 0  # No need to modify, return 0

    cc = opencc.OpenCC('s2t')
    lines = content.splitlines()

    results = []
    suggestions = defaultdict(set)
    printed_lines = defaultdict(set)
    lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        char_lists = [list(line) for line in lines]
        future_to_line_num = {
            executor.submit(process_line, file_path, line_num + 1, char_list, cc, results, suggestions, printed_lines,
                            lock): line_num + 1 for line_num, char_list in enumerate(char_lists)}
        for future in tqdm(concurrent.futures.as_completed(future_to_line_num), total=len(char_lists),
                           desc=f"处理文件 '{file_path}'", ncols=100, dynamic_ncols=True):
            line_num = future_to_line_num[future]
            try:
                future.result()
            except Exception as exc:
                print(f"处理文件 '{file_path}' 第 {line_num} 行时发生异常：{exc}")

    max_line_num_width = len(str(len(lines)))
    ordered_results = OrderedDict()
    for file_path, line_num, line_content in results:
        key = (file_path, line_num, line_content)
        suggestions_for_line = suggestions[key]
        if suggestions_for_line:
            suggestions_for_line = sorted(suggestions_for_line, key=lambda x: x[1])
            suggestions_str = ", ".join(suggestion for suggestion, _ in suggestions_for_line)
            line_info = f"文件 '{file_path}', 第 {line_num:>{max_line_num_width}} 行：{line_content} 建议替换为繁体中文：{suggestions_str}"
            ordered_results[key] = line_info

    total_chars = sum(len(suggestions_for_line) for suggestions_for_line in suggestions.values())
    total_files = len(set(file_path for file_path, _, _ in results))
    total_chars_modified = total_chars if total_chars > 0 else 0
    total_files_modified = 1 if total_chars > 0 else 0

    return total_chars, total_files, total_chars_modified, total_files_modified


def find_non_traditional_chinese_characters_in_directory(directory, file_types_to_process):
    total_chars = 0
    total_files = 0
    total_chars_modified = 0
    total_files_modified = 0
    processed_files = set()

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if any(file_path.lower().endswith(file_type) for file_type in file_types_to_process):
                chars, files_count, chars_modified, files_modified = find_non_traditional_chinese_characters_in_file(
                    file_path)
                total_chars += chars
                total_files += files_count
                total_chars_modified += chars_modified
                total_files_modified += files_modified
                processed_files.add(file_path)

                if chars == 0:
                    print(f"文件 '{file_path}' 中不包含简体中文。")

    print(f"\n总计发现 {total_chars} 个字需要修改，涉及 {total_files} 个文件。")
    print(f"总计修改 {total_chars_modified} 个字，涉及 {total_files_modified} 个文件。")
    print("已处理文件：")
    for file_path in processed_files:
        print(file_path)
    print(f"处理完成，By DW")


if __name__ == "__main__":
    print(f"开始检测简体中文")
    directory_path = r"D:\Work\bac\新建文件夹\新建文件夹\pages"  # 替换成你的文件夹路径
    file_types = [".vue", ".txt"]  # 添加更多文件类型
    find_non_traditional_chinese_characters_in_directory(directory_path, file_types)
