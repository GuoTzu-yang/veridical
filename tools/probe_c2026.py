import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
hits = []
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if "2026_MCM_Problem_C" in f or "Most Recent Cohort" in f:
            hits.append(os.path.join(root, f))
for p in hits:
    print("  === %s ===" % p.replace(HERE, "."))
    try:
        d = pd.read_csv(p) if p.lower().endswith(".csv") else pd.read_excel(p)
    except Exception as e:
        print("     读失败:", e); continue
    print("     形状: %s" % (d.shape,))
    print("     列(%d): %s" % (len(d.columns), [str(c)[:22] for c in d.columns][:14]))
    print("     前 2 行:")
    print(d.head(2).to_string()[:400])
    print()