import os
import pandas as pd

ROOT = os.path.join("external", "github", "jihe520__MathModelAgent",
                    "backend", "app", "example", "example")

# ① 2024 高教杯 C 题：两张表，数值列少
p = os.path.join(ROOT, "2024高教杯C题", "附件2.xlsx")
print("=== 2024高教杯C题 附件2 ===")
xl = pd.ExcelFile(p)
for sh in xl.sheet_names:
    d = xl.parse(sh)
    num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    print("  [%s] %dx%d  数值列 %d: %s"
          % (sh, d.shape[0], d.shape[1], len(num), num))

# ② 2025 五一杯 C 题：13 MB CSV
p2 = os.path.join(ROOT, "2025五一杯C题", "附件2 (Attachment 2).csv")
print()
print("=== 2025五一杯C题 附件2 ===")
if os.path.exists(p2):
    d2 = pd.read_csv(p2, nrows=5000, low_memory=False)
    num2 = [c for c in d2.columns if pd.api.types.is_numeric_dtype(d2[c])]
    print("  %dx%d（前 5000 行）  数值列 %d" % (d2.shape[0], d2.shape[1], len(num2)))
    print("  列名: %s" % list(d2.columns)[:10])
else:
    print("  缺文件")