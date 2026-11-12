import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")
for f in sorted(os.listdir(D)):
    if not f.endswith(".xlsx"):
        continue
    d = pd.read_excel(os.path.join(D, f))
    num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    print("  === %s : %d 行 x %d 数值列 ===" % (f, len(d), len(num)))
    print("      全部列: %s" % [str(c)[:18] for c in d.columns])
    print()