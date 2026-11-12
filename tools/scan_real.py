import os
import pandas as pd

ROOT = "external/github/jihe520__MathModelAgent/backend/app/example"
CASES = [
    ("2023华数杯C题", os.path.join(ROOT, "example", "2023华数杯C题", "附件.xlsx")),
    ("sample_data", os.path.join(ROOT, "sample_data", "附件.xlsx")),
    ("2024高教杯C题-2", os.path.join(ROOT, "example", "2024高教杯C题", "附件2.xlsx")),
]
for nm, p in CASES:
    if not os.path.exists(p):
        print("  %s: 缺文件" % nm)
        continue
    try:
        xl = pd.ExcelFile(p)
        print("  === %s ===  表: %s" % (nm, xl.sheet_names))
        for sh in xl.sheet_names:
            d = xl.parse(sh)
            num = [c for c in d.columns
                   if pd.api.types.is_numeric_dtype(d[c])]
            if len(num) >= 3:
                print("    [%s] %dx%d  数值列 %d: %s"
                      % (sh, d.shape[0], d.shape[1], len(num), num[:7]))
    except Exception as e:
        print("  %s: %s: %s" % (nm, type(e).__name__, str(e)[:60]))