import csv

# 需要查询的CVE集合
cve_set = {
    'CVE-2023-46227', 'CVE-2023-3432', 'CVE-2023-20860', 'CVE-2023-3431', 
    'CVE-2022-4137', 'CVE-2021-29506', 'CVE-2023-20873', 'CVE-2018-1002201', 
    'CVE-2023-46502', 'CVE-2018-8088', 'CVE-2016-15026', 'CVE-2023-36820', 
    'CVE-2018-12418', 'CVE-2022-25914', 'CVE-2023-20861', 'CVE-2023-46120', 
    'CVE-2021-23900', 'CVE-2019-0224', 'CVE-2023-25753', 'CVE-2023-2422', 
    'CVE-2023-43642', 'CVE-2021-20202', 'CVE-2023-45669', 'CVE-2022-23596', 
    'CVE-2022-3510', 'CVE-2023-4218', 'CVE-2022-3509', 'CVE-2022-31194'
}

# 读取多个CSV文件，筛选出符合条件的CVE信息
def extract_cve_info(csv_files, output_csv):
    cve_rows = []
    for file in csv_files:
        with open(file, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if row[0] in cve_set:
                    cve_rows.append({
                        'CVE_ID': row[0],
                        'Project': row[1],
                        'Affected_Version': row[2],
                        'Link': row[3]
                    })
    
    # 将筛选结果写入到新的CSV文件
    with open(output_csv, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['CVE_ID', 'Project', 'Affected_Version', 'Link'])
        writer.writeheader()
        writer.writerows(cve_rows)

# 输入的多个CSV文件路径
csv_files = ['output_1.csv', 'output_2.csv', 'output_3.csv', 'output_4.csv']
output_csv = 'output.csv'  # 输出文件路径

# 调用函数提取并生成新的表格
extract_cve_info(csv_files, output_csv)

print(f'已生成新的CVE表格，保存到 {output_csv}')
