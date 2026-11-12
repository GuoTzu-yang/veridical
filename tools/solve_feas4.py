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
    """名次约束 + 份额非负 + 归一，三者同时满足的 fan share 可行域。"""
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
    lam, ps = [], []
    for _ in range(4000):
        # δ_k = δ_N + Σ_{j>=k} e_j , e>=0 ; δ 递减 ⟹ 综合名次 = placement 序
        dN = RNG.uniform(0.0, 1.0)
        e = RNG.dirichlet(np.ones(n)) * RNG.uniform(0.0, 2.0)
        cum = np.cumsum(e[::-1])[::-1]            # cum[k] = Σ_{j>=k} e_j
        delta = dN + cum
        ssum = delta.sum()
        x = (1.0 - A - ssum) / n
        p = x + (Jn[-1] - Jn) + delta
        if p.min() < EPS - 1e-12:
            continue
        c = 0.5 * Jn + 0.5 * p
        if list(np.argsort(-c)) != list(range(n)):
            continue                               # 复核：名次必须严格一致
        lam.append(float(np.dot(Jn, p)))
        ps.append(p)
    if len(ps) < 5:
        return None
    P = np.array(ps)
    return dict(g=g, Jn=Jn, lam_lo=float(np.percentile(lam, 5)),
                lam_hi=float(np.percentile(lam, 95)),
                lam_med=float(np.median(lam)),
                p_med=np.median(P, axis=0), p_lo=np.percentile(P, 5, axis=0),
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
    prk = desc_rank(Jn)
    for i, nm in enumerate(r["g"].celebrity_name):
        det.append(dict(season=s, week=w, celebrity_name=nm,
                        placement=int(g.plc.iloc[i]),
                        judge=float(g.judge_score.iloc[i]),
                        judge_rank=int(prk[i]), n=int(len(g)),
                        p_est=float(r["p_med"][i]), p_lo=float(r["p_lo"][i]),
                        p_hi=float(r["p_hi"][i])))
res = pd.DataFrame(rows)
print("  可解季-周: %d / %d   平均有效样本 %.0f"
      % (len(res), L.groupby(["season","week"]).ngroups, res.nvalid.mean()))
print("  lambda 中位 %.3f   90%%区间宽度中位 %.3f"
      % (res.lam_med.median(), res.width.median()))
print("  lambda 最高的 5 周:")
print(res.sort_values("lam_med", ascending=False).head(5)[
      ["season","week","n","lam_med","lam_lo","lam_hi"]].to_string(index=False))
res.to_csv(os.path.join(HERE, "out", "fanvote_lam.csv"), index=False)
pd.DataFrame(det).to_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"), index=False)