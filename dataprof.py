#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dataprof.py —— 数据质量画像（第 20 轮）

为什么要它
----------
方法映射表显示：56 条方法分支里 25 条映射不到命令，其中最常用的一类是
「数据预处理」（缺失值 / 异常值 / 特征选择）。

但 mm.py 里只有一个私有的 _normalize，清洗逻辑散落在 run() 内部 ——
它能删缺失行，但不告诉你**该不该删、删了多少、还剩什么隐患**。

这个模块回答四个问题：
    1. 每列缺多少、有没有异常值（IQR 法）
    2. 分布偏不偏（偏度/峰度）→ 决定要不要变换
    3. 量纲是否悬殊 → 决定要不要标准化
    4. 因子间是否共线（条件数）→ 决定系数能不能解释

每条结论都带数字，能直接写进论文的「数据预处理」一节。

用法
    python dataprof.py out/prof.json
    python dataprof.py selftest
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _skew(x: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    m = x.mean()
    s = x.std(ddof=0)
    if s == 0:
        return 0.0
    return float(((x - m) ** 3).mean() / (s ** 3))


def _kurt(x: np.ndarray) -> float:
    """超额峰度（正态为 0）。"""
    n = len(x)
    if n < 4:
        return 0.0
    m = x.mean()
    s = x.std(ddof=0)
    if s == 0:
        return 0.0
    return float(((x - m) ** 4).mean() / (s ** 4) - 3.0)


def col_profile(x, name: str) -> dict:
    """单列的画像。"""
    arr = np.asarray([v for v in x if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    n_obs = len(x)
    n_bad = n_obs - len(arr)
    d = dict(name=name, n=n_obs, n_missing=n_bad,
             missing_rate=round(n_bad / n_obs, 4) if n_obs else 0.0)
    if len(arr) < 2:
        d.update(dict(ok=False, why="有效值不足两个"))
        return d

    q1, q3 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = int(((arr < lo) | (arr > hi)).sum())

    d.update(dict(
        ok=True,
        mean=round(float(arr.mean()), 6),
        std=round(float(arr.std(ddof=1)) if len(arr) > 1 else 0.0, 6),
        min=round(float(arr.min()), 6),
        max=round(float(arr.max()), 6),
        span=round(float(arr.max() - arr.min()), 6),
        q1=round(q1, 6), q3=round(q3, 6), iqr=round(iqr, 6),
        n_outlier=n_out, outlier_rate=round(n_out / len(arr), 4),
        iqr_fence=[round(lo, 6), round(hi, 6)],
        skew=round(_skew(arr), 4), kurt=round(_kurt(arr), 4),
        n_unique=len(set(arr.tolist())),
        is_constant=bool(arr.std(ddof=0) == 0),
    ))
    return d


def condition_numbers(ds, cols=None) -> dict:
    """设计矩阵条件数：原始 / 标准化后，两个都报。

    为什么必须报两个：原始条件数会把**量纲差异**当成共线。
    实测踩到 —— B 题三列跨度 0.3/1.5/10，原始条件数 1447，
    但标准化后只有 1.4，说明因子几乎是正交的。
    只看原始值会得出「严重共线、系数不可解释」这种错误结论。
    """
    names = cols or [c for c in ds.num_names if "编号" not in c]
    if len(names) < 2:
        return dict(raw=None, scaled=None)
    try:
        X = np.column_stack([np.asarray(ds.col(c), dtype=float)
                             for c in names])
        A = np.column_stack([np.ones(len(X)), X])
        s = np.linalg.svd(A, compute_uv=False)
        raw = float(s[0] / s[-1]) if s[-1] > 0 else float("inf")
        # 标准化（按列 z-score）后重算
        mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd == 0] = 1.0
        Z = (X - mu) / sd
        B = np.column_stack([np.ones(len(Z)), Z])
        s2 = np.linalg.svd(B, compute_uv=False)
        scaled = float(s2[0] / s2[-1]) if s2[-1] > 0 else float("inf")
        return dict(raw=round(raw, 2), scaled=round(scaled, 2),
                    names=names)
    except Exception:                               # noqa: BLE001
        return dict(raw=None, scaled=None)


def condition_number(ds, cols=None) -> float | None:
    """兼容旧接口：返回**标准化后**的条件数（那才是共线的判据）。"""
    return condition_numbers(ds, cols).get("scaled")


def profile(ds) -> dict:
    """整份数据的画像。"""
    cols = [col_profile(ds.col(c), c) for c in ds.num_names]
    ok = [c for c in cols if c.get("ok")]
    _cn = condition_numbers(ds)
    cond = _cn.get("scaled")        # 共线判据用标准化后的
    cond_raw = _cn.get("raw")

    # 量纲悬殊：最大跨度 / 最小跨度
    spans = [c["span"] for c in ok if c["span"] > 0]
    ratio = round(max(spans) / min(spans), 2) if len(spans) >= 2 else None

    return dict(
        n_rows=ds.n_rows, n_cols=len(ds.num_names),
        columns=cols,
        cond=cond, cond_raw=cond_raw,
        span_ratio=ratio,
        n_missing_total=sum(c["n_missing"] for c in cols),
        n_outlier_total=sum(c.get("n_outlier", 0) for c in ok),
        n_constant=[c["name"] for c in ok if c.get("is_constant")],
    )


def advice(p: dict) -> list:
    """按画像给建议。每条都带数字，不是套话。"""
    out = []
    for c in p["columns"]:
        if not c.get("ok"):
            continue
        if c["missing_rate"] > 0.2:
            out.append(f"{c['name']}：缺失 {c['missing_rate']:.0%}，"
                       f"直接删行会丢太多，考虑插值或剔除该列")
        elif c["missing_rate"] > 0:
            out.append(f"{c['name']}：缺失 {c['n_missing']} 行"
                       f"（{c['missing_rate']:.1%}），删行可接受")
        if c["outlier_rate"] > 0.05:
            out.append(f"{c['name']}：IQR 判出 {c['n_outlier']} 个异常值"
                       f"（{c['outlier_rate']:.1%}），需说明是删、截尾还是保留")
        if abs(c["skew"]) > 1:
            out.append(f"{c['name']}：偏度 {c['skew']:+.2f}，"
                       f"建议取对数或做变换后再建模")
        if c["is_constant"]:
            out.append(f"{c['name']}：全列同值，应剔除")
    # 共线判据用标准化后的条件数 —— 原始值会把量纲差异误报成共线
    if p.get("cond") and p["cond"] > 1000:
        out.append(f"标准化后条件数 {p['cond']:.0f} > 1000，"
                   f"因子真的共线，单个系数不可解释（预测仍可能准）")
    elif p.get("cond") and p["cond"] > 30:
        out.append(f"标准化后条件数 {p['cond']:.0f}，轻度共线，"
                   f"解释系数时需谨慎")
    elif p.get("cond") and p.get("cond_raw") and p["cond_raw"] > 100:
        out.append(f"原始条件数 {p['cond_raw']:.0f} 但标准化后只有 "
                   f"{p['cond']:.1f} —— 高值来自量纲差异，"
                   f"不是共线；不要据此说系数不可解释")
    if p.get("span_ratio") and p["span_ratio"] > 1000:
        out.append(f"各列跨度相差 {p['span_ratio']:.0f} 倍，"
                   f"做距离类方法（聚类/近邻）前必须标准化")
    if not out:
        out.append("数据质量无明显问题")
    return out


def report(p: dict) -> str:
    L = [f"数据画像：{p['n_rows']} 行 × {p['n_cols']} 列　"
         f"缺失 {p['n_missing_total']} 个　异常 {p['n_outlier_total']} 个",
         f"条件数 原始 {p.get('cond_raw')} / 标准化 {p['cond']}　"
         f"跨度比 {p['span_ratio']}", ""]
    L.append(f"  {'列名':<16}{'缺失':>6}{'异常':>6}{'偏度':>8}"
             f"{'跨度':>12}{'唯一值':>8}")
    for c in p["columns"]:
        if not c.get("ok"):
            L.append(f"  {c['name'][:14]:<16}{'—':>6}{'—':>6}{'—':>8}"
                     f"{'—':>12}{'—':>8}")
            continue
        L.append(f"  {c['name'][:14]:<16}{c['n_missing']:>6}"
                 f"{c['n_outlier']:>6}{c['skew']:>8.2f}"
                 f"{c['span']:>12.4g}{c['n_unique']:>8}")
    L.append("")
    L.append("建议：")
    for a in advice(p):
        L.append(f"  · {a}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    rng = np.random.default_rng(0)

    # 单列：正常
    d = col_profile(list(rng.normal(0, 1, 100)), "normal")
    ck("正常列能画像", d["ok"] and d["n"] == 100, f"n={d['n']}")
    ck("正态列偏度接近 0", abs(d["skew"]) < 0.6, f"{d['skew']:+.3f}")
    ck("正态列异常值占比 <5%", d["outlier_rate"] < 0.05,
       f"{d['outlier_rate']:.1%}")

    # 单列：缺失 + 异常
    x = list(rng.normal(0, 1, 100))
    x[0] = np.nan
    x[1] = np.nan
    x[2] = 50.0
    d2 = col_profile(x, "dirty")
    ck("缺失被数出", d2["n_missing"] == 2, str(d2["n_missing"]))
    ck("极端值被判异常", d2["n_outlier"] >= 1, str(d2["n_outlier"]))

    # 常数列
    d3 = col_profile([5.0] * 20, "const")
    ck("常数列被识别", d3["is_constant"], str(d3.get("is_constant")))

    # 偏态列
    d4 = col_profile(list(rng.lognormal(0, 1, 200)), "lognormal")
    ck("对数正态被判偏态", abs(d4["skew"]) > 1, f"{d4['skew']:+.2f}")

    # 共线
    class FakeDS:
        num_names = ["a", "b", "c"]
        n_rows = 50

        def col(self, nm):
            a = np.arange(50, dtype=float)
            return {"a": a, "b": 2 * a + 1, "c": a * 3 - 2}[nm]

    c = condition_number(FakeDS())
    ck("完全共线时条件数极大", c is not None and c > 1e6, f"{c:.3g}")
    # 量纲差异不该被判成共线
    class ScaleDS:
        num_names = ["small", "large", "mid"]
        n_rows = 50

        def col(self, nm):
            # 三列必须是**不同的**随机数，只是量纲不同。
            # 之前用同一个 a 缩放三份，标准化后三列完全相同 →
            # 条件数无穷大，测试自然失败（是测试写错，不是代码错）。
            return {"small": np.random.default_rng(11).normal(0, 1, 50) * 0.001,
                    "large": np.random.default_rng(22).normal(0, 1, 50) * 100.0,
                    "mid": np.random.default_rng(33).normal(0, 1, 50)}[nm]

    _cn = condition_numbers(ScaleDS())
    ck("量纲差异下原始条件数大", _cn["raw"] > 100, f"{_cn['raw']:.0f}")
    ck("量纲差异下标准化条件数小", _cn["scaled"] < 30,
       f"{_cn['scaled']:.1f}")

    # 真实数据
    try:
        import mm
        ds = mm.DS(mm.find_xlsx())
        p = profile(ds)
        ck("真实数据能画像", p["n_rows"] == 84, f"{p['n_rows']} 行")
        ck("每列都有画像", len(p["columns"]) == p["n_cols"],
           f"{len(p['columns'])} 列")
        ck("能给建议", len(advice(p)) >= 1, advice(p)[0][:44])
        ck("报告能生成", "数据画像" in report(p))
    except Exception as e:                          # noqa: BLE001
        ck("真实数据能画像", False, f"{type(e).__name__}: {e}")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if not a or a[0] == "selftest":
        return selftest()
    import mm
    ds = mm.DS(mm.find_xlsx())
    p = profile(ds)
    print(report(p))
    if a[0].endswith(".json"):
        with open(a[0], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(p, fh, ensure_ascii=False, indent=2)
        print(f"\n  已写 {a[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
