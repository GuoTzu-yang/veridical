import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))


def desc_rank(v):
    """降序名次（1=最好）。并列取平均名次，与赛事的并列处理一致。"""
    v = np.asarray(v, dtype=float)
    order = np.argsort(-v, kind="mergesort")
    ranks = np.empty(len(v), dtype=float)
    ranks[order] = np.arange(1, len(v) + 1)
    # 并列：同值取平均
    uniq = {}
    for i, x in enumerate(v):
        uniq.setdefault(x, []).append(i)
    for x, idx in uniq.items():
        if len(idx) > 1:
            ranks[idx] = np.mean(ranks[idx])
    return ranks


def elim_is_last(J, p, elim, method):
    n = len(J)
    rJ = desc_rank(J)
    rp = desc_rank(p)
    if method == "pct":
        Jn = ((J - J.min()) / (J.max() - J.min())
              if J.max() > J.min() else np.zeros(n))
        pn = p / p.sum() if p.sum() > 0 else np.ones(n) / n
        c = 0.5 * Jn + 0.5 * pn
        return elim == int(np.argmin(c))
    c = 0.5 * rJ + 0.5 * rp
    return elim == int(np.argmax(c))


def feasible_beta(J, elim, method, lo=0.0, hi=80.0, steps=8001):
    z = (J - J.mean()) / (J.std() if J.std() > 0 else 1.0)
    ok = []
    for b in np.linspace(lo, hi, steps):
        e = np.exp(b * (z - z.max()))
        p = e / e.sum()
        if elim_is_last(J, p, elim, method):
            ok.append(b)
    return (min(ok), max(ok)) if ok else (None, None)


L["elim_w"] = L.groupby("celebrity_name")["eliminated"].transform("max")
rows = []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    g = g[g.week <= g.elim_w]
    if int(g.eliminated.sum()) != 1:
        continue
    J = g.judge_score.values.astype(float)
    elim = int(np.where(g.eliminated.values == 1)[0][0])
    if len(J) < 3:
        continue
    bp = feasible_beta(J, elim, "pct")
    br = feasible_beta(J, elim, "rank")
    rows.append(dict(season=s, week=w, n=len(J), elim_weeks=int(g.elim_w.iloc[elim]),
                     beta_pct_lo=bp[0], beta_pct_hi=bp[1],
                     beta_rank_lo=br[0], beta_rank_hi=br[1]))
res = pd.DataFrame(rows)
res["w_pct"] = res.beta_pct_hi - res.beta_pct_lo
res["w_rank"] = res.beta_rank_hi - res.beta_rank_lo
print("  可解季-周: %d / %d" % (len(res), L.groupby(["season", "week"]).ngroups))
print("  无法复现的周（两法都无解）: %d" % ((res.beta_pct_lo.isna()).sum()))
print()
print("  beta 区间宽度 pct 法: 中位 %.2f  最小 %.2f  最大 %.2f"
      % (res.w_pct.median(), res.w_pct.min(), res.w_pct.max()))
print("  beta 区间宽度 rank 法: 中位 %.2f  最小 %.2f  最大 %.2f"
      % (res.w_rank.median(), res.w_rank.min(), res.w_rank.max()))
print()
print("  最不确定的 8 周（pct 法）：")
print(res.sort_values("w_pct", ascending=False).head(8)[
    ["season", "week", "n", "elim_weeks", "beta_pct_lo", "beta_pct_hi", "w_pct"]
].to_string(index=False))
res.to_csv(os.path.join(HERE, "out", "beta_feasible.csv"), index=False)