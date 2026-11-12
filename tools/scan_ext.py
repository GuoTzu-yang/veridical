import json
import os
import warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
used = set()
for c in cfg.values():
    used.add(os.path.basename(c.get("data", "")))
print("  runs.json 已用:", sorted(used))
print()
# 列 external 下所有数据文件
allf = []
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if f.lower().endswith((".xlsx", ".xls", ".csv")):
            allf.append(os.path.join(root, f))
print("  external 下数据文件共 %d 个" % len(allf))