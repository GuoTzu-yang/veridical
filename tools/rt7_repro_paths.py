#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_repro_paths.py —— 冻结表 path 抽查（只读）。

对每条抽样 path：给出 (a) 产出它的代码位置，(b) 独立复算路径，
(c) 复算值与冻结值是否一致。复算尽量走与插件无关的路径
（pandas 直读 xlsx / 工件直读 / 恒等式）。
"""
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import numpy as np                                            # noqa: E402


# ── 不依赖 scipy 的 t 分布分位（正则化不完全 beta）────────────────────
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
          + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(lb)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf_two(t, df):
    """P(|T| > t) ，双侧。"""
    x = df / (df + t * t)
    return _betai(df / 2.0, 0.5, x)


def t_crit(df, alpha=0.05):
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_sf_two(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ─────────────────────────────────────────────────────────────────────
def load_frozen(nm):
    p = os.path.join(HERE, "out", "runs", nm, "冻结数字.json")
    fz = json.load(io.open(p, encoding="utf-8"))
    return {it["path"]: it["value"] for it in fz["items"]}


def fz_final():
    p = os.path.join(HERE, "out", "final", "冻结数字.json")
    fz = json.load(io.open(p, encoding="utf-8"))
    return {it["path"]: it["value"] for it in fz["items"]}


OK = [0, 0]


def rep(path, got, want, rule, src, tol=1e-9):
    OK[1] += 1
    t = tol * max(1.0, abs(want)) if tol < 1 else tol
    good = (got is not None) and abs(got - want) <= t
    print("%-2s %-32s 冻结值=%-22.10g 复算=%-22s"
          % ("OK" if good else "XX", path, want,
             ("%.10g" % got) if got is not None else "n/a"))
    print("     规则: %s" % rule)
    print("     来源: %s" % src)
    if good:
        OK[0] += 1
    return good


def main():
    A = load_frozen("age_struct")
    import pandas as pd
    df = pd.read_excel(os.path.join(HERE, "out", "data",
                                    "age_struct.xlsx"))
    num = df.select_dtypes(include=[np.number])
    c0 = num.iloc[:, 0].dropna().to_numpy(dtype=float)

    print("── 抽查 10 条 frozen path ──")
    print()
    rep("eda.per_col[0].mean", float(c0.mean()),
        A["eda.per_col[0].mean"],
        "pandas 直读 xlsx，第 1 个数值列均值",
        "mm.py:362 float(x.mean())  (eda() 内 per_col)")
    rep("eda.per_col[0].std", float(c0.std(ddof=1)),
        A["eda.per_col[0].std"],
        "pandas 直读 xlsx，样本标准差 ddof=1",
        "mm.py:356 sd = float(x.std(ddof=1))")
    rep("eda.rows", float(len(df) - int(df[num.columns[0]]
                                         .isna().sum())),
        A["eda.rows"],
        "pandas 直读 xlsx，该列非空行数",
        "mm.py:335 res={'rows': ds.n_rows}")
    rep("eda.per_col[0].skew", float(
        np.mean(((c0 - c0.mean()) / c0.std(ddof=1)) ** 3)),
        A["eda.per_col[0].skew"],
        "pandas 直读 xlsx，矩偏度",
        "mm.py:357 skew = mean(((x-mean)/sd)**3)")
    frm, to = A["q5_tradeoff.frm"], A["q5_tradeoff.to"]
    rep("q5_tradeoff.shift", to / frm - 1.0,
        A["q5_tradeoff.shift"],
        "恒等式 shift == to/frm - 1（to=594522.6676, frm=2.381）",
        "mmkit.py:3566-3573 从 ctx['q5']['tradeoff'] 摊平 frm/to/shift")
    rep("cond.raw", round(A["fit.cond_linear"], 2), A["cond.raw"],
        "与 fit.cond_linear 同一个量，只差 dataprof 的 round(...,2)",
        "mmkit.py:3561-3565 ctx 摊平；dataprof.condition_numbers 返回 "
        "round(raw,2)", tol=0.006)
    cand = {}
    for k, v in A.items():
        m = re.match(r"fit\.cands\[(\d+)\]\.rmse$", k)
        if m:
            cand[int(m.group(1))] = v
    best = min(cand.values())
    worse = [v for v in cand.values() if v > best]
    rep("model_gap_pct", (worse[0] / best - 1.0) * 100.0,
        A["model_gap_pct"],
        "(第一个更差 rmse / 最优 rmse - 1) * 100",
        "mmkit.py:3616-3628，注释称与 paper._explain_model_choice 同算法")
    rho = A["falsify.0 - 4_seg0_rho"]
    lo, hi = A["falsify.0 - 4_seg0_lo"], A["falsify.0 - 4_seg0_hi"]
    good = (-1.0 <= rho <= 1.0) and (lo < hi) and abs(rho - round(rho, 3)) < 1e-9
    OK[1] += 1
    print("%-2s %-32s 冻结值=%-22.10g lo/hi=%s" %
          ("OK" if good else "XX", "falsify.0 - 4_seg0_rho", rho, (lo, hi)))
    print("     规则: rho∈[-1,1]，lo<hi，rho 已按 3 位小数舍入")
    print("     来源: mmkit.py:3574-3585 取 ctx['falsify'][nm]['segs'][i]"
          " 的 [lo,hi,rho]；falsify.py 算滑动窗口局部相关")
    if good:
        OK[0] += 1

    F = fz_final()
    sch = json.load(io.open(os.path.join(HERE, "schema.json"),
                            encoding="utf-8"))
    rep("derived.n_commands", float(sch["n_commands"]),
        F["derived.n_commands"],
        "schema.json['n_commands'] 字段直读",
        "tools/freeze_paper_numbers.py:67 derived['n_commands']=D['n_commands']")
    rep("data.schema_bytes", float(os.path.getsize(
        os.path.join(HERE, "schema.json"))), F["data.schema_bytes"],
        "os.path.getsize('schema.json')",
        "tools/collect_paper_data*.py 采集 schema 体量")
    rep("derived.n_declared_args", float(sch["n_declared_args"]),
        F["data.n_declared_args"],
        "schema.json['n_declared_args'] 字段直读",
        "tools/freeze_paper_numbers.py:68 derived['n_declared_args']")

    n, alpha = 84, 0.05
    tc = t_crit(n - 2, alpha)
    rc = tc / math.sqrt(tc * tc + (n - 2))
    rep("derived.r_crit_84", rc, F["derived.r_crit_84"],
        "t 反解 r=t/sqrt(t^2+df)，df=82，alpha=0.05（自写不完全 beta，无 scipy）",
        "tools/freeze_paper_numbers.py:111 **手写字面量** 0.2146",
        tol=5e-4)

    print()
    print("合计：%d/%d 条能独立复算到与冻结值一致" % (OK[0], OK[1]))
    print()
    print("── 手写字面量（tools/freeze_paper_numbers.py:106-111）──")
    for k in ("derived.dpi_floor", "derived.historic_claim_low",
              "derived.historic_claim_high", "derived.name_sha256_bits",
              "derived.alpha", "derived.r_crit_84"):
        print("   %-32s = %s" % (k, F.get(k)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
