"""论文里三个「辅助断言」的实算来源。

1. A5 的通过率：placement 是否等于淘汰那周的在场人数
2. 舞伴效应：placement 对 partner 的单因素方差分析 F 与置换 p
3. 排除退赛者后的稳健性（样本量 411，各秩相关的最大偏移）

这些数原先在论文里是定性陈述（"verified against the data" / "larger than"），
2026-11-10 改为给数，故单独成脚本，供 merge_model_stats_into_freeze.py 读取。
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")


def spear(a, b):
    ra = pd.Series(a).rank().to_numpy(float)
    rb = pd.Series(b).rank().to_numpy(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    W = pd.read_excel(os.path.join(D, "dwts2026c.xlsx"))
    L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
    out = {}

    # ── 1. A5：placement == 淘汰周在场人数 ──
    el = W[(W.eliminated_week > 0) & (W.withdrew == 0)]
    ok = 0
    bad_seasons = set()
    for _, r in el.iterrows():
        wk = int(r.eliminated_week)
        g = L[(L.season == r.season) & (L.week == wk)]
        g = g[g.judge_score > 0]          # 剔除缺席填 0
        if int(r.placement) == len(g):
            ok += 1
        else:
            bad_seasons.add(int(r.season))
    out["a5_holds"] = int(ok)
    out["a5_total"] = int(len(el))
    out["a5_rate"] = round(100.0 * ok / max(1, len(el)), 1)
    out["a5_violating_seasons"] = int(len(bad_seasons))

    # ── 2. 舞伴效应：单因素 F + 置换 p ──
    g = W.dropna(subset=["pro_dancer", "placement"])
    y = g.placement.to_numpy(float)
    lab = g.pro_dancer.to_numpy()

    def F_of(yy):
        grand = yy.mean()
        k = len(set(lab))
        n = len(yy)
        means = pd.Series(yy).groupby(lab).transform("mean").to_numpy()
        ssb = float(((means - grand) ** 2).sum())
        ssw = float(((yy - means) ** 2).sum())
        return (ssb / (k - 1)) / (ssw / (n - k))

    F0 = F_of(y)
    rng = np.random.default_rng(2026)
    N = 5000
    cnt = sum(1 for _ in range(N) if F_of(rng.permutation(y)) >= F0)
    out["partner_F"] = round(float(F0), 2)
    out["partner_p"] = round((cnt + 1) / (N + 1), 3)
    out["permutation_draws"] = N

    # ── 3. 排除退赛者后的稳健性 ──
    W0 = W[W.withdrew == 0]
    out["n_non_withdrawing"] = int(len(W0))
    vars_ = ("judge_avg", "age", "n_weeks", "judge_max", "judge_min")
    shifts = []
    for v in vars_:
        d1 = W[[v, "placement"]].dropna()
        d2 = W0[[v, "placement"]].dropna()
        r1 = spear(d1[v].to_numpy(float), d1.placement.to_numpy(float))
        r2 = spear(d2[v].to_numpy(float), d2.placement.to_numpy(float))
        shifts.append(abs(r1 - r2))
    out["max_rho_shift_excl_withdrawals"] = round(float(max(shifts)), 3)

    p = os.path.join(D, "c2026c_aux_stats.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\n写出 %s" % p)


if __name__ == "__main__":
    main()
