#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
falsify.py —— 主动证伪（P07，第 9 轮）

为什么需要它
------------
lanes.py 的 7 条通道验的是「整体符号对不对」：偏相关 +0.64 说应为负，
于是判方向错误。这是统计层面。

但还有一类错它抓不到：**结论在局部不成立**。
    「宽度比每增加 0.1，热阻下降 5%」——全局偏相关确实是负的，
    但可能在某两个宽度之间热阻反而上升（噪声、或真实非单调）。
    这种结论写进论文，被评委挑一个点就崩。

所以这里补三件事：
    1. 逐点反例搜索（counterexamples）—— 找违反结论的数据点
    2. 极限行为（limit_behavior）—— 把输入推到边界外，看预测是否荒谬
    3. 量纲一致性（dimension_check）—— 等式两边量纲必须相同

Lean 的做法是「你写不出反例才算对」。数模没法形式化证明，
但可以退一步：**主动搜反例，搜不到才有资格说这结论稳**。

用法
    python falsify.py selftest
    python falsify.py counter --data X.xlsx --y 热阻 --x 宽度 --sign -1
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ══════════════════════════════════════════════════════════════════════
#  ① 逐点反例搜索
# ══════════════════════════════════════════════════════════════════════
def counterexamples(xs, ys, sign: int, min_seg: int = 8) -> dict:
    """找违反「x 增 → y 按 sign 变」的局部区段。

    sign=+1 表示「x 增 y 也增」，-1 表示「x 增 y 降」。

    做法：按 x 排序后滑动窗口，窗口内算 x 和 y 的秩相关。
    与主张符号相反、且样本量够的窗口，就是一个反例区段。

    为什么用秩相关而不是线性斜率：局部可能非线性，
    秩相关只问「同增还是反向」，不假设直线。
    """
    pairs = [(float(a), float(b)) for a, b in zip(xs, ys)
             if a is not None and b is not None
             and not (isinstance(a, float) and math.isnan(a))
             and not (isinstance(b, float) and math.isnan(b))]
    if len(pairs) < min_seg * 2:
        return dict(ok=False, why=f"样本不足（{len(pairs)} < {min_seg * 2}）",
                    n=len(pairs), segments=[], n_violating=0,
                    aggregated=False, n_groups=len({p[0] for p in pairs}),
                    n_test=len(pairs))
    pairs.sort(key=lambda p: p[0])

    # ── 重尾 ties：先聚合再判单调 ──────────────────────────────────
    # 滑窗按 x 排序取连续点。若 x 只有少数几个不同取值（例如「服务台数」
    # 只有 1..5，共 24 行），窗口会落在同一取值的重复值内部，量的是组内
    # 噪声而不是沿 x 的方向。实测 queueing 因此算出「100% 覆盖」的假象。
    _distinct = len({p[0] for p in pairs})
    _aggregated = False
    if _distinct < max(3, len(pairs) // 3):
        _groups = {}
        for a, b in pairs:
            _groups.setdefault(a, []).append(b)
        pairs = sorted((a, sum(v) / len(v)) for a, v in _groups.items())
        _aggregated = True
        # 组数少时必须放宽窗口，否则永远凑不满
        min_seg = max(3, min(min_seg, len(pairs) // 2))
        if len(pairs) < 3:
            return dict(ok=False,
                        why=f"x 只有 {len(pairs)} 个不同取值，无法判单调",
                        n=len(pairs), segments=[], n_violating=0,
                        aggregated=True, n_groups=_distinct,
                        n_test=len(pairs))

    segments = []
    for i in range(0, len(pairs) - min_seg + 1):
        seg = pairs[i:i + min_seg]
        rho = _spearman([p[0] for p in seg], [p[1] for p in seg])
        if rho is None:
            continue
        # 与主张符号相反 = 反例
        if rho * sign < 0:
            segments.append(dict(
                start=round(seg[0][0], 6), end=round(seg[-1][0], 6),
                rho=round(rho, 4), i0=i, i1=i + min_seg - 1))

    # 合并重叠区段，只报最长的几段
    merged = _merge(segments)
    return dict(ok=not merged, n=len(pairs),
                aggregated=_aggregated, n_groups=_distinct,
                n_test=len(pairs),
                n_violating=len(merged),
                segments=merged[:6],
                # 这条必须写出来：本搜索是**边际**的，没控制其他变量。
                # 边际反例可能是混淆造成的，不是真的非单调。
                marginal=True,
                caution=("本搜索未控制其他变量。边际反例可能来自未控制的"
                         "第三变量；要与偏相关符号一起看，两者都矛盾才算"
                         "真的非单调"),
                why=("没有局部反例" if not merged
                     else f"发现 {len(merged)} 段局部违反（边际，未控制）"))


def _spearman(a, b):
    """秩相关。ties 用平均秩。"""
    n = len(a)
    if n < 3:
        return None
    ra, rb = _rank(a), _rank(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def _rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _merge(segs):
    if not segs:
        return []
    segs.sort(key=lambda s: s["i0"])
    out = [dict(segs[0])]
    for s in segs[1:]:
        if s["i0"] <= out[-1]["i1"]:
            out[-1]["i1"] = max(out[-1]["i1"], s["i1"])
            out[-1]["end"] = s["end"]
            # 保留更强的（|rho| 更大）
            if abs(s["rho"]) > abs(out[-1]["rho"]):
                out[-1]["rho"] = s["rho"]
        else:
            out.append(dict(s))
    # 按跨度排序，报最长的
    out.sort(key=lambda s: s["i1"] - s["i0"], reverse=True)
    return out


# ══════════════════════════════════════════════════════════════════════
#  ② 极限行为
# ══════════════════════════════════════════════════════════════════════
def fit_centered(xs, ys):
    """一元线性拟合，返回**中心化**形式的系数。

    为什么单独给一个函数（第 96 轮）：`limit_behavior` 用的是中心化公式
        yhat = intercept + coef * (x - xmean)
    而 `np.polyfit` 给的截距是 **x = 0 处**的值。两者直接对接会把常数项
    平移 coef*xmean —— 预测值整体错位，于是算出根本不存在的「外推穿零」。

    实测代价：上一轮我用 polyfit 的输出喂 limit_behavior，23 道题报出
    11 道「荒谬外推」；改正约定后有相当一部分是假的。

    返回值可直接作为 `limit_behavior(**d)` 的入参。
    """
    import numpy as _np
    xv = _np.asarray([v for v in xs], dtype=float)
    yv = _np.asarray([v for v in ys], dtype=float)
    mask = ~(_np.isnan(xv) | _np.isnan(yv))
    xv, yv = xv[mask], yv[mask]
    if len(xv) < 3 or _np.std(xv) == 0:
        return dict(coef=0.0, intercept=float(_np.mean(yv) if len(yv) else 0.0),
                    xmean=float(_np.mean(xv) if len(xv) else 0.0),
                    xstd=float(_np.std(xv) if len(xv) else 0.0),
                    xs_min=float(_np.min(xv) if len(xv) else 0.0),
                    xs_max=float(_np.max(xv) if len(xv) else 0.0))
    xm = float(_np.mean(xv))
    coef, icpt0 = _np.polyfit(xv, yv, 1)          # icpt0 是 x=0 处的值
    return dict(coef=float(coef),
                intercept=float(icpt0) + float(coef) * xm,   # 平移到 x=xm
                xmean=xm, xstd=float(_np.std(xv)),
                xs_min=float(_np.min(xv)), xs_max=float(_np.max(xv)))


def limit_behavior(coef, intercept, xmean, xstd, xs_min, xs_max,
                   y_bounds=None, n_extrap: int = 5,
                   y_sign=None, x_sign=None) -> dict:
    """把输入推到观测范围外，看线性预测是否给出荒谬值。

    线性模型在样本区间外必然线性外推。如果推出去的值物理上不可能
    （负的热阻、负的浓度、超过 100% 的占比），那说明这个模型
    只在其定义域内有效，论文里必须声明边界。

    coef / intercept 用**中心化**约定：`yhat = intercept + coef*(x - xmean)`，
    也就是 intercept 是 **x = xmean 处**的值，不是 x = 0 处的值。
    直接拿 `np.polyfit` 的截距塞进来会整体平移 `coef*xmean` ——
    用 `fit_centered()` 转换，别手接（第 96 轮踩过，报出一堆假荒谬）。

    原来那行还写着

        yhat = intercept + coef * (x - xmean) / (xstd or 1.0) * xstd

    `/ xstd * xstd` 恒等于 1，看着像「先标准化再还原」，其实什么都没做。
    写清楚反而危险：读的人会以为传标准化系数也行。现已改成直白的形式。

    y_bounds: (lo, hi) 物理可行范围；None 表示不检查越界。
    y_sign:   +1 / -1 表示观测到的 y 全部同号。给了就检查外推是否**穿过零点**
              （负热阻、负浓度这类荒谬值的共同特征）。这一条不需要人为阈值：
              只要观测全正，预测出现负值就是荒谬，与量纲无关。
    x_sign:   +1 / -1 表示观测到的 x 全部同号。给了就把外推网格限制在
              自变量仍然成立的半轴内 —— 否则「服务台数 = -10」这种
              本就不可能的取值会制造一堆无意义的告警。
    """
    issues = []
    step = (xs_max - xs_min) / max(1, n_extrap)
    grid = [xs_min - step * k for k in (3, 2, 1)] + \
           [xs_max + step * k for k in (1, 2, 3)]
    # 自变量本身不能推到不可能的取值（第 95 轮）：
    # 「服务台数 = -10」「人口 = -151 万」这种外推没有意义 —— 自变量已经
    # 不成立了，再说因变量荒谬是空话。实测不加这一步，23 道题里 11 道会报，
    # 大半报的就是这类。
    if x_sign in (1, -1):
        if x_sign > 0:
            grid = [g for g in grid if g > 0]
        else:
            grid = [g for g in grid if g < 0]
    preds = []
    for x in grid:
        yhat = intercept + coef * (x - xmean)
        preds.append(dict(x=round(x, 6), yhat=round(yhat, 6)))

    if y_bounds:
        lo, hi = y_bounds
        for p in preds:
            if p["yhat"] < lo or p["yhat"] > hi:
                issues.append(
                    f"外推到 x={p['x']} 时预测 {p['yhat']} 超出物理可行范围 "
                    f"[{lo}, {hi}]，该模型不可外推")
    if y_sign in (1, -1):
        bad = [p for p in preds if p["yhat"] * y_sign <= 0]
        if bad:
            issues.append(
                "观测到的响应全部 %s，但外推到 x=%s 时预测 %s "
                "（穿过零点，物理上不可行）"
                % ("为正" if y_sign > 0 else "为负",
                   bad[0]["x"], bad[0]["yhat"]))

    return dict(ok=not issues, extrapolation=preds,
                issues=issues,
                note=("观测区间 [" + str(round(xs_min, 6)) + ", "
                      + str(round(xs_max, 6)) + "]，区间外为外推"))


# ══════════════════════════════════════════════════════════════════════
#  ③ 量纲一致性
# ══════════════════════════════════════════════════════════════════════
# 常见量的量纲（用 SI 基本量指数 [L, M, T, Θ]）
DIMS = {
    "length": (1, 0, 0, 0),
    "mass": (0, 1, 0, 0),
    "time": (0, 0, 1, 0),
    "temperature": (0, 0, 0, 1),
    "velocity": (1, 0, -1, 0),
    "acceleration": (1, 0, -2, 0),
    "force": (1, 1, -2, 0),
    "pressure": (-1, 1, -2, 0),
    "energy": (2, 1, -2, 0),
    "power": (2, 1, -3, 0),
    "density": (-3, 1, 0, 0),
    "thermal_conductivity": (1, 1, -3, -1),
    "heat_transfer_coef": (0, 1, -3, -1),
    "thermal_resistance": (-2, -1, 3, 1),
    "kinematic_viscosity": (2, 0, -1, 0),
    "dynamic_viscosity": (-1, 1, -1, 0),
    "dimensionless": (0, 0, 0, 0),
}


def dim_of(name: str):
    return DIMS.get(str(name).strip().lower())


def dimension_check(lhs: str, rhs_terms) -> dict:
    """检查等式两边量纲是否一致。

    rhs_terms: [(符号名, 指数)]，例如 [("pressure", -1), ("velocity", 2)]
    返回 issues；空表示一致。
    """
    L = dim_of(lhs)
    if L is None:
        return dict(ok=None, issues=[f"未知量纲：{lhs}"], lhs=None, rhs=None)
    acc = [0, 0, 0, 0]
    unknown = []
    for nm, e in rhs_terms:
        d = dim_of(nm)
        if d is None:
            unknown.append(nm)
            continue
        for k in range(4):
            acc[k] += d[k] * e
    if unknown:
        return dict(ok=None, issues=[f"右侧含未知量纲：{unknown}"],
                    lhs=L, rhs=tuple(acc))
    ok = tuple(acc) == tuple(L)
    return dict(ok=ok, lhs=L, rhs=tuple(acc),
                issues=[] if ok else
                [f"量纲不一致：左边 {lhs}{L}，右边 {tuple(acc)}"])


# ══════════════════════════════════════════════════════════════════════
#  自测
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

    # ── 反例搜索 ──
    # 单调下降：不该报反例
    xs = list(range(40))
    ys = [100 - 2 * x for x in xs]
    r = counterexamples(xs, ys, sign=-1)
    ck("单调序列无局部反例", r["ok"], f"{r['n_violating']} 段")

    # 中间有个平台/上翘：应报反例
    ys2 = [100 - 2 * x if x < 15 else (70 + (x - 15) * 2) for x in xs]
    r2 = counterexamples(xs, ys2, sign=-1)
    ck("上翘段被抓出", not r2["ok"], f"{r2['n_violating']} 段")
    ck("反例区段带起止值", bool(r2["segments"])
       and "start" in r2["segments"][0],
       str(r2["segments"][0])[:60] if r2["segments"] else "")

    # 样本太少不硬判
    r3 = counterexamples([1, 2, 3], [3, 2, 1], sign=-1)
    ck("样本不足时返回 ok=False 但不报反例",
       r3["ok"] is False and r3["n_violating"] == 0, r3["why"][:40])

    # ── 极限行为 ──
    # 热阻随宽度下降，外推到很宽 → 可能为负
    lb = limit_behavior(coef=-2.0, intercept=0.75, xmean=0.5, xstd=0.1,
                        xs_min=0.2, xs_max=0.9, y_bounds=(0.0, 10.0))
    neg = [p for p in lb["extrapolation"] if p["yhat"] < 0]
    ck("外推出负热阻被抓出", bool(neg) and not lb["ok"],
       f"{len(neg)} 个越界点" if neg else "没抓到")

    # 不设物理边界 → 不报越界
    lb2 = limit_behavior(coef=-0.5, intercept=0.75, xmean=0.5, xstd=0.1,
                         xs_min=0.2, xs_max=0.9, y_bounds=None)
    ck("不设边界时不误报", lb2["ok"])
    ck("外推网格给出 6 个点", len(lb["extrapolation"]) == 6,
       f"{len(lb['extrapolation'])}")

    # ── 第 94 轮：原始单位公式 + 零穿越 ──
    # 原来的 yhat 写成 `intercept + coef*(x-xmean)/(xstd or 1.0)*xstd`，
    # `/xstd*xstd` 恒等于 1 —— 看着像标准化还原，其实什么都没做。
    # 下面这条断言把「就等于原始单位公式」钉死，防止有人再加回自消的写法。
    _lbn = limit_behavior(coef=1.5, intercept=2.0, xmean=0.5, xstd=0.1,
                          xs_min=0.2, xs_max=0.9)
    _ok_formula = all(
        abs(p["yhat"] - (2.0 + 1.5 * (p["x"] - 0.5))) < 1e-6
        for p in _lbn["extrapolation"])
    ck("外推按原始单位公式算（/xstd*xstd 是自消的）", _ok_formula,
       str(_lbn["extrapolation"][:2]))
    # 观测全为正、外推却穿过零点 → 必须报
    _z = limit_behavior(coef=-2.0, intercept=0.75, xmean=0.5, xstd=0.1,
                        xs_min=0.2, xs_max=0.9, y_sign=1)
    ck("观测全正但外推穿零 → 报荒谬", not _z["ok"]
       and any("穿过零点" in s for s in _z["issues"]),
       str(_z["issues"][:1])[:70])
    # 外推仍在正区间 → 放行
    _z2 = limit_behavior(coef=0.2, intercept=5.0, xmean=0.5, xstd=0.1,
                         xs_min=0.2, xs_max=0.9, y_sign=1)
    ck("外推未穿零 → 放行", _z2["ok"], str(_z2["issues"])[:50])
    # 不传 y_sign 也不传 bounds → 只看网格，不报问题（保持旧行为）
    _z3 = limit_behavior(coef=-2.0, intercept=0.75, xmean=0.5, xstd=0.1,
                         xs_min=0.2, xs_max=0.9)
    ck("不给约束时保持旧行为（只给网格）", _z3["ok"])

    # x_sign：自变量本身不可能时不要拿它去论证因变量荒谬。
    # 实测不加这一步，23 道题里 11 道报错，大半报的是「服务台数 = -10」
    # 这种自变量先失效的情形。
    _g0 = limit_behavior(coef=-2.0, intercept=0.75, xmean=0.5, xstd=0.1,
                         xs_min=0.2, xs_max=0.9, y_sign=1)
    _g1 = limit_behavior(coef=-2.0, intercept=0.75, xmean=0.5, xstd=0.1,
                         xs_min=0.2, xs_max=0.9, y_sign=1, x_sign=1)
    ck("x_sign 剔掉非正的自变量取值",
       all(p["x"] > 0 for p in _g1["extrapolation"])
       and any(p["x"] <= 0 for p in _g0["extrapolation"]),
       f"{[p['x'] for p in _g1['extrapolation']]}")

    # ── 量纲 ──
    # 粘性压力尺度 = 动力粘度 × 速度 / 长度  → 应为压力
    # （mu*v/L^2 是压力梯度 dP/dx，不是压力，量纲差一个 L）
    d = dimension_check("pressure",
                        [("dynamic_viscosity", 1), ("velocity", 1),
                         ("length", -1)])
    ck("压力梯度量纲一致", d["ok"] is True, str(d["rhs"]))

    # 故意的错：压力 = 速度
    d2 = dimension_check("pressure", [("velocity", 1)])
    ck("错误量纲被抓出", d2["ok"] is False, d2["issues"][0][:50])

    # 无量纲数
    d3 = dimension_check("dimensionless", [("dimensionless", 1)])
    ck("无量纲数自身一致", d3["ok"] is True)

    # 未知量纲不硬判
    d4 = dimension_check("pressure", [("神秘量", 1)])
    ck("未知量纲返回 ok=None", d4["ok"] is None, str(d4["issues"])[:50])

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="主动证伪")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "counter"])
    ap.add_argument("--data", default="")
    ap.add_argument("--y", default="")
    ap.add_argument("--x", default="")
    ap.add_argument("--sign", type=int, default=-1,
                    help="主张符号：+1 同增，-1 反向")
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()

    if not (a.data and a.y and a.x):
        print("  需要 --data --y --x")
        return 2
    import mm
    ds = mm.DS(a.data)
    # --x 可以是逗号分隔的多个因子（第 108 轮）。
    # 原来整个串被当成**一个列名**，于是 KeyError:
    #   没有数值列 '宽度,深高'；有 [...]
    # —— 开赛当天第一条反例命令就崩，这是手册验证抓出来的。
    _xs = [x.strip() for x in str(a.x).split(",") if x.strip()]
    _ys = [y.strip() for y in str(a.y).split(",") if y.strip()]
    if not _xs or not _ys:
        print("  --x / --y 解析后为空")
        return 2
    _bad = 0
    for _y in _ys:
        for _x in _xs:
            try:
                # 用 ds.pick 而不是 ds.col：pick 能认**显示名**（如「宽度」对应
                # 数据里的「针肋宽度比」），跟 hints / race 的口径一致（第 108 轮）。
                _cx = ds.pick([_x])[0]
                _cy = ds.pick([_y])[0]
                r = counterexamples(ds.col(_cx), ds.col(_cy), sign=a.sign)
            except (KeyError, IndexError) as e:
                print(f"  跳过 {_x} → {_y}：{e}")
                _bad += 1
                continue
            print(f"  反例搜索：{_x} → {_y}（主张符号 {a.sign:+d}）")
            # 样本量要说全（第 108 轮）：原来只印「样本 {r['n']}」，
            # 而 r['n'] 是**x 的不同取值数（分组数）**，不是行数 ——
            # 实测 84 行数据上打印「样本 5」，等于报错样本量。
            # 这类数字会被评委直接看，错了就是硬伤。
            _ng = r.get("n_groups", r.get("n"))
            _nt = r.get("n_test")
            print(f"  原始 {len(ds.col(_cx))} 行；x 有 {_ng} 个不同取值"
                  + (f"，其中 {_nt} 组参与检验" if _nt else "")
                  + f"；违反区段 {r['n_violating']} 段")
            for s in r["segments"]:
                print(f"    x∈[{s['start']}, {s['end']}]  rho={s['rho']:+.3f}")
            if r["segments"]:
                print("    → 这条主张**不能**写成结论，只能写成局限")
            else:
                print("    → 未找到反例（仍需看样本量是否够）")

            # 边际反例必须和条件符号一起看 —— 否则会把混淆当成非单调
            try:
                others = [c for c in ds.num_names
                          if c not in (_x, _y) and "编号" not in c][:4]
                pcs = []
                for o in others:
                    pc = mm.partial_corr(ds, _y, _x, [o])
                    # partial_corr 可能返回 dict，也可能是带属性的对象；
                    # 只写 pc.get(...) 会 AttributeError，整段对照静默失效。
                    _r = (pc.get("r") if isinstance(pc, dict)
                          else getattr(pc, "r", None))
                    if _r is not None:
                        pcs.append((o, _r))
                if pcs:
                    print("\n  控制单个变量后的偏相关符号（用于对照）：")
                    for o, rr in pcs:
                        agree = (rr * a.sign > 0)
                        print(f"    控制 {o[:14]:<16} r={rr:+.3f}  "
                              f"{'与主张一致' if agree else '与主张相反'}")
                    same = all(rr * a.sign > 0 for _, rr in pcs)
                    if not r["ok"] and same:
                        print("\n  ⚠ 边际有反例，但控制后符号一致 —— "
                              "反例很可能来自未控制的第三变量，不是真非单调")
                    elif not r["ok"] and not same:
                        print("\n  ✗ 边际反例 + 条件符号相反 —— 这个结论不成立")
            except Exception as e:                      # noqa: BLE001
                print(f"  （偏相关对照失败：{type(e).__name__}）")
    return 0 if _bad == 0 else 2


    if r["ok"]:
        print("  没有找到局部反例 —— 这个结论在观测范围内站得住")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
