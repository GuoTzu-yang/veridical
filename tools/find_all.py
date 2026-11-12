import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
# 上一轮筛出的候选（数值列 >=3、行数 >=20），排除重复副本与结果文件
WANT = ("Problem C - Most Recent Cohort", "population_data.xls",
        "age_data.xls", "life_expectancy_0_data.xls",
        "birth_rate_data.xls", "hiv_aids_data.xls",
        "fertility_data.xls", "MCM_NFLIS_Data.xlsx",
        "microwave.tsv", "pacifier.tsv", "hair_dryer.tsv")
found = {}
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        for w in WANT:
            if f == w or (w in f and f.endswith((".xls", ".xlsx", ".tsv"))):
                if w not in found or len(os.path.join(root, f)) < len(found[w]):
                    found[w] = os.path.join(root, f)
print("  找到 %d / %d" % (len(found), len(WANT)))
for w in WANT:
    p = found.get(w)
    print("    %-34s %s" % (w, "OK" if p else "缺"))