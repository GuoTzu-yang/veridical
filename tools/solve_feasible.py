import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = 0.002
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
place = dict(zip(W.celebrity_name, W.placement))
exitw = dict(zip(W.celebrity_name, np.where(W.eliminated_week > 0,
                                            W.eliminated_week, W.last_week)))


def solve_week(g):
    """给一周的选手（含淘汰者），求 fan share 可行域。"""
    g = g.copy()
    g["plc"] = g.celebrity_name.map(place)
    g["exw"] = g.celebrity_name.map(exitw)
    g = g[g.exw >= g.week]              # 该周仍在的
    if len(g) < 3 or g.plc.isna().any():
        return None
    g = g.sort_values("plc").reset_index(drop=True)
    J = g.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    A = float(np.sum(Jn[-1] - Jn))       # Σ (Jn_(N) - Jn_(k))
    meanJn = float(Jn.mean())

    # p_(k) = x + (Jn_(N)-Jn_(k)) + δ_k ;  δ>=0 ; Σp=1
    # x = (1 - A - Σδ)/N
    # 约束 p_(k) >= EPS  =>  Σ_{m≠k} δ_m <= B_k
    B = 1.0 - A + n * (EPS - (Jn[-1] - Jn))     # 注意 Jn[-1] 是 Jn_(N)

    # Σ_{m≠k} δ_m <= B_k, δ>=0  =>  S - δ_k <= B_k, S=Σδ
    # 给定 S：δ_k >= S - B_k (取正部)；需 Σ max(0,S-B_k) <= S
    def S_max():
        lo, hi = 0.0, 10.0
        if np.maximum(0.0, hi - B).sum() <= hi:
            return hi
        for _ in range(200):
            mid = (lo + hi) / 2
            if np.maximum(0.0, mid - B).sum() > mid:
                hi = mid
            else:
                lo = mid
        return lo

    Smax = S_max()
    coef = Jn - meanJn

    def lam_at(S, want_max=True):
        """给定 S=Σδ，λ 的最优值（余量优先给极端系数的）。"""
        base = np.maximum(0.0, S - B)
        need = S - base.sum()
        if need <= 1e-12:
            return float(np.dot(coef, base))
        order = np.argsort(coef)
        if want_max:
            k = order[-1]
        else:
            k = order[0]
        d = base.copy()
        d[k] += need
        return float(np.dot(coef, d))

    lam_hi = max(lam_at(s, True) for s in np.linspace(0, Smax, 41))
    lam_lo = min(lam_at(s, False) for s in np.linspace(0, Smax, 41))

    # p_(k) 的上下界（用同样框架，目标是 p_k）
    def p_at(S, k, want_max=True):
        base = np.maximum(0.0, S - B)
        need = S - base.sum()
        d = base.copy()
        if need > 1e-12:
            # 让 p_k 最大：把余量给 δ_k 之外的、且不违反 B 的位置；
            # 简化：把余量给「B_m 最大」的 m≠k（该 m 不受 S-δ_k 约束）
            cand = [m for m in range(len(B)) if m != k]
            if cand:
                m = max(cand, key=lambda i: B[i]) if want_max else min(cand, key=lambda i: B[i])
                d[m] += need
        x = (1.0 - A - d.sum()) / n
        return x + (Jn[-1] - Jn[k]) + d[k]

    ks = list(range(n))
    p_hi = np.array([max(p_at(s, k, True) for s in np.linspace(0, Smax, 21))
                     for k in ks])
    p_lo = np.array([min(p_at(s, k, False) for s in np.linspace(0, Smax, 21))
                     for k in ks])
    return dict(g=g, Jn=Jn, lam_lo=lam_lo, lam_hi=lam_hi,
                p_lo=p_lo, p_hi=p_hi, Smax=Smax)


rows, details = [], []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    r = solve_week(g)
    if r is None:
        continue
    rows.append(dict(season=s, week=w, n=len(r["g"]), lam_lo=r["lam_lo"],
                     lam_hi=r["lam_hi"], width=r["lam_hi"] - r["lam_lo"],
                     Smax=r["Smax"]))
    for i, nm in enumerate(r["g"].celebrity_name):
        details.append(dict(season=s, week=w, celebrity_name=nm,
                            placement=int(r["g"].plc.iloc[i]),
                            judge=r["g"].judge_score.iloc[i],
                            p_lo=r["p_lo"][i], p_hi=r["p_hi"][i]))
res = pd.DataFrame(rows)
print("  可解季-周: %d / %d" % (len(res), L.groupby(["season","week"]).ngroups))
print("  lambda 宽度: 中位 %.4f  最小 %.4f  最大 %.4f"
      % (res.width.median(), res.width.min(), res.width.max()))
print("  最确定的 5 周:", res.sort_values("width").head(5)[
      ["season","week","n","lam_lo","lam_hi","width"]].to_dict("records"))
res.to_csv(os.path.join(HERE, "out", "fanvote_lam.csv"), index=False)
pd.DataFrame(details).to_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"), index=False)
print("  已写出 fanvote_lam.csv / fanvote_bounds.csv")