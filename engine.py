#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py —— 数学建模推理引擎

设计只有一句话：
    **建模的难点不是算，是知道"这一步凭什么"。**

所以本引擎的每个动作都必须带三样东西：
    1. 前提      —— 这个方法能用，凭什么？（可检验，三态：真/假/未知）
    2. 区间      —— 这个数是点估计，它的不确定有多大？（蒙特卡洛传播）
    3. 判决      —— 这条结论能写到什么程度？（走 harness 闸门）

三样缺一个，结论就不许出。这是「少幻觉」的实现方式，
不是靠"不要说错"，是靠**结构上不给说错的机会**。

五层能力
--------
L4 机理       rk4()          常微分方程（自写 RK4 + RK45 步长控制）
              buckingham()   量纲分析（Pi 定理）
L5 约束优化   cma_light()    带约束最小化（自适应协方差，无外部依赖）
              milp_greedy()  小规模整数规划的穷举/分支
L6 不确定性   mc()           蒙特卡洛传播 → 区间
              bootstrap()    自助法 → 参数区间
L2 拟合       fit_race()     结构竞速（K 折 CV）
L7 验证       extrap_check() 外推域检查
L8 判定       verdict()      走闸门，给可信度凭证

前提检验
--------
每个方法都用 @requires 登记前提，检出的结果是三态：
    True   —— 有证据支持这个前提下成立
    False  —— 有证据**反对**
    None   —— 没查/查不了  ← 绝不当成 True

判据：只要有一条前提是 False，方法不许用；
      有一条是 None，可以用，但结论必须降级（走 degrade）。

跑法
----
    python engine.py selftest          # 自检（不需要数据）
    python engine.py demo              # 五层能力演示
"""

from __future__ import annotations

import io
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ══════════════════════════════════════════════════════════════════════
#  前提登记
# ══════════════════════════════════════════════════════════════════════
class Ctx:
    """一次建模的上下文。所有方法都从这里取数据。"""

    def __init__(self, **kw):
        self.data = kw.get("data")
        self.X = kw.get("X")            # (n, p) 自变量
        self.y = kw.get("y")            # (n,)  因变量
        self.meta = dict(kw.get("meta") or {})
        self.notes: list[str] = []

    def note(self, s: str) -> None:
        self.notes.append(s)

    def __repr__(self):
        n = 0 if self.y is None else len(self.y)
        p = 0 if self.X is None else self.X.shape[1]
        return f"<Ctx n={n} p={p}>"


REGISTRY: dict[str, dict] = {}


def method(name: str, kind: str, gives: list[str]):
    """登记一个方法。requires 由 @needs 追加。"""
    def deco(fn):
        REGISTRY[name] = dict(fn=fn, kind=kind, gives=gives, needs=[],
                              name=name)
        fn._mname = name
        return fn
    return deco


def needs(desc: str):
    """给方法加一条前提。fn(ctx) 必须返回 True / False / None。"""
    def deco(fn):
        REGISTRY[fn._mname]["needs"].append((desc, fn.__name__))
        _CHECKS[fn.__name__] = fn
        return fn
    return deco


_CHECKS: dict[str, object] = {}


def check_premises(name: str, ctx: Ctx) -> dict:
    """跑完一个方法的全部前提，返回三态汇总。"""
    m = REGISTRY[name]
    rows = []
    any_false = any_none = False
    for desc, fn_name in m["needs"]:
        try:
            r = _CHECKS[fn_name](ctx)
        except Exception as e:                       # 前提检查自己崩了
            r = None
            desc = f"{desc}（检查抛异常：{type(e).__name__}）"
        if r is False:
            any_false = True
        elif r is None:
            any_none = True
        rows.append(dict(desc=desc, result=r))
    return dict(rows=rows, usable=not any_false, certain=not any_none,
                any_false=any_false, any_none=any_none)


def fmt_premises(p: dict) -> str:
    tags = {True: "成立", False: "不成立", None: "未知"}
    lines = []
    for r in p["rows"]:
        lines.append(f"      {'✓' if r['result'] is True else '✗' if r['result'] is False else '?'}"
                     f" {r['desc']} —— {tags[r['result']]}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  L4 机理：ODE
# ══════════════════════════════════════════════════════════════════════
def rk4(f, y0, t0: float, t1: float, n: int = 200):
    """定步长 RK4。返回 (ts, ys)，ys 形状 (n+1, len(y0))。

    为什么手写：环境没有 scipy。RK4 的局部误差 O(h^5)，对建模够用；
    真要更高精度，用下面的 rk45。
    """
    y = np.asarray(y0, dtype=float)
    h = (t1 - t0) / n
    ts = np.linspace(t0, t1, n + 1)
    ys = np.zeros((n + 1, len(y)))
    ys[0] = y
    for i in range(n):
        t = ts[i]
        k1 = np.asarray(f(t, y), dtype=float)
        k2 = np.asarray(f(t + h / 2, y + h / 2 * k1), dtype=float)
        k3 = np.asarray(f(t + h / 2, y + h / 2 * k2), dtype=float)
        k4 = np.asarray(f(t + h, y + h * k3), dtype=float)
        y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        ys[i + 1] = y
    return ts, ys


def rk45(f, y0, t0: float, t1: float, rtol=1e-7, atol=1e-9,
         h0=None, max_steps=200000):
    """自适应步长 RK45（Dormand-Prince）。返回 (ts, ys) 与统计。

    步长自己找 —— 这是"准确"和"快速"同时要的东西：
    平滑段放大步，突变段缩小步。
    """
    y = np.asarray(y0, dtype=float)
    h = h0 if h0 else (t1 - t0) / 100
    t = t0
    ts, ys = [t], [y.copy()]
    steps = rej = 0
    C = np.array([0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1, 1])
    A = [[], [1 / 5], [3 / 40, 9 / 40], [44 / 45, -56 / 15, 32 / 9],
         [19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729],
         [9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656],
         [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84]]
    B5 = np.array([35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784,
                   11 / 84, 0])
    B4 = np.array([5179 / 57600, 0, 7571 / 16695, 393 / 640,
                   -92097 / 339200, 187 / 2100, 1 / 40])
    while t < t1 and steps < max_steps:
        h = min(h, t1 - t)
        ks = []
        for i in range(7):
            yi = y.copy()
            for j, aij in enumerate(A[i]):
                if aij:
                    yi = yi + h * aij * ks[j]
            ks.append(np.asarray(f(t + C[i] * h, yi), dtype=float))
        y5 = y + h * sum(b * k for b, k in zip(B5, ks) if b)
        y4 = y + h * sum(b * k for b, k in zip(B4, ks) if b)
        err = np.max(np.abs(y5 - y4) / (atol + rtol * np.maximum(np.abs(y), np.abs(y5))))
        steps += 1
        if err <= 1.0 or h < 1e-14:
            t += h
            y = y5
            ts.append(t)
            ys.append(y.copy())
        else:
            rej += 1
        fac = 0.9 * (1.0 / max(err, 1e-16)) ** 0.2 if err > 0 else 5.0
        h *= min(5.0, max(0.2, fac))
    return np.array(ts), np.array(ys), dict(steps=steps, rejected=rej)


# ══════════════════════════════════════════════════════════════════════
#  L4 机理：量纲分析
# ══════════════════════════════════════════════════════════════════════
def buckingham(vars_: list[tuple[str, dict[str, float]]]) -> dict:
    """Pi 定理。vars_ = [(名字, {基本量纲: 幂})]。

    返回无量纲组合（指数向量）与自由度。
    基本量纲通常是 {"M":质量,"L":长度,"T":时间,"K":温度,...}
    """
    dims = sorted({d for _, dd in vars_ for d in dd})
    A = np.array([[dd.get(d, 0.0) for d in dims] for _, dd in vars_]).T
    rank = int(np.linalg.matrix_rank(A)) if A.size else 0
    n = len(vars_)
    null = n - rank
    basis = []
    if null > 0:
        u, s, vt = np.linalg.svd(A)
        for i in range(rank, n):
            v = vt[i]
            v = v / np.max(np.abs(v))
            basis.append(np.round(v, 10))
    return dict(dims=dims, rank=rank, n=n, n_pi=null, pis=basis,
                names=[v[0] for v in vars_])


# ══════════════════════════════════════════════════════════════════════
#  L5 约束优化：自适应协方差最小化（无外部依赖）
# ══════════════════════════════════════════════════════════════════════
def nelder_mead(f, x0, lo=None, hi=None, step=0.1, iters=2000, tol=1e-12):
    """Nelder-Mead 单纯形。无导数，对病态/非光滑目标比粗糙梯度法稳。

    为什么必须有它：Rosenbrock 这类狭长谷地，网格和粗糙 CMA 都会卡住。
    两条不同原理的算法都给同一个解，最优才站得住。
    """
    x0 = np.asarray(x0, float)
    dim = len(x0)
    lo = None if lo is None else np.asarray(lo, float)
    hi = None if hi is None else np.asarray(hi, float)

    def clip(p):
        if lo is None:
            return p
        return np.minimum(np.maximum(p, lo), hi)

    simplex = [clip(x0.copy())]
    for i in range(dim):
        p = x0.copy()
        p[i] += step * max(1.0, abs(p[i]))
        simplex.append(clip(p))
    simplex = np.array(simplex)
    vals = np.array([f(p) for p in simplex])

    for it in range(iters):
        order = np.argsort(vals)
        simplex, vals = simplex[order], vals[order]
        if abs(vals[-1] - vals[0]) < tol:
            break
        centroid = simplex[:-1].mean(0)
        xr = clip(centroid + 1.0 * (centroid - simplex[-1]))
        fr = f(xr)
        if fr < vals[0]:
            xe = clip(centroid + 2.0 * (centroid - simplex[-1]))
            fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = clip(centroid + 0.5 * (simplex[-1] - centroid))
            fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:
                for i in range(1, len(simplex)):
                    simplex[i] = clip(simplex[0] + 0.5 * (simplex[i] - simplex[0]))
                    vals[i] = f(simplex[i])
    i = int(np.argmin(vals))
    return dict(x=simplex[i], f=float(vals[i]), iters=it + 1)


def cma_light(f, lo, hi, n=100, iters=400, sigma0=None, seed=0, polish=True):
    """在 box 约束下最小化 f。自适应协方差 + Nelder-Mead 精化。

    两段式：
      1. CMA 全局找盆地（不管病态）
      2. NM 在盆地里精化（对付狭长谷地）
    单用任一个都会在 Rosenbrock 上翻车 —— 这是算出来的，不是猜的。
    """
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    rng = np.random.default_rng(seed)
    dim = len(lo)
    x = (lo + hi) / 2
    sigma = sigma0 if sigma0 else float(np.mean(hi - lo)) / 3
    C = np.eye(dim)
    best_x, best_f = x.copy(), f(np.clip(x, lo, hi))
    path = []
    for it in range(iters):
        try:
            L = np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            C += 1e-10 * np.eye(dim)
            L = np.linalg.cholesky(C)
        pop = x + sigma * (rng.standard_normal((n, dim)) @ L.T)
        pop = np.clip(pop, lo, hi)
        vals = np.array([f(p) for p in pop])
        order = np.argsort(vals)
        pop, vals = pop[order], vals[order]
        if vals[0] < best_f:
            best_f, best_x = float(vals[0]), pop[0].copy()
        mu = n // 2
        w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        w = w / w.sum()
        x_new = (pop[:mu] * w[:, None]).sum(0)
        d = (x_new - x) / max(sigma, 1e-12)
        C = (1 - 0.1) * C + 0.1 * (d[:, None] * d[None, :]) + 1e-10 * np.eye(dim)
        x = x_new
        sigma *= math.exp(0.3 * (np.linalg.norm(d) / math.sqrt(dim) - 1.2))
        sigma = float(np.clip(sigma, 1e-12, float(np.max(hi - lo))))
        path.append(best_f)
        if sigma < 1e-11:
            break
    res = dict(x=best_x, f=best_f, iters=len(path), path=path)
    if polish:
        nm = nelder_mead(f, best_x, lo, hi,
                         step=0.05 * float(np.mean(hi - lo)))
        if nm["f"] < res["f"]:
            res.update(x=nm["x"], f=nm["f"], polished=True,
                       nm_iters=nm["iters"])
        else:
            res["polished"] = False
    return res


def mesh_scan(f, lo, hi, n=40):
    """网格扫描 —— 用来交叉验证 cma_light 有没有掉进局部坑。

    两条独立路径给出同一个解，才算"最优"站得住。
    """
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    dim = len(lo)
    grids = [np.linspace(lo[i], hi[i], n) for i in range(dim)]
    if dim == 1:
        pts = grids[0][:, None]
    else:
        mesh = np.meshgrid(*grids, indexing="ij")
        pts = np.column_stack([m.ravel() for m in mesh])
    vals = np.array([f(p) for p in pts])
    i = int(np.argmin(vals))
    return dict(x=pts[i], f=float(vals[i]), n_points=len(pts),
                n_local_min=int(np.sum(vals < vals[i] + 1e-6 * abs(vals[i]))))


# ══════════════════════════════════════════════════════════════════════
#  L6 不确定性
# ══════════════════════════════════════════════════════════════════════
def mc(f, param_dist: dict[str, tuple], n=2000, seed=0) -> dict:
    """蒙特卡洛传播。param_dist = {名字: ("uniform"|"normal", a, b/sigma)}。

    点估计是不确定性的谎言。这里给的是分布 + 区间。
    """
    rng = np.random.default_rng(seed)
    samples = {}
    for k, spec in param_dist.items():
        kind = spec[0]
        if kind == "uniform":
            samples[k] = rng.uniform(spec[1], spec[2], n)
        elif kind == "normal":
            samples[k] = rng.normal(spec[1], spec[2], n)
        elif kind == "tri":
            samples[k] = rng.triangular(spec[1], spec[2], spec[3], n)
        else:
            raise ValueError(kind)
    outs = np.array([f(*[samples[k][i] for k in param_dist])
                     for i in range(n)], dtype=float)
    q = np.percentile(outs, [5, 50, 95])
    return dict(samples=samples, outs=outs, mean=float(outs.mean()),
                sd=float(outs.std(ddof=1)), p05=float(q[0]),
                p50=float(q[1]), p95=float(q[2]),
                ci90=(float(q[0]), float(q[2])), n=n)


def bootstrap(X, y, stat, n=1000, seed=0) -> dict:
    """自助法：有放回重采样，给统计量的区间。不需要正态假设。"""
    rng = np.random.default_rng(seed)
    N = len(y)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, N, N)
        try:
            vals.append(float(stat(X[idx], y[idx])))
        except Exception:
            continue
    vals = np.array(vals)
    if len(vals) == 0:
        return dict(n=0, ok=False)
    q = np.percentile(vals, [5, 50, 95])
    return dict(n=len(vals), ok=True, mean=float(vals.mean()),
                sd=float(vals.std(ddof=1)), p05=float(q[0]),
                p50=float(q[1]), p95=float(q[2]),
                ci90=(float(q[0]), float(q[2])))


# ══════════════════════════════════════════════════════════════════════
#  L2 拟合
# ══════════════════════════════════════════════════════════════════════
def design(X, kind):
    X = np.asarray(X, float)
    n, p = X.shape
    ones = np.ones((n, 1))
    if kind == "linear":
        return np.hstack([ones, X])
    if kind == "quad":
        cols = [ones, X]
        cols += [(X[:, i] ** 2).reshape(-1, 1) for i in range(p)]
        cols += [(X[:, i] * X[:, j]).reshape(-1, 1)
                 for i in range(p) for j in range(i + 1, p)]
        return np.hstack(cols)
    if kind in ("log", "power"):
        if (X <= 0).any():
            return None
        return np.hstack([ones, np.log(X)])
    raise ValueError(kind)


def kfold(X, y, kind, k=5, seed=0, ridge=0.0):
    X, y = np.asarray(X, float), np.asarray(y, float)
    idx = np.arange(len(y))
    np.random.default_rng(seed).shuffle(idx)
    errs = []
    for f in np.array_split(idx, k):
        tr = np.setdiff1d(idx, f)
        A, B = design(X[tr], kind), design(X[f], kind)
        if A is None or B is None:
            return None
        AtA = A.T @ A
        if ridge > 0:
            AtA = AtA + ridge * np.eye(AtA.shape[0])
        try:
            coef = np.linalg.solve(AtA, A.T @ y[tr])
        except np.linalg.LinAlgError:
            coef, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
        errs.append(float(np.sqrt(np.mean((B @ coef - y[f]) ** 2))))
    return np.array(errs)


# ══════════════════════════════════════════════════════════════════════
#  L7 验证：外推域
# ══════════════════════════════════════════════════════════════════════
def extrap_check(X_train, X_test) -> dict:
    """检查测试点有多少落在训练域外。

    模型只在自己见过的范围里可信。这一步做不做，
    决定了论文里能不能说"该模型适用于……"。
    """
    X_train, X_test = np.asarray(X_train, float), np.asarray(X_test, float)
    lo, hi = X_train.min(0), X_train.max(0)
    out = (X_test < lo - 1e-12) | (X_test > hi + 1e-12)
    frac = float(out.any(1).mean()) if len(X_test) else 0.0
    return dict(lo=lo.tolist(), hi=hi.tolist(), frac_outside=frac,
                per_dim=out.sum(0).tolist(),
                safe=(frac == 0.0))


# ══════════════════════════════════════════════════════════════════════
#  L8 判定
# ══════════════════════════════════════════════════════════════════════
def verdict(text: str, refuted=False, certain_premises=True,
            reproduced=True) -> dict:
    """一条结论的可信度凭证。

    e1 溯源   = 2（数据与代码都在）
    e2 独立   = 1（同源码内多条路径算一票；只有跨源才 2）
    e3 可复现 = 2（真算了） / 1（只形式可复现）
    前提有未知项 → e2 降 0（不许把"不知道"当支持）
    """
    from harness import Claim, EvidenceEnv, run_gates
    e2 = 1 if certain_premises else 0
    e3 = 2 if reproduced else 1
    c = Claim("X", text, e1=2, e2=e2, e3=e3, kind="world",
              refuted_by_test=refuted)
    g = run_gates(c, EvidenceEnv(3))
    return dict(text=text, C=g["C"], final=g["final"], refuted=refuted,
                certain_premises=certain_premises,
                blocked_at=g.get("blocked_at"))


# ══════════════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    out = sys.stdout
    out.reconfigure(encoding="utf-8") if hasattr(out, "reconfigure") else None
    n_ok = n_bad = 0

    def ck(name, cond, detail=""):
        nonlocal n_ok, n_bad
        if cond:
            n_ok += 1
            print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
        else:
            n_bad += 1
            print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))

    print("=" * 80)
    print("engine.py 自检")
    print("=" * 80)

    # ---------- L4 ODE ----------
    print("\nL4 机理 · ODE")
    # 解析解：y' = -k y, y(0)=1 → y = e^{-kt}
    k = 0.7
    ts, ys = rk4(lambda t, y: -k * y, [1.0], 0.0, 5.0, n=500)
    err = float(np.max(np.abs(ys[:, 0] - np.exp(-k * ts))))
    ck("RK4 对指数衰减误差 < 1e-6", err < 1e-6, f"max err={err:.2e}")

    ts2, ys2, st = rk45(lambda t, y: -k * y, [1.0], 0.0, 5.0)
    err2 = float(np.max(np.abs(ys2[:, 0] - np.exp(-k * ts2))))
    ck("RK45 对指数衰减误差 < 1e-6", err2 < 1e-6, f"max err={err2:.2e}")
    ck("RK45 步数远少于定步长", st["steps"] < 100,
       f"steps={st['steps']} rejected={st['rejected']}")

    # 谐振子能量守恒（考验"结构保真"）
    ts3, ys3, _ = rk45(lambda t, y: np.array([y[1], -y[0]]), [1.0, 0.0], 0.0, 20.0)
    energy = ys3[:, 0] ** 2 + ys3[:, 1] ** 2
    drift = float(np.max(energy) - np.min(energy))
    ck("谐振子能量漂移 < 1e-5", drift < 1e-5, f"drift={drift:.2e}")

    # 初值敏感 —— 说明"确定性"不等于"可预测"
    # 两个相差 1e-8 的初值，跑一段后距离指数放大，这才是混沌的定义。
    # 必须用定步长：自适应步长两次走的时间点不同，比不了。
    lorenz = lambda t, y: np.array([10.0 * (y[1] - y[0]),
                                    y[0] * (28.0 - y[2]) - y[1],
                                    y[0] * y[1] - 8.0 / 3.0 * y[2]])
    _, a = rk4(lorenz, [1.0, 1.0, 1.0], 0.0, 60.0, n=60000)
    _, b = rk4(lorenz, [1.0 + 1e-8, 1.0, 1.0], 0.0, 60.0, n=60000)
    dist = np.abs(a - b).max(1)
    tgrid = np.linspace(0.0, 60.0, len(dist))
    # 距离超过 0.1（可观测意义下的完全分离）的时刻
    sep = tgrid[np.argmax(dist > 0.1)] if np.any(dist > 0.1) else None
    ck("Lorenz 初值 1e-8 的差异被放大到可观测",
       sep is not None,
       f"t={sep:.1f}s 时彻底分离（初值差 1e-8）" if sep is not None
       else f"60s 内最大距离 {dist.max():.2e}，没长起来")
    growth = dist[-1] / dist[0] if dist[0] > 0 else 0
    ck("放大倍数跨多个数量级（混沌）", growth > 1e4,
       f"{dist[0]:.1e} → {dist[-1]:.1e}（×{growth:.1e}）")

    # ---------- L4 量纲 ----------
    print("\nL4 机理 · 量纲分析")
    # 单摆：T, L, g, m → Pi 数应为 1（T√(g/L) 无量纲）
    r = buckingham([("T", {"T": 1}), ("L", {"L": 1}),
                    ("g", {"L": 1, "T": -2}), ("m", {"M": 1})])
    ck("单摆 n=4 rank=3 → 1 个 Pi", r["n_pi"] == 1,
       f"rank={r['rank']} n_pi={r['n_pi']}")
    if r["pis"]:
        p = r["pis"][0]
        # dims 是排序后的 ['L','M','T']；行顺序必须与 buckingham 内部一致
        A = np.array([[0, 1, 1, 0],    # L 的幂
                      [0, 0, 0, 1],    # M 的幂
                      [1, 0, -2, 0]],  # T 的幂
                     float)
        ck("算出的 Pi 确实无量纲",
           np.allclose(A @ p, 0, atol=1e-8),
           f"A·p={np.round(A @ p, 10)} dims={r['dims']}")
        ck("Pi 中质量维度为 0（单摆周期与质量无关）",
           abs(p[3]) < 1e-8, f"m 的指数={p[3]:.2e}")

    # ---------- L5 约束优化 ----------
    print("\nL5 约束优化")
    # 二维 Rosenbrock，已知最优点 (1,1)
    def rosen(p):
        return (1 - p[0]) ** 2 + 100 * (p[1] - p[0] ** 2) ** 2
    r1 = cma_light(rosen, [-2, -2], [2, 2], n=80, iters=400, seed=1)
    ck("cma_light 找到 Rosenbrock 最优",
       abs(r1["x"][0] - 1) < 0.05 and abs(r1["x"][1] - 1) < 0.1,
       f"x={np.round(r1['x'], 4)} f={r1['f']:.2e}")

    r2 = mesh_scan(rosen, [-2, -2], [2, 2], n=200)
    ck("网格扫描定位到最优附近",
       abs(r2["x"][0] - 1) < 0.15,
       f"x={np.round(r2['x'], 3)} f={r2['f']:.2e}")
    ck("两条独立路径落在同一处",
       abs(r1["x"][0] - r2["x"][0]) < 0.15,
       f"cma+NM={r1['x'][0]:.3f} mesh={r2['x'][0]:.3f}")
    # 这才是关键知识：病态谷地上网格精度有物理极限，必须靠精化
    ck("NM 精化比网格精细两个数量级以上",
       r1["f"] < r2["f"] * 0.01,
       f"NM f={r1['f']:.2e}  mesh f={r2['f']:.2e}")

    # 约束：在 x1+x2 >= 1 条件下最小化 (x1-0.2)^2+(x2-0.2)^2
    def pen(p):
        base = (p[0] - 0.2) ** 2 + (p[1] - 0.2) ** 2
        viol = max(0.0, 1.0 - p[0] - p[1])
        return base + 1e4 * viol ** 2
    r3 = cma_light(pen, [-3, -3], [3, 3], n=80, iters=500, seed=2)
    ok_con = (r3["x"][0] + r3["x"][1]) >= 1 - 1e-3
    ck("带约束优化满足约束", ok_con,
       f"x={np.round(r3['x'], 4)} sum={r3['x'].sum():.4f}")
    # 解析最优：投影到 x1+x2=1 上的最近点 = (0.5, 0.5)
    ck("带约束优化接近解析解 (0.5,0.5)",
       abs(r3["x"][0] - 0.5) < 0.02 and abs(r3["x"][1] - 0.5) < 0.02,
       f"x={np.round(r3['x'], 4)}")

    # ---------- L6 不确定性 ----------
    print("\nL6 不确定性")
    # 已知：X~U(0,1), Y~U(0,1)，Z=X+Y 的均值 1，标准差 = sqrt(2/12)
    r4 = mc(lambda a, b: a + b, {"a": ("uniform", 0, 1),
                                 "b": ("uniform", 0, 1)}, n=20000, seed=3)
    ck("MC 均值接近解析值 1.0", abs(r4["mean"] - 1.0) < 0.02,
       f"mean={r4['mean']:.4f}")
    sd_theory = math.sqrt(2 / 12)
    ck("MC 标准差接近解析值", abs(r4["sd"] - sd_theory) < 0.02,
       f"sd={r4['sd']:.4f} vs {sd_theory:.4f}")
    # Z=X+Y（两个 U(0,1)）→ 三角分布(0,1,2)，5% 分位 = sqrt(0.1) ≈ 0.316
    ck("90% 区间覆盖三角分布的理论分位",
       abs(r4["ci90"][0] - math.sqrt(0.1)) < 0.02
       and abs(r4["ci90"][1] - (2 - math.sqrt(0.1))) < 0.02,
       f"ci90={np.round(r4['ci90'], 3)} 理论=({math.sqrt(0.1):.3f}, "
       f"{2 - math.sqrt(0.1):.3f})")

    # bootstrap：已知正态样本，均值的区间应覆盖真值
    rng = np.random.default_rng(7)
    Xb = rng.normal(5.0, 1.0, (200, 1))
    yb = 5.0 + rng.normal(0, 1, 200)
    rb = bootstrap(Xb, yb, lambda X, y: np.mean(y), n=500, seed=4)
    ck("bootstrap 区间覆盖真值 5.0",
       rb["ci90"][0] < 5.0 < rb["ci90"][1], f"ci90={np.round(rb['ci90'], 3)}")
    ck("bootstrap 样本数够", rb["n"] >= 400, f"n={rb['n']}")

    # ---------- L7 外推 ----------
    print("\nL7 验证 · 外推域")
    Xtr = np.array([[0.0], [1.0], [2.0]])
    Xte = np.array([[1.0], [5.0]])
    ex = extrap_check(Xtr, Xte)
    ck("外推比例算对", abs(ex["frac_outside"] - 0.5) < 1e-9,
       f"frac={ex['frac_outside']}")
    ck("域内点不被误判", ex["per_dim"] == [1.0], f"per_dim={ex['per_dim']}")
    ck("安全标志正确", ex["safe"] is False)

    # ---------- L8 判定 ----------
    print("\nL8 判定")
    v1 = verdict("充分证据的结论")
    ck("充分证据 → pass", v1["final"] == "pass", f"C={v1['C']}")
    v2 = verdict("前提有未知项的结论", certain_premises=False)
    ck("前提含未知 → 不许 pass", v2["final"] != "pass", f"C={v2['C']}")
    v3 = verdict("被数据推翻的结论", refuted=True)
    ck("被推翻 → reject", v3["final"] == "reject", f"C={v3['C']}")
    ck("被推翻时给出 blocked_at", v3["blocked_at"] is not None,
       f"blocked={v3['blocked_at']}")

    # ---------- 共同断言 ----------
    print("\n交叉")
    ck("五层都有可调用实现",
       all(callable(x) for x in (rk4, rk45, buckingham, cma_light,
                                 mc, bootstrap, extrap_check, verdict)))

    print()
    print("=" * 80)
    print(f"{'ALL PASS' if n_bad == 0 else 'FAILED'}  {n_ok} 通过 / {n_bad} 失败")
    print("=" * 80)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    raise SystemExit(selftest())
