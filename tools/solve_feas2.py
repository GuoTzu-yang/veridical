import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = 0.002
RNG = np.random.default_rng(2026)
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
place = dict(zip(W.celebrity_name, W.placement))
exitw = dict(zip(W.celebrity_name, np.where(W.eliminated_week > 0,
                                            W.eliminated_week, W.last_week)))


def week_set(g):
    g = g.copy()
    g["plc"] = g.celebrity_name.map(place)
    g["exw"] = g.celebrity_name.map(exitw)
    g = g[g.exw >= g.week]
    if len(g) < 3 or g.plc.isna().any():
        return None
    g = g.sort_values("plc").reset_index(drop=True)
    J = g.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    A = float(np.sum(Jn[-1] - Jn))
    B = 1.0 - A + n * (Jn[-1] - Jn) - n * EPS

    def dmin(S):
        return np.maximum(0.0, (S - B) / (n - 1))

    def smax():
        lo, hi = 0.0, 5.0
        if dmin(hi).sum() <= hi:
            return hi
        for _ in range(120):
            mid = (lo + hi) / 2
            if dmin(mid).sum() > mid:
                hi = mid
            else:
                lo = mid
        return lo

    Sm = smax()
    lam, ps = [], []
    for _ in range(400):
        S = RNG.uniform(0, Sm)
        d = dmin(S)
        need = S - d.sum()
        if need > 1e-12:
            w = RNG.dirichlet(np.ones(n))
            d = d + need * w
        x = (1.0 - A - d.sum()) / n
        p = x + (Jn[-1] - Jn) + d
        p = np.clip(p, EPS, None)
        p = p / p.sum()
        lam.append(float(np.dot(Jn, p)))
        ps.append(p)
    P = np.array(ps)
    return dict(g=g, Jn=Jn, lam_lo=float(np.percentile(lam, 5)),
                lam_hi=float(np.percentile(lam, 95)),
                lam_med=float(np.median(lam)), p_med=np.median(P, axis=0),
                p_lo=np.percentile(P, 5, axis=0), p_hi=np.percentile(P, 95, axis=0))


rows, det = [], []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    r = week_set(g)
    if r is None:
        continue
    rows.append(dict(season=s, week=w, n=len(r["g"]), lam_lo=r["lam_lo"],
                     lam_hi=r["lam_hi"], lam_med=r["lam_med"],
                     width=r["lam_hi"] - r["lam_lo"]))
    for i, nm in enumerate(r["g"].celebrity_name):
        det.append(dict(season=s, week=w, celebrity_name=nm,
                        placement=int(r["g"].plc.iloc[i]),
                        judge=float(r["g"].judge_score.iloc[i]),
                        p_est=float(r["p_med"][i]),
                        p_lo=float(r["p_lo"][i]), p_hi=float(r["p_hi"][i])))
res = pd.DataFrame(rows)
print("  可解季-周: %d / %d" % (len(res), L.groupby(["season","week"]).ngroups))
print("  lambda（观众票被评委分解释的比例）: 中位 %.3f" % res.lam_med.median())
print("  90%% 可信区间宽度: 中位 %.3f  最小 %.3f  最大 %.3f"
      % (res.width.median(), res.width.min(), res.width.max()))
print("  lambda 最高（观众最跟随评委）的 5 周：")
print(res.sort_values("lam_med", ascending=False).head(5)[
      ["season","week","n","lam_med","lam_lo","lam_hi"]].to_string(index=False))
res.to_csv(os.path.join(HERE, "out", "fanvote_lam.csv"), index=False)
pd.DataFrame(det).to_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"), index=False)
print("  已写出 fanvote_lam.csv / fanvote_bounds.csv")