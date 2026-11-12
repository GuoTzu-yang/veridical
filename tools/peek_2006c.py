import os
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "external", "github",
                    "usail-hkust__LLM-MM-Agent", "LLM-MM-Agent-main",
                    "MMBench", "dataset", "2006_C")
for f in ("population_data.xls", "fertility_data.xls",
          "life_expectancy_0_data.xls", "birth_rate_data.xls"):
    p = os.path.join(BASE, f)
    if not os.path.exists(p):
        print("  缺 %s" % f)
        continue
    d = pd.read_excel(p)
    num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    print("  === %s : %d 行 x %d 列（数值 %d）===" % (f, len(d), len(d.columns),
                                                len(num)))
    print("      列: %s" % [str(c)[:14] for c in d.columns[:10]])
    print("      样例行: %s" % [str(x)[:12] for x in d.iloc[0].tolist()[:8]])
    # 找最后一个数值列（通常是 2005 年）和倒数第二（2004）
    if len(num) >= 2:
        print("      末两个数值列: %s / %s" % (num[-2], num[-1]))
    print()