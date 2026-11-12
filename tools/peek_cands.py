import os
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "external", "github",
                    "usail-hkust__LLM-MM-Agent")
targets = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if f in ("population_data.xls", "fertility_data.xls",
                 "hiv_aids_data.xls", "life_expectancy_0_data.xls",
                 "birth_rate_data.xls", "age_data.xls",
                 "MCM_NFLIS_Data.xlsx", "hair_dryer.tsv",
                 "microwave.tsv", "pacifier.tsv"):
            targets.append(os.path.join(root, f))
targets = sorted(set(targets))
print("  找到 %d 个目标文件" % len(targets))
for p in targets:
    rel = os.path.relpath(p, HERE)
    try:
        if p.lower().endswith(".tsv"):
            d = pd.read_csv(p, sep="\t", nrows=400, low_memory=False,
                           encoding_errors="replace")
        elif p.lower().endswith(".xls"):
            d = pd.read_excel(p, nrows=400)
        else:
            d = pd.read_excel(p, nrows=400)
    except Exception as e:
        print("    [skip] %s  %s" % (rel, type(e).__name__))
        continue
    num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    print("    %s" % rel.split("LLM-MM-Agent")[-1][:70])
    print("        %d 行 x %d 列（数值 %d）  列名: %s"
          % (len(d), len(d.columns), len(num),
             [str(c)[:16] for c in d.columns[:6]]))