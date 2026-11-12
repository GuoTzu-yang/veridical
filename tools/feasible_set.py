import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = 0.001          # 每人至少 0.1% 的票（真实 fan vote 不会为 0）
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))


def desc_rank(v):
    v = np.asarray(v, dtype=float)
    order = np.argsort(-v, kind="mergesort")
    r = np.empty(len(v), dtype=float)
    r[order] = np.arange(1, len(v) + 1)
    u = {}
    for i, x in enumerate(v):
        u.setdefault(x, []).append(i)
    for x, idx in u.items():
        if len(idx) > 1:
            r[idx] = np.mean(r[idx])
    return r


def feasible_set(J, elim, method="pct", eps=EPS):
    """求每周 fan share 的可行域。返回 (lam_lo, lam_hi, p_e_hi, bounds)。"""
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    if method == "pct":
        c = Jn - Jn[elim]                 # p_i >= p_e - c_i
    else:
        c = (desc_rank(J) - desc_rank(J)[elim]) / n   # rank 法的近似尺度
    c = np.clip(c, 0.0, None)

    def lows(pe):
        return np.maximum(eps, pe - c)

    # p_e 上界：sum(lows) <= 1
    lo, hi = 0.0, 1.0
    if lows(hi).sum() > 1.0:
        for _ in range(200):
            mid = (lo + hi) / 2
            if lows(mid).sum() > 1.0:
                hi = mid
            else:
                lo = mid
        pe_hi = lo
    else:
        pe_hi = 1.0
    if lows(pe_hi).sum() > 1.0 + 1e-9:
        return None

    # 断点：p_e 落在 c_i 处时 L_i 换段
    brk = sorted(set([0.0, pe_hi] + [x for x in c if 0 < x < pe_hi]))
    pts = []
    for b in brk:
        pts += [b, min(b + 1e-7, pe_hi)]
    pts = sorted(set(round(x, 12) for x in pts if 0 <= x <= pe_hi))

    lam_lo, lam_hi = 1e9, -1e9
    p_lo = np.full(n, np.inf)
    p_hi = np.full(n, -np.inf)
    for pe in pts:
        Lw = lows(pe)
        free = 1.0 - pe - (Lw.sum() - Lw[elim])
        if free < -1e-12:
            continue
        for i in range(n):
            if i == elim:
                lo_i, hi_i = pe, pe
            else:
                lo_i = Lw[i]
                hi_i = Lw[i] + free
            p_lo[i] = min(p_lo[i], lo_i)
            p_hi[i] = max(p_hi[i], hi_i)
            lam_lo = min(lam_lo, Jn[i] * lo_i)
            lam_hi = max(lam_hi, Jn[i] * hi_i)
    if lam_hi < lam_lo:
        return None
    return dict(lam_lo=lam_lo, lam_hi=lam_hi, pe_hi=pe_hi,
                p_lo=p_lo, p_hi=p_hi, Jn=Jn)


rows = []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    if int(g.eliminated.sum()) != 1:
        continue
    J = g.judge_score.values.astype(float)
    elim = int(np.where(g.eliminated.values == 1)[0][0])
    if len(J) < 3:
        continue
    for m in ("pct", "rank"):
        r = feasible_set(J, elim, m)
        if r is None:
            rows.append(dict(season=s, week=w, n=len(J), method=m,
                             feasible=0, lam_lo=np.nan, lam_hi=np.nan,
                             width=np.nan, pe_hi=np.nan))
        else:
            rows.append(dict(season=s, week=w, n=len(J), method=m, feasible=1,
                             lam_lo=r["lam_lo"], lam_hi=r["lam_hi"],
                             width=r["lam_hi"] - r["lam_lo"], pe_hi=r["pe_hi"]))
res = pd.DataFrame(rows)
for m in ("pct", "rank"):
    d = res[(res.method == m) & (res.feasible == 1)]
    print("  %s 法：可行季-周 %d / %d   lambda 宽度中位 %.4f  最大 %.4f"
          % (m, len(d), (res.method == m).sum(),
             d.width.median() if len(d) else np.nan,
             d.width.max() if len(d) else np.nan))
print()
d = res[(res.method == "pct") & (res.feasible == 1)]
print("  lambda 区间最宽的 8 周（观众票最不确定）：")
print(d.sort_values("width", ascending=False).head(8)[
    ["season", "week", "n", "lam_lo", "lam_hi", "width"]].to_string(index=False))
res.to_csv(os.path.join(HERE, "out", "fanvote_feasible.csv"), index=False)