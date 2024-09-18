import os
import requests
import csv
import re
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor

# GitHub access token 用于访问私有仓库
access_token = ''

# 本地存放所有仓库的目录
base_path1 = '/Users/mac/Documents/repo'

# 输入的 CSV 文件路径
input_csv = "/Users/mac/Documents/JavaRepair/1.csv"

# 输出的 CSV 文件路径
output_csv = "/Users/mac/Documents/JavaRepair/a.csv"

# 定义正则表达式模式
single_line_comment_pattern = re.compile(r'^[+-]?\s*//')
multi_line_comment_start_pattern = re.compile(r'^[+-]?\s*/\*')
multi_line_comment_cont_pattern = re.compile(r'^[+-]?\s*\*')
empty_or_whitespace_pattern = re.compile(r'^\s*$')

def clone_repository(url, output_dir):
    """
    克隆指定的 Git 仓库到本地目录。
    
    参数:
    - url: Git 仓库的 URL。
    - output_dir: 克隆到本地的目录。

    如果仓库已经存在，则跳过克隆。
    """
    try:
        repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
        repo = re.search(r'[^/]+$', repository_name).group()
        repository_url = f"https://{access_token}@github.com/{repository_name}"
        print(repo)

        if os.path.exists(os.path.join(output_dir, repo)):
            print(f"Repository {repo} already exists, skipping...")
            return

        subprocess.run(["git", "clone", repository_url], check=True)
        print(f"Successfully cloned {url}")
        time.sleep(2)

    except Exception as e:
        print(f"Error cloning {url}: {e}")

def extract_commit_hash(url):
    """
    从给定的 URL 提取提交哈希值。

    参数:
    - url: 包含提交哈希的 URL。

    返回:
    - 提交哈希值（如果存在），否则返回 None。
    """
    match = re.search(r'/commit/([^/#]+)', url)
    return match.group(1) if match else None

def test_finder(url):
    """
    检查指定的提交 URL 是否包含测试用例。

    参数:
    - url: 包含提交信息的 URL。

    返回:
    - 如果提交包含测试用例，则返回 True；否则返回 False。
    """
    repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
    repo = re.search(r'[^/]+$', repository_name).group()
    os.chdir(os.path.join(base_path1, repo))
    commit_hash = extract_commit_hash(url)
    git_ls_tree = f'git ls-tree -r {commit_hash}'
    result = subprocess.run(['zsh', '/c', git_ls_tree], capture_output=True, text=True)
    return bool(result.stdout)

class DiffParser:
    def __init__(self, diff_output):
        """
        初始化 DiffParser 对象，解析 diff 输出。

        参数:
        - diff_output: git diff 命令的输出。
        """
        self.lines = diff_output.splitlines(keepends=False)
        self.diff_output = diff_output
        
    def extract_functions(self, index):
        """
        向上查找直到找到 @@ 行，提取附近的函数定义。

        参数:
        - index: 当前行的索引。

        返回:
        - 找到的函数名或 None。
        """
        func_pattern = re.compile(r'^\s*(?:public|private|protected|static|final|synchronized|abstract|native)?'
                                  r'\s*(?:static)?\s*[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(throws\s+\w+(?:\s*,\s*\w+)*)?\s*{')

        # 从当前行向上查找，直到找到 @@ 行
        for i in range(index, 0, -1):
            line = self.lines[i].strip()
            if line.startswith('@@'):
                print(f"Found @@ line: {line}")
                break  # 找到 @@ 行时，停止查找
            match = func_pattern.match(line)
            if match:
                function_name = f"{match.group(1)}({match.group(2)})"
                return function_name

        return None
    
    def parse_hunk(self):
        """
        解析并统计 Hunk 的数量。Hunk 是指 diff 中的修改块。

        返回:
        - hunk: Hunk 的数量。 function: 函数名集合。
        """
        pointer = -1  # 指针，用于记录行索引
        hunk = 0  # Hunk 的数量
        is_in_hunk = 0  # 标志位，表示是否在 Hunk 中
        is_comment = 0  # 标志位，表示是否在注释中
        is_test_case = 0  # 标志位，表示是否为测试用例文件
        is_java_file = 1 # 标志位，表示是否为 Java 文件
        functions = []  # 函数名集合
        func_pattern = re.compile(r'^\s*(?:public|private|protected|static|final|synchronized|abstract|native)?'
                                  r'\s*(?:static)?\s*[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(throws\s+\w+(?:\s*,\s*\w+)*)?\s*{')

        for index, line in enumerate(self.lines, start=1):
            # print(line)
            if line.startswith('@@'):
                match = re.search(func_pattern, line)
                if match:
                    function_name = f"{match.group(1)}({match.group(2)})"
                    default_functions = function_name
                    print("default_functions:", default_functions)
                    is_first_func = 1
                else:
                    default_functions = None
                    is_first_func = 1
                is_in_hunk = 0  # 重置 Hunk 标志位
                is_comment = 0  # 重置注释标志位
                continue
            # 结束多行注释
            if line.find('*/') != -1 and is_comment == 1:
                is_comment = 0  # 注释结束
                if is_in_hunk == 1:
                    pointer = index
                continue

            if is_comment == 1:
                if is_in_hunk == 1:
                    pointer = index
                continue

            if line.startswith("diff"):
                is_test_case = 0  # 重置测试用例标志位
                is_java_file = 0  # 重置 Java 文件标志位
                test_pattern = "^diff --git.*[Tt][Ee][Ss][Tt].*$"
                test_ans = re.search(test_pattern, line)
                if test_ans:
                    is_test_case = 1
                java_pattern = r"^diff --git.*\.java$"
                java_ans = re.search(java_pattern, line)
                if java_ans:
                    is_java_file = 1
            if is_test_case == 1:
                continue
            if is_java_file == 0:
                continue

            # 处理修改行（+/-开头的行）
            #如果行中没有找到import，认为是代码行
            if line.find("import") == -1:
                if line[0] == '-' or line[0] == "+":
                    if any(line.startswith(ignore) for ignore in ["+++", "---"]):
                        #说明开头为+++或者---，跳过
                        continue


                    #从此往后就是以+或者-开头的修改行
                    if bool(empty_or_whitespace_pattern.match(line[1:])) or single_line_comment_pattern.match(line):
                        pointer = index
                        continue


                    #处理多行注释
                    if multi_line_comment_start_pattern.match(line):
                        is_comment = 1
                        pointer = index
                        continue
                    is_in_hunk = 1


                    if pointer == -1:
                        pointer = index
                        hunk += 1
                        if default_functions is not None and is_first_func:
                            functions.append(default_functions)
                            is_first_func = 0
                        elif not is_first_func:
                            function = None
                            # 倒查diff至找到函数,返回值为函数名
                            function = self.extract_functions(index)
                            if default_functions is None and function is None:
                                # 认为找不到hunk对应的函数，跳过
                                continue
                            elif default_functions is not None and function is None:
                                # 未找到函数，使用默认函数名
                                functions.append(default_functions)
                        print("hunk:", hunk)
                        print("line:", line)
                    else:
                        if index == (pointer + 1):
                            is_in_hunk=1
                            pointer = index
                        else:
                            if is_in_hunk == 1:
                                pointer = index
                            hunk += 1
                            if default_functions is not None and is_first_func:
                                functions.append(default_functions)
                                is_first_func = 0
                            elif not is_first_func:
                                function = None
                                # 倒查diff至找到函数,返回值为函数名
                                function = self.extract_functions(index)
                                if default_functions is None and function is None:
                                    # 认为找不到hunk对应的函数，跳过
                                    continue
                                elif default_functions is not None and function is None:
                                    # 未找到函数，使用默认函数名
                                    functions.append(default_functions)
                            print("hunk:", hunk)
                            print("line:", line)
                else:
                    is_in_hunk = 0
        # if is_in_hunk == 1:
        #     hunk += 1
        print(hunk)
        print(functions)
        return hunk, functions



    def parse_file(self):
        """
        解析 diff 输出，统计文件数量、Java 文件数量和测试用例文件数量。

        返回:
        - file: 总文件数量
        - java_file: Java 文件数量
        - test_in_commit: 是否包含测试用例
        """
        file = 0
        java_file = 0
        is_test_case = 0
        test_in_commit = 0

        for line in self.lines:
            if line.startswith("diff"):
                is_test_case = 0
                pattern = "^diff --git.*[Tt][Ee][Ss][Tt].*$"
                if re.search(pattern, line):
                    is_test_case = 1
            if is_test_case == 1:
                test_in_commit = 1
                continue
            if line.startswith("diff"):
                file += 1
                if line.endswith(".java"):
                    java_file += 1

        print("[java_file]:", java_file)
        print("[file]:", file)
        print("[test_in_commit]:", test_in_commit)
        return file, java_file, test_in_commit
    
    # def extract_diff_file_and_lines(self):
    #     """
    #     从 diff 输出中提取 Java 文件及其修改的行号范围。

    #     返回:
    #     - files_and_ranges: 包含 Java 文件路径和行号范围的字典。
    #     """
    #     files_and_ranges = {}  # 存储 Java 文件路径和行号范围
    #     current_file = None  # 当前文件路径
    #     is_java_file = False  # 当前文件是否为 Java 文件

    #     for line in self.lines:
    #         if line.startswith('diff --git'):
    #             match = re.search(r'diff --git a/(.*?) b/\1', line)
    #             if match:
    #                 current_file = match.group(1)
    #                 is_java_file = current_file.endswith('.java')
    #                 if is_java_file:
    #                     files_and_ranges[current_file] = []
    #                 else:
    #                     current_file = None

    #         elif line.startswith('@@') and current_file and is_java_file:
    #             hunk_header = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
    #             if hunk_header:
    #                 start_line = int(hunk_header.group(1))
    #                 line_count = int(hunk_header.group(2)) if hunk_header.group(2) else 1
    #                 end_line = start_line + line_count - 1
    #                 files_and_ranges[current_file].append((start_line, end_line))

    #     return files_and_ranges

    # def extract_functions_from_file(self, file_path, start_line, end_line):
    #     """
    #     从 Java 文件中提取函数名。

    #     参数:
    #     - file_path: 文件路径。
    #     - start_line: 起始行号。
    #     - end_line: 结束行号。

    #     返回:
    #     - functions: 提取的函数名列表。
    #     """
    #     functions = []
    #     func_pattern = re.compile(r'^\s*(public|private|protected)?\s*(static)?\s*[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(throws\s+\w+(?:\s*,\s*\w+)*)?\s*{')

    #     try:
    #         with open(file_path, 'r', encoding='utf-8') as file:
    #             lines = file.readlines()
                
    #             # 向前遍历直到第一个函数定义
    #             found_function = False
    #             i = start_line - 1
    #             while i >= 0:
    #                 line = lines[i].strip()
    #                 match = func_pattern.match(line)
    #                 if match:
    #                     function_name = f"{match.group(3)}({match.group(4)})"
    #                     functions.append(function_name)
    #                     found_function = True
    #                     break
    #                 i -= 1

    #             # 遍历修改的行号范围
    #             for i in range(start_line - 1, min(end_line, len(lines))):
    #                 line = lines[i].strip()
    #                 match = func_pattern.match(line)
    #                 if match:
    #                     function_name = f"{match.group(3)}({match.group(4)})"
    #                     functions.append(function_name)

    #     except FileNotFoundError:
    #         print(f"File {file_path} not found.")
    #     except Exception as e:
    #         print(f"Error reading file {file_path}: {e}")

    #     return functions

    # def extract_functions(self):
    #     """
    #     从 diff 输出中提取修改的函数名。

    #     返回:
    #     - modified_functions: 修改的函数名列表。
    #     """
    #     modified_functions = [] # 存储修改的函数名
    #     files_and_ranges = self.extract_diff_file_and_lines() # 提取 Java 文件及其修改的行号范围

    #     for file_path, ranges in files_and_ranges.items(): # 遍历文件及其修改的行号范围
    #         full_file_path = os.path.join(base_path1, repo, file_path) # 获取文件的完整路径

    #         for start_line, end_line in ranges: # 遍历修改的行号范围
    #             functions_in_range = self.extract_functions_from_file(full_file_path, start_line, end_line) # 提取函数名
    #             modified_functions.extend(functions_in_range) # 添加到列表
    #     print(modified_functions) # 打印修改的函数名列表
    #     return modified_functions # 返回修改的函数名列表

def get_commit_subject(commit_hash, repo_path):
    """
    获取指定提交的主题信息。

    参数:
    - commit_hash: 提交的哈希值。
    - repo_path: 仓库路径。

    返回:
    - 提交主题（如果获取成功），否则返回 None。
    """
    path_str = os.path.join(base_path1, repo_path)
    command = ["git", "-C", path_str, "show", "--format=%s", "-s", commit_hash]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return result.stdout.strip()
    else:
        print("Failed to get commit subject")
        print("Error:", result.stderr)
        return None

if __name__ == '__main__':
    max_workers = 5

    # 读取输入的 CSV 文件，获取所有的仓库 URL
    with open(input_csv) as csvfile:
        reader = csv.reader(csvfile)
        urls = [row[3] for row in reader]

    # 克隆所有仓库
    # os.chdir(base_path1)
    # with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #     for url in urls:
    #         executor.submit(clone_repository, url, base_path1)

    # 输出 CSV 文件初始化
    with open(output_csv, 'w') as f:
        f.write("url,repo,file,java_file,func,hunk,test,note\n")

    # 分析每个仓库的提交记录
    for url in urls:
        try:
            commit_hash = extract_commit_hash(url)
            repo = repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
            repo = re.search(r'[^/]+$', repository_name).group()
            note = get_commit_subject(commit_hash, repo)
            os.chdir(os.path.join(base_path1, repo))
            diff_command = f'git diff {commit_hash}^..{commit_hash}'  # 注意添加了空格
            diff_output = subprocess.run(['zsh', '-Command', diff_command], capture_output=True, text=True, encoding='utf-8').stdout
            print(diff_command)
            if len(diff_output) < 1:
                print("the repo local is bad")
                diff_url = url + '.diff'
                res = requests.get(diff_url).text
                if res is not None:
                    # print("it is solved")
                    diff_output = res
            parser = DiffParser(diff_output)
            with open(output_csv, 'a') as f:
                file, java_file, test_in_commit = parser.parse_file()
                result = parser.parse_hunk()
                hunk, functions = parser.parse_hunk()

                string = "URL: {}   Repo: {}   file: {}   java_file: {}   functions: {}   hunk: {}\n".format(url, repo, file, java_file, functions, hunk)
                test_in_repo = 0
                if test_in_commit == 0:
                    if test_finder(url):
                        test_in_repo = 1

                string = "{},{},{},{},{},{},{},{}\n".format(url, repository_name, file, java_file, len(functions), hunk, test_in_commit | test_in_repo, note)
                f.write(string)
                print(string)
        except Exception as e:
            print(f"Error processing {url}: {e}")
            continue
