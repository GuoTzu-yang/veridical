#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
q5.py —— 问题 5：加工误差与工况波动对**选定设计**的影响

题目原文
--------
「考虑加工误差及运行工况波动等实际因素，在前述研究基础上分析关键参数
  小范围扰动对系统性能的影响，评估设计方案的敏感性与稳定性。」

与已做过的两件事的区别
----------------------
· mm.sens    全局扫每个因子 ±30%，看输出怎么动 —— 回答「哪个因子重要」
· robustness 响应做 log/sqrt 变换，看符号是否翻转 —— 回答「结论是不是尺度的产物」
· **本模块**  在**选定的那一个设计点**上加加工误差 —— 回答「这个设计站不站得住」

第三件事是题目问的。前两件都不能替代它：全局扫描看不出边界效应，
变换检验与几何误差无关。

实测的设计点（minimax regret，行 47）：
    针肋宽度比 0.20    歧管深高比 4.50    排数 6
歧管深高比恰好落在取值上界 —— 正向误差直接越界，这一点必须报出来。
"""

from __future__ import annotations

import numpy as np


def fit_surrogates(ds, ys, xs) -> dict:
    """每个指标一个线性代理模型（局部扰动下线性近似足够，且可解释）。"""
    X = np.column_stack([np.asarray(ds.col(c), dtype=float) for c in xs])
    out = {}
    for yc in ys:
        y = np.asarray(ds.col(yc), dtype=float)
        A = np.column_stack([np.ones(len(y)), X])
        b, *_ = np.linalg.lstsq(A, y, rcond=None)
        out[yc] = b
    return out


def design_sensitivity(ds, xs, ys, row, pcts=(0.01, 0.05, 0.10),
                       n=4000, seed=0) -> dict:
    """在选定设计点上按 ±pct 均匀加扰动，统计性能漂移与越界概率。

    参数
    ----
    row  : 设计点在数据里的行号
    pcts : 相对扰动幅度列表（加工误差的典型量级）

    返回每个幅度下：各指标的相对漂移、超出 5% 容差的概率、越界概率。
    """
    rng = np.random.default_rng(seed)
    coefs = fit_surrogates(ds, ys, xs)
    base = np.array([float(np.asarray(ds.col(c), dtype=float)[row])
                     for c in xs])
    y_base = {yc: float(np.asarray(ds.col(yc), dtype=float)[row])
              for yc in ys}

    # 因子的取值区间 —— 用来判断扰动是否出界
    lo = np.array([float(np.asarray(ds.col(c), dtype=float).min())
                   for c in xs])
    hi = np.array([float(np.asarray(ds.col(c), dtype=float).max())
                   for c in xs])
    at_bound = [(xs[i], base[i], lo[i], hi[i])
                for i in range(len(xs))
                if abs(base[i] - hi[i]) < 1e-9 or abs(base[i] - lo[i]) < 1e-9]

    rows = []
    for p in pcts:
        # 均匀扰动（加工误差通常按公差带均匀分布，不是正态）
        dev = rng.uniform(-p, p, size=(n, len(xs)))
        Xs = base * (1.0 + dev)
        # 越界：超出观测到的因子范围
        oob = ((Xs < lo - 1e-12) | (Xs > hi + 1e-12)).any(axis=1)

        per = {}
        for yc in ys:
            b = coefs[yc]
            pred = b[0] + Xs @ b[1:]
            rel = (pred - y_base[yc]) / abs(y_base[yc])
            per[yc] = dict(
                drift_mean=float(rel.mean()),
                drift_abs_mean=float(np.abs(rel).mean()),
                drift_p95=float(np.percentile(np.abs(rel), 95)),
                exceed_5pct=float((np.abs(rel) > 0.05).mean()),
                # 最坏方向：这个指标越小越好，所以正向漂移才是坏事
                worse_prob=float((rel > 0.0).mean()),
            )
        rows.append(dict(pct=p, oob=float(oob.mean()), per=per))

    return dict(xs=list(xs), ys=list(ys), row=int(row),
                base=[float(v) for v in base],
                y_base=y_base,
                at_bound=at_bound,
                n_sample=n, rows=rows)


def required_tolerance(res: dict, tol: float = 0.05) -> dict:
    """反推：要让越界概率降到目标水平，加工公差应收到多紧。

    这是问题 5 的落地结论 —— 只说「敏感」没用，要说「公差该多紧」。
    """
    out = {}
    for r in res.get("rows") or []:
        if r["oob"] <= tol:
            out["pct"] = r["pct"]
            out["oob"] = r["oob"]
            return out
    rows = res.get("rows") or []
    if rows:
        last = rows[-1]
        # 越界概率近似与扰动幅度成正比，按比例外推
        if last["oob"] > 0:
            est = last["pct"] * tol / last["oob"]
            out = dict(pct=est, oob=tol, extrapolated=True)
    return out


def margin_tradeoff(ds, xs, ys, row, factor, target) -> dict:
    """把边界上的那个因子移到 target，三指标各付多少代价。

    问题 5 不能只说「设计在边界上不稳定」，要说清移动它的代价。
    用线性系数做局部预测（位移在因子跨度内，线性近似够用），
    并明确标注这是局部近似。
    """
    coefs = fit_surrogates(ds, ys, xs)
    i = list(xs).index(factor) + 1
    fvals = [float(np.asarray(ds.col(c), dtype=float)[row]) for c in xs]
    x0 = fvals[i - 1]
    out = {}
    for yc in ys:
        b = coefs[yc]
        y0 = float(np.asarray(ds.col(yc), dtype=float)[row])
        y1 = float(b[0] + sum(b[j + 1] * (target if j == i - 1 else fvals[j])
                             for j in range(len(xs))))
        out[yc] = dict(base=y0, moved=y1,
                       rel=(y1 - y0) / abs(y0) if y0 else 0.0)
    return dict(factor=factor, frm=x0, to=target,
                shift=(target - x0) / abs(x0) if x0 else 0.0,
                per=out, linear_approx=True)


def summary(res: dict, translate=None) -> list:
    """论文用的结论句（英文）。"""
    tr = translate or (lambda x: str(x))
    L = []
    rows = res.get("rows") or []
    if not rows:
        return L
    ab = res.get("at_bound") or []
    if ab:
        names = ", ".join(f"{tr(n)} at {v:.4g} (range {a:.4g} to {b:.4g})"
                          for n, v, a, b in ab)
        L.append(
            f"The selected design sits on the boundary of the tested range "
            f"for {names}. Any positive manufacturing deviation therefore "
            f"leaves the region in which the surrogate was fitted, and the "
            f"prediction there is an extrapolation rather than an "
            f"interpolation. This is a property of the design, not of the "
            f"analysis: a design placed at a bound has no margin on that "
            f"side.")
    worst = max(rows, key=lambda r: r["oob"]) if rows else None
    if worst:
        L.append(
            f"At a uniform tolerance of {worst['pct']:.0%} on every "
            f"dimension, {worst['oob']:.0%} of manufactured units fall "
            f"outside the tested range on at least one dimension.")
    # 哪个指标漂移最大
    if rows:
        last = rows[-1]
        per = last["per"]
        top = max(per.items(), key=lambda kv: kv[1]["drift_abs_mean"])
        L.append(
            f"Among the performance indicators, {tr(top[0])} drifts most: at "
            f"{last['pct']:.0%} tolerance its mean absolute deviation is "
            f"{top[1]['drift_abs_mean']:.1%}, with 95th percentile "
            f"{top[1]['drift_p95']:.1%}. That ordering tells the process "
            f"engineer which dimension to tighten first, which is a more "
            f"useful output than a single sensitivity number.")
    return L
