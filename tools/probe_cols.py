import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(HERE, "external", "github", "li1408__MathModelHub",
                   "competitions", "2026_MCM_Problem_C_Data.csv")
d = pd.read_csv(src)
print("  形状: %s" % (d.shape,))
print()
print("  全部列：")
for i, c in enumerate(d.columns):
    nn = d[c].notna().sum()
    print("    %2d %-34s 非空 %4d  %s" % (i, str(c)[:34], nn, str(d[c].dtype)[:10]))