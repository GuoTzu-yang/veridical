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


def desc_rank(v):
    v = np.asarray(v, float)
    o = np.argsort(-v, kind="mergesort")
    r = np.empty(len(v)); r[o] = np.arange(1, len(v) + 1)
    u = {}
    for i, x in enumerate(v):
        u.setdefault(x, []).append(i)
    for x, idx in u.items():
        if len(idx) > 1:
            r[idx] = np.mean(r[idx])
    return r


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
    # B_k = 1 - A + N(Jn_(N)-Jn_(k)) - N*EPS ; 约束 S - N*delta_k <= B_k
    B = 1.0 - A + n * (Jn[-1] - Jn) - n * EPS
    dmin = lambda S: np.maximum(0.0, (S - B) / n)

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
    for _ in range(600):
        S = RNG.uniform(0, Sm)
        d = dmin(S)
        need = S - d.sum()
        if need > 1e-12:
            d = d + need * RNG.dirichlet(np.ones(n))
        x = (1.0 - A - d.sum()) / n
        p = x + (Jn[-1] - Jn) + d
        # ── 采样后验证：份额非负、和为 1、名次与 placement 一致 ──
        if p.min() < EPS - 1e-9 or abs(p.sum() - 1.0) > 1e-6:
            continue
        c = 0.5 * Jn + 0.5 * p
        if not np.all(np.diff(c[np.argsort(Jn)]) >= -1e-9):
            pass
        if list(np.argsort(-c)) != list(range(n)):
            continue                      # 综合名次必须与 placement 序一致
        lam.append(float(np.dot(Jn, p)))
        ps.append(p)
    if not ps:
        return None
    P = np.array(ps)
    return dict(g=g, Jn=Jn, lam_lo=float(np.percentile(lam, 5)),
                lam_hi=float(np.percentile(lam, 95)),
                lam_med=float(np.median(lam)),
                p_med=np.median(P, axis=0),
                p_lo=np.percentile(P, 5, axis=0),
                p_hi=np.percentile(P, 95, axis=0), nvalid=len(ps))


rows, det = [], []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    r = week_set(g)
    if r is None:
        continue
    rows.append(dict(season=s, week=w, n=len(r["g"]), lam_lo=r["lam_lo"],
                     lam_hi=r["lam_hi"], lam_med=r["lam_med"],
                     width=r["lam_hi"] - r["lam_lo"], nvalid=r["nvalid"]))
    Jn, g = r["Jn"], r["g"]
    prk = desc_rank(Jn)                # 评委分名次（1=最好）
    for i, nm in enumerate(r["g"].celebrity_name):
        det.append(dict(season=s, week=w, celebrity_name=nm,
                        placement=int(g.plc.iloc[i]),
                        judge=float(g.judge_score.iloc[i]),
                        judge_rank=int(prk[i]), n=int(len(g)),
                        p_est=float(r["p_med"][i]),
                        p_lo=float(r["p_lo"][i]), p_hi=float(r["p_hi"][i])))
res = pd.DataFrame(rows)
print("  可解季-周: %d / %d   平均有效样本 %.0f"
      % (len(res), L.groupby(["season","week"]).ngroups, res.nvalid.mean()))
print("  lambda 中位 %.3f   90%%区间宽度中位 %.3f"
      % (res.lam_med.median(), res.width.median()))
res.to_csv(os.path.join(HERE, "out", "fanvote_lam.csv"), index=False)
pd.DataFrame(det).to_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"), index=False)
print("  写出 fanvote_lam.csv / fanvote_bounds.csv")