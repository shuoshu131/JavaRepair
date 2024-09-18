import os
import requests
import csv
import re
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor

# GitHub access token 用于访问私有仓库
access_token = 'your_access_token_here'

# 本地存放所有仓库的目录
base_path1 = 'G:\\Repo'

# 输入的 CSV 文件路径
input_csv = "E:\\task\\JavaRepair\\1.csv"

# 输出的 CSV 文件路径
output_csv = "E:\\task\\JavaRepair\\a.csv"

# 定义正则表达式模式
single_line_comment_pattern = re.compile(r'^[+-]?\s*//')
multi_line_comment_start_pattern = re.compile(r'^[+-]?\s*/\*')
multi_line_comment_cont_pattern = re.compile(r'^[+-]?\s*\*')
empty_or_whitespace_pattern = re.compile(r'^\s*$')

def clone_repository(url, output_dir):
    """
    克隆指定的 Git 仓库到本地目录。
    如果仓库已经存在，则跳过克隆。
    """
    try:
        repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
        repo = re.search(r'[^/]+$', repository_name).group()
        repository_url = f"https://{access_token}@github.com/{repository_name}"

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
    """
    match = re.search(r'/commit/([^/#]+)', url)
    return match.group(1) if match else None

def test_finder(url):
    """
    检查指定的提交 URL 是否包含测试用例。
    """
    repository_name = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1)
    repo = re.search(r'[^/]+$', repository_name).group()
    os.chdir(os.path.join(base_path1, repo))
    commit_hash = extract_commit_hash(url)
    git_ls_tree = f'git ls-tree -r {commit_hash}'
    result = subprocess.run(['cmd', '/c', git_ls_tree], capture_output=True, text=True)
    return bool(result.stdout)

class DiffParser:
    def __init__(self, diff_output):
        """
        初始化 DiffParser 对象，解析 diff 输出。
        """
        self.lines = diff_output.splitlines(keepends=False)
        self.diff_output = diff_output

    def extract_functions(self, index):
        """
        向上查找直到找到 @@ 行，提取附近的函数定义。
        """
        func_pattern = re.compile(r'^\s*(?:public|private|protected|static|final|synchronized|abstract|native)?'
                                  r'\s*(?:static)?\s*[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(throws\s+\w+(?:\s*,\s*\w+)*)?\s*{')
        for i in range(index, 0, -1):
            line = self.lines[i].strip()
            if line.startswith('@@'):
                print(f"Found @@ line: {line}")
                break
            match = func_pattern.match(line)
            if match:
                function_name = f"{match.group(1)}({match.group(2)})"
                return function_name
        return None

    def parse_hunk(self):
        """
        解析并统计 Hunk 的数量。Hunk 是指 diff 中的修改块。
        """
        hunk = 0
        pointer = -1
        functions = []
        default_functions = None
        func_pattern = re.compile(r'^\s*(?:public|private|protected|static|final|synchronized|abstract|native)?'
                                  r'\s*(?:static)?\s*[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(throws\s+\w+(?:\s*,\s*\w+)*)?\s*{')

        for index, line in enumerate(self.lines, start=1):
            if line.startswith('@@'):
                match = re.search(func_pattern, line)
                if match:
                    default_functions = f"{match.group(1)}({match.group(2)})"
                continue
            
            # 处理代码行中的注释和多行注释
            if line.find('*/') != -1 and is_comment == 1:
                is_comment = 0
                continue

            if line.startswith("diff"):
                continue  # 跳过文件路径行
            
            # 处理修改行（+/-开头的行）
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                if bool(empty_or_whitespace_pattern.match(line[1:])) or single_line_comment_pattern.match(line):
                    continue

                if multi_line_comment_start_pattern.match(line):
                    is_comment = 1
                    continue

                # 更新 Hunk 数量
                if pointer == -1:
                    pointer = index
                    hunk += 1
                    if default_functions:
                        functions.append(default_functions)
                elif index != pointer + 1:
                    hunk += 1
                    if default_functions:
                        functions.append(default_functions)
                    pointer = index

        print(f"Hunk Count: {hunk}, Functions: {functions}")
        return hunk, functions

    def parse_file(self):
        """
        解析 diff 输出，统计文件数量、Java 文件数量和测试用例文件数量。
        """
        file = 0
        java_file = 0
        is_test_case = 0

        for line in self.lines:
            if line.startswith("diff"):
                file += 1
                if line.endswith(".java"):
                    java_file += 1
                if "test" in line.lower():
                    is_test_case = 1

        return file, java_file, is_test_case

def get_commit_subject(commit_hash, repo_path):
    """
    获取指定提交的主题信息。
    """
    path_str = os.path.join(base_path1, repo_path)
    command = ["git", "-C", path_str, "show", "--format=%s", "-s", commit_hash]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return result.stdout.strip()
    else:
        print("Failed to get commit subject")
        return None

if __name__ == '__main__':
    max_workers = 5

    # 读取输入的 CSV 文件
    with open(input_csv) as csvfile:
        reader = csv.reader(csvfile)
        urls = [row[3] for row in reader]

    # 输出 CSV 文件初始化
    with open(output_csv, 'w') as f:
        f.write("url,repo,file,java_file,func,hunk,test,note\n")

    # 分析每个仓库的提交记录
    for url in urls:
        try:
            commit_hash = extract_commit_hash(url)
            repo = re.search(r'/([^/]+/[^/]+)/commit/', url).group(1).split('/')[-1]
            note = get_commit_subject(commit_hash, repo)
            os.chdir(os.path.join(base_path1, repo))
            diff_command = f'git diff {commit_hash}^..{commit_hash}'
            diff_output = subprocess.run(['pwsh', '-Command', diff_command], capture_output=True, text=True, encoding='utf-8').stdout

            if not diff_output:
                diff_url = url + '.diff'
                diff_output = requests.get(diff_url).text

            parser = DiffParser(diff_output)
            file, java_file, test_in_commit = parser.parse_file()
            hunk, functions = parser.parse_hunk()

            with open(output_csv, 'a') as f:
                f.write(f"{url},{repo},{file},{java_file},{functions},{hunk},{test_in_commit},{note}\n")

        except Exception as e:
            print(f"Error processing {url}: {e}")
