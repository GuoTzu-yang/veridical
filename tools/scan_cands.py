import json
import os
import warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
used = {os.path.basename(c.get("data") or "") for c in cfg.values()}
# out/data 下已转成 xlsx 的
outd = os.path.join(HERE, "out", "data")
used |= set(os.listdir(outd)) if os.path.isdir(outd) else set()

allf = []
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if f.lower().endswith((".xlsx", ".xls", ".csv")):
            allf.append(os.path.join(root, f))
print("  external 下 %d 个数据文件" % len(allf))
print()
import pandas as pd
cands = []
for p in allf:
    b = os.path.basename(p)
    if b in used:
        continue
    try:
        if p.lower().endswith(".csv"):
            d = pd.read_csv(p, nrows=200)
        else:
            d = pd.read_excel(p, nrows=200)
    except Exception as e:
        cands.append((b, "读取失败: %s" % type(e).__name__, 0, 0, p))
        continue
    num = d.select_dtypes("number")
    cands.append((b, "", d.shape[0], num.shape[1], p))
cands.sort(key=lambda x: -x[3])
print("  未使用的（按数值列数排序，前 22 个）：")
for b, err, r, nc, p in cands[:22]:
    tag = " %s" % err if err else ""
    print("    %-46s %5d行 %2d数值列%s" % (b[:46], r, nc, tag))