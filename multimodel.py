#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multimodel.py —— 三个性能指标分别建代理模型（第 5 轮查出的核心缺陷）

问题
----
题目问题 1 要求「分析三因子对**三项指标**的影响规律」，
问题 2 要求「建立代理模型，评估拟合与预测效果」。

实测：我们只对**热阻**跑了 mm.fit，压降和温度非均匀性从没建过模。
而且 —— 三个指标的正确模型形式并不相同：

    热阻       CV 选线性   (0.007434 vs 二次 0.008796)
    压降       CV 选二次   (0.007658 vs 线性 0.014207，改善 46%)
    温度非均匀  CV 选二次   (0.011957 vs 线性 0.019103，改善 37%)

所以「二次比线性差 18.3%」这句话**只对热阻成立**。
把它写成对三个指标都成立，是过度推广。

做法
----
每个指标独立跑完整的候选集竞速（线性/二次/对数/幂律/岭），
按 CV-RMSE 选，并把「每个指标选了谁、改善多少」做成一张表。
"""

from __future__ import annotations

import numpy as np


def fit_all(ds, ys, xs, translate=None) -> dict:
    """对每个指标独立建模，返回对比表。

    ys: 指标列名列表
    xs: 因子列名列表
    """
    import mm as _mm
    tr = translate or (lambda x: str(x))
    rows = []
    for yc in ys:
        r = _mm.fit(ds, yc, xs)
        best = r.get("best") or {}
        cands = [(c.get("label"), float(c["rmse"]))
                 for c in (r.get("cands") or []) if c.get("rmse") is not None]
        cands.sort(key=lambda t: t[1])
        lin = next((v for lab, v in cands
                    if "线性" in str(lab) or str(lab).lower().startswith(
                        "linear")), None)
        rows.append(dict(
            y=yc,
            y_en=tr(yc),
            best_label=str(best.get("label") or ""),
            best_label_en=tr(str(best.get("label") or "")),
            best_rmse=float(best.get("rmse") or 0.0) or None,
            linear_rmse=lin,
            gain=(1.0 - float(best.get("rmse") or 0.0) / lin)
            if (lin and best.get("rmse")) else 0.0,
            n_cands=len(cands),
            top=[(str(l), float(v)) for l, v in cands[:3]],
            is_linear=("线性" in str(best.get("label") or "")
                       or str(best.get("label") or "").lower().startswith(
                           "linear")),
        ))
    # 三个指标是不是都选了同一种形式
    forms = {r["best_label"] for r in rows}
    return dict(rows=rows,
                n=int(len(rows)),
                uniform=(len(forms) == 1),
                forms=sorted(forms))


def summary_lines(res: dict) -> list:
    """把对比表变成论文可用的结论句（英文，供 paper.py 拼接）。"""
    L = []
    rows = res.get("rows") or []
    if not rows:
        return L
    if res.get("uniform"):
        L.append(
            f"All {res['n']} performance indicators select the same "
            f"specification, "
            f"{rows[0].get('best_label_en') or rows[0]['best_label']}, "
            f"under "
            f"cross-validation. That uniformity is itself a finding: it "
            f"means the three indicators respond to the geometry in the "
            f"same functional form, so one structural argument covers "
            f"all three rather than three separate ones.")
    else:
        parts = []
        for r in rows:
            if r["is_linear"]:
                parts.append(f"{r.get('y_en') or r['y']} selects the "
                             f"linear form")
            else:
                parts.append(
                    f"{r.get('y_en') or r['y']} selects "
                    f"{r.get('best_label_en') or r['best_label']}, "
                    f"lowering the "
                    f"cross-validated error by {r['gain']:.0%} against "
                    f"the linear form")
        L.append(
            "The three indicators do not agree on a functional form. "
            + "; ".join(parts) + ". Reporting one specification for all "
            "three would therefore be wrong for at least one of them, "
            "which is why each is modelled and reported separately.")
    return L
