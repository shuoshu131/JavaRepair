import subprocess
from rs import  DiffParser
import os

#D:\linshi_zancun_repo\pgjdbc     06abfb78a627277a580d4df825f210e96a4e14ee
#D:\linshi_zancun_repo\spring-security` 5b293d21161e946bf241d9e974b9af93cfafaaac
#D:\linshi_zancun_repo\jodd    9bffc3913aeb8472c11bb543243004b4b4376f16
#D:\linshi_zancun_repo\jackson-databind           3ccde7d938fea547e598fdefe9a82cff37fed5cb
#D:\linshi_zancun_repo\opencast  32bfbe5f78e214e2d589f92050228b91d704758e
#D:\linshi_zancun_repo\plantuml    fbe7fa3b25b4c887d83927cffb1009ec6cb8ab1e



#dir选填
dir="D:\linshi_zancun_repo\plantuml"
os.chdir(dir)

#hash选填
commit_hash = "fbe7fa3b25b4c887d83927cffb1009ec6cb8ab1e"
diff_command = f'git diff {commit_hash}^..{commit_hash}'  # 注意添加了空格
diff_output = subprocess.run(['powershell', '-Command', diff_command], capture_output=True, text=True, encoding='utf-8').stdout
parser = DiffParser(diff_output)
file, java_file, test_in_commit = parser.parse_file()
hunk, functions = parser.parse_hunk()
print(f"file: {file}, java_file: {java_file}, test_in_commit: {test_in_commit}, hunk: {hunk}, functions: {functions}")
