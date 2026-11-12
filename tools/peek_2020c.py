import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "external", "github",
                    "usail-hkust__LLM-MM-Agent", "LLM-MM-Agent-main",
                    "MMBench", "dataset", "2020_C")
d = pd.read_csv(os.path.join(BASE, "hair_dryer.tsv"), sep="\t",
                low_memory=False, encoding_errors="replace")
print("  2020_C hair_dryer: %d 行 x %d 列" % d.shape)
for c in d.columns:
    nu = d[c].nunique()
    print("    %-22s dtype=%-10s 唯一值 %d" % (str(c)[:22], str(d[c].dtype)[:10], nu))
num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
print("  数值列: %s" % num)