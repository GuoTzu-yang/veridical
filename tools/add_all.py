import json
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
DATA = os.path.join(HERE, "out", "data")
os.makedirs(DATA, exist_ok=True)

# 标识符列：不能当目标或解释变量
ID_WORDS = ("index", "id", "code", "编号", "序号", "批次", "模拟轮次",
            "customer", "review", "product", "parent", "row", "unnamed")

# (runs 名字, 文件名, 题面)
JOBS = [
    ("ecdc_cohort", "Problem C - Most Recent Cohort.xls",
     "epidemic cohort incidence across regions and years"),
    ("pop_panel", "population_data.xls",
     "population growth path of each country"),
    ("age_struct", "age_data.xls",
     "age structure of national populations"),
    ("life_exp", "life_expectancy_0_data.xls",
     "life expectancy across countries and periods"),
    ("birth_rate", "birth_rate_data.xls",
     "birth rate trend across countries"),
    ("hiv", "hiv_aids_data.xls",
     "hiv prevalence and its correlates"),
    ("fertility", "fertility_data.xls",
     "fertility by age band across countries"),
    ("nflis", "MCM_NFLIS_Data.xlsx",
     "drug report counts across states and years"),
    ("review_microwave", "microwave.tsv",
     "which review features drive helpfulness votes"),
    ("review_pacifier", "pacifier.tsv",
     "which review features drive helpfulness votes"),
]


def find(fn):
    best = None
    for root, dirs, files in os.walk(EXT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        if fn in files:
            p = os.path.join(root, fn)
            if best is None or len(p) < len(best):
                best = p
    return best


def load(p):
    if p.lower().endswith(".tsv"):
        return pd.read_csv(p, sep="\t", low_memory=False,
                           encoding_errors="replace")
    if p.lower().endswith(".csv"):
        return pd.read_csv(p, low_memory=False, encoding_errors="replace")
    if p.lower().endswith(".xls"):
        try:
            return pd.read_excel(p)
        except Exception:
            xl = pd.ExcelFile(p)
            best, n = None, -1
            for sh in xl.sheet_names:
                d = xl.parse(sh)
                k = sum(1 for c in d.columns
                        if pd.api.types.is_numeric_dtype(d[c]))
                if k > n:
                    best, n = d, k
            return best
    xl = pd.ExcelFile(p)
    best, n = None, -1
    for sh in xl.sheet_names:
        d = xl.parse(sh)
        k = sum(1 for c in d.columns if pd.api.types.is_numeric_dtype(d[c]))
        if k > n:
            best, n = d, k
    return best


cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
added = []
for name, fn, problem in JOBS:
    p = find(fn)
    if not p:
        print("  [skip] %s 找不到" % fn)
        continue
    d = load(p)
    if d is None or len(d) < 20:
        print("  [skip] %s 行数不足" % fn)
        continue
    num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    use = [c for c in num
           if not any(w in str(c).lower() for w in ID_WORDS)]
    if len(use) < 2:
        print("  [skip] %s 数值列不足（%d）" % (fn, len(use)))
        continue
    # 行数上限：太大就降采样（回归不需要两万行，但保留量级信息）
    if len(d) > 6000:
        d = d.iloc[::max(1, len(d) // 6000)].reset_index(drop=True)
        print("    降采样 -> %d 行" % len(d))
    out = d[use].copy()
    dst = os.path.join(DATA, name + ".xlsx")
    out.to_excel(dst, index=False, sheet_name="Sheet1")
    y = use[-1]
    xs = use[:min(4, len(use) - 1)]
    mins = [y] + use[:2]
    cfg[name] = {
        "data": name + ".xlsx", "y": str(y),
        "x": ",".join(str(c) for c in xs),
        "min": ",".join(str(c) for c in mins),
        "problem": problem, "out": "out/runs/" + name}
    added.append((name, len(out), len(use), str(y), xs))
    print("  + %-18s %5d 行 x %2d 列  y=%s  x=%s"
          % (name, len(out), len(use), str(y)[:18],
             ",".join(str(c) for c in xs)[:38]))

json.dump(cfg, open(os.path.join(HERE, "runs.json"), "w",
                    encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print()
print("  新增 %d 道，runs.json 共 %d 道" % (len(added), len(cfg)))