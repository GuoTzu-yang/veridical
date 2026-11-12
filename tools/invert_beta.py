import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))

def merged_rank_ok(J, p, elim, method="pct"):
    """按合并方法算综合名次，被淘汰者必须垫底（名次最大）。"""
    n = len(J)
    rJ = pd.Series(J).rank(ascending=False, method="ordinal").values
    rp = pd.Series(p).rank(ascending=False, method="ordinal").values
    if method == "pct":
        Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
        pn = p / p.sum() if p.sum() > 0 else np.ones(n) / n
        c = 0.5 * Jn + 0.5 * pn
        return elim == int(np.argmin(c))
    else:
        c = 0.5 * rJ + 0.5 * rp
        return elim == int(np.argmax(c))

def feasible_beta(J, elim, method, lo=0.0, hi=60.0, steps=6001):
    """搜 beta 区间：使被淘汰者按该合并方法垫底。"""
    z = (J - J.mean()) / (J.std() if J.std() > 0 else 1.0)
    ok = []
    for b in np.linspace(lo, hi, steps):
        e = np.exp(b * (z - z.max()))
        p = e / e.sum()
        if merged_rank_ok(J, p, elim, method):
            ok.append(b)
    return (min(ok), max(ok)) if ok else (None, None)

rows = []
for (s, w), g in L[L.eliminated == 0].groupby(["season", "week"], sort=True):
    pass
# 每周的存活集合：第 w 周还在的 = eliminated_week==0 或 > w，或 w<=淘汰周
L2 = L.copy()
L2["elim_w"] = L2.groupby("celebrity_name")["eliminated"].transform("max")
rows = []
for (s, w), g in L2.groupby(["season", "week"], sort=True):
    g = g[g.week <= g.elim_w]
    if g.eliminated.sum() != 1:
        continue
    J = g.judge_score.values
    elim = int(np.where(g.eliminated.values == 1)[0][0])
    if len(J) < 3:
        continue
    bp = feasible_beta(J, elim, "pct")
    br = feasible_beta(J, elim, "rank")
    rows.append(dict(season=s, week=w, n=len(J), elim_weeks=int(g.elim_week.iloc[elim]),
                     beta_pct_lo=bp[0], beta_pct_hi=bp[1],
                     beta_rank_lo=br[0], beta_rank_hi=br[1]))
res = pd.DataFrame(rows)
print("  可解周数: %d（共 %d 个季-周组合）" % (len(res), L2.groupby(["season","week"]).ngroups))
print()
print("  beta 区间宽度（pct 法）: 中位 %.2f  最小 %.2f  最大 %.2f"
      % ((res.beta_pct_hi - res.beta_pct_lo).median(),
         (res.beta_pct_hi - res.beta_pct_lo).min(),
         (res.beta_pct_hi - res.beta_pct_lo).max()))
print("  beta 区间宽度（rank 法）: 中位 %.2f" % ((res.beta_rank_hi - res.beta_rank_lo).median()))
print()
print("  宽度最大的 8 周（确定性最差）：")
res["w_pct"] = res.beta_pct_hi - res.beta_pct_lo
print(res.sort_values("w_pct", ascending=False).head(8)[
    ["season","week","n","beta_pct_lo","beta_pct_hi","w_pct"]].to_string(index=False))
res.to_csv(os.path.join(HERE, "out", "beta_feasible.csv"), index=False)