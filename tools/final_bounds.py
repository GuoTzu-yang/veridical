import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = 0.003
RNG = np.random.default_rng(2026)
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
W["_k"] = list(zip(W.season, W.celebrity_name))
place = dict(zip(W["_k"], W.placement))
exitw = dict(zip(W["_k"], np.where(W.eliminated_week > 0,
                                     W.eliminated_week, W.last_week)))
L["_k"] = list(zip(L.season, L.celebrity_name))


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


def week_bounds(g, method="pct"):
    """一周的 fan share 可行域（pct 解析 / rank 采样）。返回每人 [lo,hi] 与 λ 范围。"""
    g = g.copy()
    g["plc"] = g["_k"].map(place)
    g["exw"] = g["_k"].map(exitw)
    # 先记下淘汰者的名字，再过滤 —— 否则 exitw 映射不到时
    # NaN 比较为 False，淘汰者会被过滤掉，索引越界。
    elim_names = g.loc[g.eliminated == 1, "celebrity_name"].tolist()
    if len(elim_names) != 1:
        return None
    elim_name = elim_names[0]
    g = g[g.exw >= g.week].copy()
    if len(g) < 3 or g.plc.isna().any() or elim_name not in set(g.celebrity_name):
        return None
    g = g.sort_values("plc").reset_index(drop=True)
    J = g.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    elim = int(np.where(g.celebrity_name.values == elim_name)[0][0])
    if n < 3:
        return None
    if method == "pct":
        # 约束：c_e <= c_i  =>  p_e - p_i <= Jn_i - Jn_e
        c = Jn - Jn[elim]
        # 2026-11-10 修：原来是 np.full(n, EPS)，而下方 p.min() >= EPS 过滤
        # 保证了 p >= EPS，于是 np.minimum(EPS, p) 恒等于 EPS —— p_lo 永远
        # 是 0.003，不是「算出来的下界」。这让 p_est=(p_lo+p_hi)/2 系统性
        # 偏低，实测 p_est 在 52% 的周违反论文自己的式(1)。
        # 改成 inf 初始化，才能在循环里真正取到样本最小值。
        best_lo = np.full(n, np.inf)
        best_hi = np.full(n, -1e9)
        lam_lo, lam_hi = 1e9, -1e9
        samples = []                      # (lam, p)：可行样本，用于选代表点
        # 采样 p_e ∈ [EPS, 1]，其余 p_i 的下界 max(EPS, p_e - c_i)
        for _ in range(1500):
            pe = RNG.uniform(EPS, 1.0)
            lo_i = np.maximum(EPS, pe - c)
            rest = 1.0 - pe - (lo_i.sum() - lo_i[elim])
            if rest < -1e-9:
                continue
            p = lo_i.copy()
            free = np.array([i for i in range(n) if i != elim])
            if len(free) and rest > 0:
                w = RNG.dirichlet(np.ones(len(free)))
                p[free] = lo_i[free] + rest * w
            if p.min() < EPS - 1e-9:
                continue
            p = p / p.sum()
            cnew = 0.5 * Jn + 0.5 * p
            if int(np.argmin(cnew)) != elim:
                continue                       # 复核：淘汰者必须垫底
            best_lo = np.minimum(best_lo, p)
            best_hi = np.maximum(best_hi, p)
            l = float(np.dot(Jn, p))
            lam_lo = min(lam_lo, l); lam_hi = max(lam_hi, l)
            samples.append((l, p.copy()))
        if best_hi.max() < 0 or not samples:
            return None
        best_lo = np.where(np.isfinite(best_lo), best_lo, EPS)
        # 代表点必须是**可行样本**之一，不能取坐标中点（中点可能不可行）。
        # 取 λ 最接近中位数的那个样本，保证可复现、且确实满足约束。
        _lams = np.array([s[0] for s in samples])
        _mid = float(np.median(_lams))
        p_est = samples[int(np.argmin(np.abs(_lams - _mid)))][1]
        return dict(g=g, Jn=Jn, elim=elim, p_lo=best_lo, p_hi=best_hi,
                    p_est=p_est, n_samples=len(samples),
                    lam_lo=lam_lo, lam_hi=lam_hi, method=method)
    else:
        # rank 法：c = 0.5*rJ + 0.5*r_p，淘汰者须综合最差
        # 同 pct 分支：inf 初始化，否则 np.minimum(EPS, p) 恒为 EPS
        best_lo = np.full(n, np.inf); best_hi = np.full(n, -1e9)
        lam_lo, lam_hi = 1e9, -1e9
        rJ = desc_rank(J)
        for _ in range(3000):
            w = RNG.dirichlet(np.ones(n))
            p = w / w.sum()
            if p.min() < EPS:
                continue
            rp = desc_rank(p)
            c = 0.5 * rJ + 0.5 * rp
            if int(np.argmax(c)) != elim:
                continue
            best_lo = np.minimum(best_lo, p)
            best_hi = np.maximum(best_hi, p)
            l = float(np.dot(Jn, p))
            lam_lo = min(lam_lo, l); lam_hi = max(lam_hi, l)
        if best_hi.max() < 0:
            return None
        best_lo = np.where(np.isfinite(best_lo), best_lo, EPS)
        return dict(g=g, Jn=Jn, elim=elim, p_lo=best_lo, p_hi=best_hi,
                    lam_lo=lam_lo, lam_hi=lam_hi, method=method)


rows, det = [], []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    if int(g.eliminated.sum()) != 1:
        continue
    for m in ("pct", "rank"):
        r = week_bounds(g, m)
        if r is None:
            rows.append(dict(season=s, week=w, method=m, ok=0, n=0))
            continue
        rows.append(dict(season=s, week=w, method=m, ok=1, n=len(r["g"]),
                         lam_lo=r["lam_lo"], lam_hi=r["lam_hi"],
                         width=r["lam_hi"] - r["lam_lo"]))
        if m == "pct":
            prk = desc_rank(r["Jn"])
            _pe = r.get("p_est")
            for i, nm in enumerate(r["g"].celebrity_name):
                det.append(dict(season=s, week=w, celebrity_name=nm,
                                placement=int(r["g"].plc.iloc[i]),
                                judge=float(r["g"].judge_score.iloc[i]),
                                judge_rank=int(prk[i]), n=int(len(r["g"])),
                                p_lo=float(r["p_lo"][i]), p_hi=float(r["p_hi"][i]),
                                # 代表点取可行样本，不再用 p_lo/p_hi 的中点
                                p_est=float(_pe[i]) if _pe is not None
                                else float((r["p_lo"][i] + r["p_hi"][i]) / 2)))
res = pd.DataFrame(rows)
for m in ("pct", "rank"):
    d = res[(res.method == m) & (res.ok == 1)]
    print("  %-4s 法：可行季-周 %d / %d   lambda 宽度中位 %.3f"
          % (m, len(d), (res.method == m).sum(),
             d.width.median() if len(d) else float("nan")))
res.to_csv(os.path.join(HERE, "out", "fanvote_lam.csv"), index=False)
pd.DataFrame(det).to_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"), index=False)
print("  写出 fanvote_lam.csv / fanvote_bounds.csv")