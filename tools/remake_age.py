import os
import re
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
p = None
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    if "age_data.xls" in files:
        cand = os.path.join(root, "age_data.xls")
        if p is None or len(cand) < len(p):
            p = cand
d = pd.read_excel(p)
print("  原始 %d 行 x %d 列" % (d.shape))
print("  全部列: %s" % [str(c)[:20] for c in d.columns])

# 只保留年龄段列（形如 "0 - 4" / "100+"），剔除日期与标识符
def is_age(c):
    s = str(c).strip()
    return bool(re.fullmatch(r"\d+\s*-\s*\d+", s)) or s.rstrip("+") == "100"

keep = [c for c in d.columns if is_age(c)]
print("  年龄段列 %d 个: %s" % (len(keep), [str(c) for c in keep][:6]))
out = d[keep].copy()
dst = os.path.join(HERE, "out", "data", "age_struct.xlsx")
out.to_excel(dst, index=False, sheet_name="Sheet1")
print("  写出 age_struct.xlsx: %d 行 x %d 列" % out.shape)