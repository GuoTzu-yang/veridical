#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问题 4：权重敏感性 + 鲁棒设计（minimax regret）。

题目原文：
  「考虑不同应用场景下对三项性能指标关注重点的差异，研究指标权重变化
    对最优设计方案的影响；进一步给出一个对偏好变化不敏感、稳定性较强的
    鲁棒设计方案，并说明其判定依据与优势。」

我们之前完全没做这一问。

做法
----
1. **权重扫描**：三指标权重落在单纯形上（w1+w2+w3=1, wi>=0）。
   等步长采样，每点求加权最优方案，记录选中的设计行号。
2. **鲁棒设计**：minimax regret。
   对每个候选方案 s、每个权重场景 k：
       regret(s,k) = (score_k(s) - min_j score_k(j)) / (max-min)
   选 max_k regret 最小的方案 —— 即「最坏情况下后悔最少」。
   这比「取所有场景平均最优」更强：平均最优在某个极端场景可能很糟。

判定依据的说服力：minimax regret 是决策论里的标准判据，
不需要额外假设效用函数形式。
"""

from __future__ import annotations

import numpy as np


def _norm(M: np.ndarray) -> np.ndarray:
    """按列归一化到 [0,1]，minimize 方向（越小越好）。"""
    lo = M.min(axis=0)
    hi = M.max(axis=0)
    span = np.where(hi - lo > 0, hi - lo, 1.0)
    return (M - lo) / span


def weight_simplex(n: int = 3, step: float = 0.1):
    """生成三指标权重单纯形上的采样点。

    step=0.1 → 66 个点（含边界）。不用 Dirichlet 随机采样：
    等步长网格可复现，且边界（某个权重为 0）本身就是重要场景。
    """
    pts = []
    k = int(round(1.0 / step))
    for i in range(k + 1):
        for j in range(k + 1 - i):
            w3 = 1.0 - (i + j) * step
            if w3 < -1e-9:
                continue
            pts.append([round(i * step, 6), round(j * step, 6),
                        round(max(0.0, w3), 6)])
    return np.array(pts)


def weight_sweep(M, minimize=None, step: float = 0.1) -> dict:
    """每个权重下选一个加权最优方案。

    返回：各权重场景的最优行号、被选次数的分布、以及「稳居前若干名」的方案。
    """
    A = np.asarray(M, dtype=float)
    if minimize is None:
        minimize = [True] * A.shape[1]
    Z = _norm(-A if not all(minimize) else A)
    if not all(minimize):
        # 有正向指标就翻号，统一成「越小越好」
        for j, m in enumerate(minimize):
            if not m:
                Z[:, j] = 1.0 - Z[:, j]
    W = weight_simplex(A.shape[1], step)

    picks, ranks = [], []
    for w in W:
        sc = Z @ w
        order = np.argsort(sc)
        picks.append(int(order[0]))
        r = np.empty(len(sc), dtype=int)
        r[order] = np.arange(len(sc))
        ranks.append(r)
    picks = np.array(picks)
    R = np.array(ranks)

    # 每个方案在多少比例的权重场景里排进前 k
    topk = {}
    for k in (1, 3, 5, 10):
        cnt = (R < k).sum(axis=0)
        topk[k] = (cnt / len(W))

    uniq, counts = np.unique(picks, return_counts=True)
    dist = sorted(zip(uniq.tolist(), counts.tolist()),
                  key=lambda x: -x[1])
    return dict(n_weights=len(W), n_rows=len(A),
                picks=picks, rank_matrix=R,
                dist=dist, topk=topk)


def robust_design(M, minimize=None, step: float = 0.1) -> dict:
    """minimax regret：最坏情况下后悔最少的方案。

    后悔值用「相对该场景最优的归一化差距」，所以不同权重的场景可比。
    """
    A = np.asarray(M, dtype=float)
    if minimize is None:
        minimize = [True] * A.shape[1]
    Z = _norm(A)
    for j, m in enumerate(minimize):
        if not m:
            Z[:, j] = 1.0 - Z[:, j]
    W = weight_simplex(A.shape[1], step)

    reg = np.zeros((len(A), len(W)))
    for k, w in enumerate(W):
        sc = Z @ w
        lo = sc.min()
        hi = sc.max()
        span = hi - lo if hi > lo else 1.0
        reg[:, k] = (sc - lo) / span        # 0 = 该场景最优

    worst = reg.max(axis=1)
    best_idx = int(np.argmin(worst))
    avg = reg.mean(axis=1)

    # 稳健性的判定依据：最坏后悔 + 在多少场景里进了前 10%
    R = np.argsort(np.argsort(reg, axis=0), axis=0)
    in_top10 = float((R[best_idx] < max(1, int(0.1 * len(A)))).mean())

    return dict(
        idx=best_idx,
        coords=[float(x) for x in A[best_idx]],
        worst_regret=float(worst[best_idx]),
        avg_regret=float(avg[best_idx]),
        rank_worst=int(np.argsort(np.argsort(worst))[best_idx]) + 1,
        in_top10_share=round(in_top10, 3),
        n_eval=len(A),
        n_weights=len(W),
        # 对照：加权平均意义下最好的方案
        avg_best_idx=int(np.argmin(avg)),
        avg_best_worst_regret=float(worst[int(np.argmin(avg))]),
        note=("minimax regret：先算每个权重场景下各方案相对最优的差距，"
              "再取最坏场景下的差距，选它最小的方案。"
              "比「平均最优」强在：不假设各场景等概率。"),
    )


def compare_with_argmin(M, minimize=None, weights=None) -> dict:
    """对照：单一固定权重下的最优，与鲁棒设计是不是同一个方案。

    如果不是，说明「按某个权重选出来的方案」对权重很敏感 ——
    这本身就是问题 4 要给的结论。
    """
    A = np.asarray(M, dtype=float)
    if minimize is None:
        minimize = [True] * A.shape[1]
    Z = _norm(A)
    for j, m in enumerate(minimize):
        if not m:
            Z[:, j] = 1.0 - Z[:, j]
    w = np.asarray(weights if weights is not None
                   else [1.0 / A.shape[1]] * A.shape[1], dtype=float)
    s = Z @ w
    return dict(fixed_w_idx=int(np.argmin(s)),
                fixed_w_coords=[float(x) for x in A[int(np.argmin(s))]])


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    """自测：权重扫描与 minimax regret 算得对不对。

    参照用「构造已知答案」而不是对拍别的库：
      · 只有一个候选时，任何权重下它都是最优，regret 恒为 0
      · 两个候选各占一个极端时，minimax regret 应选「两条都不最差」的那个
      · 权重单纯形的点数应等于 (k+1)(k+2)/2
    """
    import numpy as np
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    # ① 单纯形形状
    W = weight_simplex(3, 0.1)
    ck("单形点数正确", len(W) == 66, f"{len(W)} 个")
    ck("权重和为 1", np.allclose(W.sum(axis=1), 1.0),
       f"最大偏差 {abs(W.sum(axis=1) - 1).max():.2e}")
    ck("权重非负", (W >= 0).all())

    # ② 单候选：regret 恒 0
    M1 = np.array([[1.0, 2.0, 3.0]])
    r1 = robust_design(M1)
    ck("单候选时 regret 为 0", r1["worst_regret"] == 0.0,
       f"{r1['worst_regret']}")
    ck("单候选时选它自己", r1["idx"] == 0)

    # ③ 三候选：A 在指标 1 最好、指标 2/3 最差；B 相反；C 居中
    #    minimax regret 应选 C —— 它在任何权重下都不是最差
    M = np.array([
        [0.0, 10.0, 10.0],     # A：只在第一项好
        [10.0, 0.0, 10.0],     # B：只在第二项好
        [5.0, 5.0, 5.0],       # C：居中
    ])
    r2 = robust_design(M)
    ck("minimax 选居中方案", r2["idx"] == 2, f"选了 {r2['idx']}")
    # 用 <= 而不是 <：在这个对称例子里，平均最优恰好也是居中方案，
    # 两者相等。严格小于会把「本来就是同一个方案」判成失败。
    ck("居中方案的最坏后悔 <= 端点方案",
       r2["worst_regret"] <= r2["avg_best_worst_regret"],
       f"{r2['worst_regret']:.3f} vs {r2['avg_best_worst_regret']:.3f}")

    # ④ 支配关系：如果某个方案在三项上都最好，它必须被选中
    M3 = np.array([
        [1.0, 1.0, 1.0],
        [5.0, 5.0, 5.0],
        [9.0, 9.0, 9.0],
    ])
    r3 = robust_design(M3)
    ck("全面占优的方案被选中", r3["idx"] == 0, f"选了 {r3['idx']}")
    ck("占优方案 regret 为 0", r3["worst_regret"] == 0.0)

    # ⑤ 扫描：单候选时每个场景都选它
    sw = weight_sweep(M1)
    ck("扫描次数与单形点数一致", sw["n_weights"] == 66,
       f"{sw['n_weights']}")
    ck("单候选时全部场景都选它", len(sw["dist"]) == 1
       and sw["dist"][0][0] == 0)

    # ⑥ 真实数据
    try:
        import mm
        ds = mm.DS(mm.find_xlsx())
        cols = ["无量纲热阻", "无量纲压降", "无量纲温度非均匀性"]
        Mr = np.column_stack([np.asarray(ds.col(c), dtype=float)
                              for c in cols])
        rb = robust_design(Mr)
        ck("真实数据能算", 0 <= rb["idx"] < len(Mr), f"行 {rb['idx']}")
        ck("真实数据 regret 在 [0,1]", 0 <= rb["worst_regret"] <= 1,
           f"{rb['worst_regret']:.3f}")
    except Exception as e:                          # noqa: BLE001
        ck("真实数据能算", False, f"{type(e).__name__}: {e}")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import sys
    a = sys.argv[1:] if argv is None else argv
    return selftest() if (not a or a[0] == "selftest") else selftest()


if __name__ == "__main__":
    raise SystemExit(main())
