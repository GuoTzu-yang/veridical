import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
B = pd.read_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"))
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


# ── 1. 两法对比：用同一份 fan vote 估计，两种合并法各模拟一遍整季 ──
piv = B.pivot_table(index=["season", "week"], columns="celebrity_name",
                     values="p_est")
piv = piv.dropna(axis=1, how="all")
sim = []
for s in sorted(W.season.unique()):
    names = W[W.season == s].celebrity_name.tolist()
    for method in ("pct", "rank"):
        alive = [n for n in names]
        elim_order = []
        for w in range(1, 12):
            live = [n for n in alive if exitw[n] >= w]
            if len(live) <= 2:
                break
            J = np.array([float(L[(L.season == s) & (L.week == w) &
                                  (L.celebrity_name == n)].judge_score.iloc[0])
                          for n in live])
            row = piv.loc[(s, w)] if (s, w) in piv.index else None
            if row is None:
                break
            p = np.array([float(row[n]) if n in row.index and
                          not pd.isna(row[n]) else 1.0 / len(live) for n in live])
            p = p / p.sum()
            n = len(live)
            if method == "pct":
                Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
                c = 0.5 * Jn + 0.5 * p
                worst = int(np.argmin(c))
            else:
                c = 0.5 * desc_rank(J) + 0.5 * desc_rank(p)
                worst = int(np.argmax(c))
            elim_order.append((w, live[worst]))
            alive = [x for x in alive if x != live[worst]]
        got = {}
        for w, nm in elim_order:
            got[nm] = w
        for nm in names:
            sim.append(dict(season=s, method=method, celebrity_name=nm,
                            actual_plc=int(place[nm]),
                            sim_elim_week=got.get(nm, 0)))
sim = pd.DataFrame(sim)
print("  === 两种合并法的整季模拟 ===")
for m in ("pct", "rank"):
    d = sim[sim.method == m]
    exact = (d.sim_elim_week == d.actual_plc.map(
        dict(zip(W.celebrity_name, W.eliminated_week))).fillna(0)).mean()
    # 用「淘汰顺序是否与真实 placement 序一致」衡量
    ordok = 0
    for s in d.season.unique():
        dd = d[d.season == s].copy()
        dd["seq"] = dd.sim_elim_week.where(dd.sim_elim_week > 0, 99)
        a = dd.sort_values("seq").celebrity_name.tolist()
        b = dd.sort_values("actual_plc").celebrity_name.tolist()
        if a == b:
            ordok += 1
    print("    %-5s 整季淘汰顺序与真实完全一致的季数: %d / %d"
          % (m, ordok, d.season.nunique()))
sim.to_csv(os.path.join(HERE, "out", "sim_two_methods.csv"), index=False)
print()

# ── 2. controversy 案例：超额人气 ──
print("  === 题面点名的 controversy 案例 ===")
targets = [("Jerry Rice", 2), ("Billy Ray Cyrus", 4),
           ("Bristol Palin", 11), ("Bobby Bones", 27)]
for nm, s in targets:
    d = B[(B.season == s) & (B.celebrity_name == nm)]
    if d.empty:
        print("    %-16s 未在数据中找到" % nm); continue
    row = d.iloc[0]
    # 同周同季的「按评委分应得份额」基准
    wk = int(row.week)
    peers = B[(B.season == s) & (B.week == wk)]
    J = peers.judge.values.astype(float)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(len(J))
    base = Jn / Jn.sum() if Jn.sum() > 0 else np.ones(len(J)) / len(J)
    exp = float(base[list(peers.celebrity_name).index(nm)])
    act = float(row.p_est)
    print("    %-16s S%-3d 第%2d周  估计份额 %.3f  按评委分应得 %.3f  "
          "超额 %+.1f%%  (90%%区间 %.3f-%.3f)"
          % (nm, s, wk, act, exp, 100 * (act - exp) / max(exp, 1e-9),
             row.p_lo, row.p_hi))
print()

# ── 3. 因素拆解 ──
print("  === 因素与 placement 的关系（Spearman）===")
for f in ("judge_avg", "age", "n_weeks", "judge_max", "judge_min"):
    print("    %-12s rho=%+.3f" % (f, W[[f, "placement"]].corr(method="spearman").iloc[0, 1]))
ind = W.groupby("industry").placement.agg(["mean", "count"]).sort_values("mean")
print("    行业均值 placement 最高的 5 类（越靠后名次越差）:")
for k, v in ind.tail(5).iterrows():
    print("      %-24s mean %.2f  n=%d" % (str(k)[:24], v["mean"], v["count"]))
pd_w = W.groupby("pro_dancer").placement.agg(["mean", "count"])
pd_w = pd_w[pd_w["count"] >= 3].sort_values("mean")
print("    pro dancer 数量 %d（出现>=3 次的 %d 位）"
      % (W.pro_dancer.nunique(), len(pd_w)))