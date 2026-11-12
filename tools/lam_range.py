"""λ 可行宽度的**精确**范围（替代抽样估计）。

问题
----
论文报的 feasible width 是「1500 次抽样里 lam_hi - lam_lo」，只能低估真范围。
red-stats 用解析法得真实 min–max 宽度中位数 = 0.8241，而抽样只有 0.494，
低估约 40%。本脚本独立复现精确值，用于判断论文要不要改口径。

为什么可以精确算
----------------
λ = Σ Jn_i p_i 对 p **线性**，所以极值在可行域顶点。
可行域只有下界型约束：
    p_i >= eps                                （份额非负下限）
    p_i >= p_e - (Jn_i - Jn_e)   for i != e   （淘汰者综合分最低）
    Σ p_i = 1
固定 p_e 之后，其余每个 p_i 都有一个下界 lo_i(p_e)。因为目标线性且只有下界，
最优必是「所有人取下界，剩余份额全部给 Jn 最大（或最小）的那个人」——
这是贪心，不是近似。于是只需在 p_e 的一维可行区间端点比较，得精确极值。

用法
    python tools/lam_range.py            # 对照表：抽样 vs 精确
    python tools/lam_range.py --json
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")
EPS = 0.003


def exact_range(Jn, e, eps=EPS):
    """返回 (lam_min, lam_max)，在可行域上精确取到。"""
    n = len(Jn)
    d = Jn - Jn[e]

    def lo_of(pe):
        return np.array([max(eps, pe - d[i]) for i in range(n)])

    def feasible(pe):
        lo = lo_of(pe)
        lo[e] = pe
        return lo.sum() <= 1.0 + 1e-12

    if not feasible(eps):
        return None
    # p_e 越大，下界和越大；二分找最大可行 p_e
    a, b = eps, 1.0
    if feasible(b):
        pe_hi = b
    else:
        for _ in range(100):
            m = 0.5 * (a + b)
            if feasible(m):
                a = m
            else:
                b = m
        pe_hi = a

    best_min, best_max = np.inf, -np.inf
    for pe in (eps, pe_hi):
        lo = lo_of(pe)
        lo[e] = pe
        rest = 1.0 - lo.sum()
        if rest < -1e-9:
            continue
        others = [i for i in range(n) if i != e]
        for pick_max in (True, False):
            p = lo.copy()
            j = (max if pick_max else min)(others, key=lambda i: Jn[i])
            p[j] += rest
            lam = float(np.dot(Jn, p))
            if lam < best_min:
                best_min = lam
            if lam > best_max:
                best_max = lam
    if not np.isfinite(best_min):
        return None
    return best_min, best_max


def main(as_json=False):
    L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
    LAM = pd.read_csv(os.path.join(HERE, "out", "fanvote_lam.csv"))
    rows = []
    for (s, w), g in L.groupby(["season", "week"]):
        g = g.dropna(subset=["judge_score"])
        g = g[g.judge_score > 0]
        if len(g) < 3 or int(g.eliminated.sum()) != 1:
            continue
        # 与 final_bounds 一致：按 placement 升序，淘汰者是那一行
        g = g.sort_values("final_placement")
        J = g.judge_score.to_numpy(float)
        Jn = ((J - J.min()) / (J.max() - J.min())) if J.max() > J.min() else np.zeros(len(J))
        e = int(np.where(g.eliminated.to_numpy() == 1)[0][0])
        r = exact_range(Jn, e)
        if r is None:
            continue
        rows.append(dict(season=int(s), week=int(w), n=len(g),
                         exact_lo=r[0], exact_hi=r[1],
                         exact_width=r[1] - r[0]))
    E = pd.DataFrame(rows)

    # 抽样值（论文现在用的）
    samp = LAM[(LAM.method == "pct") & (LAM.ok == 1)].copy()
    samp["width"] = samp.lam_hi - samp.lam_lo
    med_samp = float(samp.width.median())

    # 对齐到同样的周（season, week）
    key = ["season", "week"]
    M = E.merge(samp[key + ["width"]], on=key, how="inner", suffixes=("", "_samp"))
    med_exact = float(M.exact_width.median())
    med_shift = float(M.width.median())

    out = dict(
        weeks_exact=len(E),
        weeks_matched=len(M),
        median_exact_width=round(med_exact, 4),
        median_sampled_width=round(med_shift, 4),
        median_paper_value=round(med_samp, 4),
        understatement_pct=round(100.0 * (1 - med_shift / med_exact), 1)
        if med_exact > 0 else None,
        samples_never_exceed_exact=bool((M.width <= M.exact_width + 1e-9).mean() > 0.99),
    )
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print("λ 可行宽度：抽样估计 vs 精确解")
    print("  可精确求解的季-周：%d" % len(E))
    print("  与抽样结果可对齐的：%d" % len(M))
    print()
    print("  抽样 min–max 中位数 : %.4f   （论文报的是 %.4f）"
          % (med_shift, med_samp))
    print("  精确 min–max 中位数 : %.4f" % med_exact)
    print("  抽样低估            : %.1f%%" % out["understatement_pct"])
    print()
    print("  抽样 >= 精确 的比例 : %.1f%%（应接近 0，否则精确解有误）"
          % (100.0 * (M.width > M.exact_width + 1e-9).mean()))
    print()
    print("  逐周对照（前 6 行）：")
    print(M.head(6)[["season", "week", "n", "width", "exact_width"]]
          .rename(columns={"width": "sampled", "exact_width": "exact"})
          .to_string(index=False))
    p = os.path.join(D, "c2026c_lam_exact.csv")
    E.to_csv(p, index=False)
    print("\n  写出 %s" % p)


if __name__ == "__main__":
    import sys
    main("--json" in sys.argv)
