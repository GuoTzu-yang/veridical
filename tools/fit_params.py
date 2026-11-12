"""参数拟合：给定模型表达式与数据，反演参数。

为什么需要它
------------
APMCM 的 A/B/D 三题都是机理题：先写出机理模型（含未知参数），再用数据拟合。
`mmkit ode` 只能「给参数 → 算结果」，不能「给结果 → 找参数」。缺这一步，
机理题全部做不了。

方法（不依赖 scipy）
------------------
1) 随机搜索：在给定区间内撒 N 组参数，算 RMSE
2) 坐标下降细化：从最优若干组出发，逐维试探步长，逐步收缩
本机无 scipy，所以全部手写。

用法
----
  python tools/fit_params.py --data X.xlsx --x carat --y price \
         --rhs "a*x**3 + b*x**2 + c*x + d" --params a,b,c,d \
         --bounds "a:-10,10;b:-10,10;c:-10,10;d:-10,10"

  python tools/fit_params.py selftest        # 内置自检

模型表达式里可用：
  x            自变量
  a,b,c,...    待拟合参数（--params 里列出的名字）
  表达式是 Python 语法，** 表示乘方。
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 数据读取 ────────────────────────────────────────────────────────────
def load_xy(path, xcol, ycol):
    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("需要 pandas")
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    if xcol not in df.columns or ycol not in df.columns:
        raise SystemExit("列不存在。可用列：%s" % list(df.columns))
    d = df[[xcol, ycol]].dropna()
    return d[xcol].to_numpy(float), d[ycol].to_numpy(float)


# ── 模型求值 ────────────────────────────────────────────────────────────
def make_fn(rhs, pnames):
    """把 rhs 编译成一个 (x, params_dict) -> y 的函数。

    表达式的可用范围要显式列出：只给内置数学函数，不给 __builtins__。
    早期版本只放了 x 与参数名，于是 `A*exp(-k*x)` 报 NameError: exp。
    """
    code = compile(rhs, "<model>", "eval")
    ns = {
        "__builtins__": {},
        "exp": math.exp, "log": math.log, "log10": math.log10,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "atan": math.atan, "atan2": math.atan2,
        "pi": math.pi, "e": math.e, "abs": abs, "pow": pow,
        "min": min, "max": max, "round": round,
    }

    def f(x, pd):
        ns.update(pd)
        ns["x"] = x
        return eval(code, ns)

    return f


def residual(fn, x, y, pd):
    try:
        s = 0.0
        for xi, yi in zip(x, y):
            v = fn(xi, pd)
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                return float("inf")
            s += (v - yi) ** 2
        return math.sqrt(s / len(x))
    except Exception:
        return float("inf")


# ── 优化 ────────────────────────────────────────────────────────────────
def random_search(fn, x, y, pnames, bounds, n=4000, seed=0):
    import random
    rng = random.Random(seed)
    best = None
    for _ in range(n):
        pd = {k: rng.uniform(*bounds[k]) for k in pnames}
        r = residual(fn, x, y, pd)
        if best is None or r < best[0]:
            best = (r, dict(pd))
    return best


def coord_descent(fn, x, y, pnames, bounds, start, rounds=20, shrink=0.6):
    """逐维试探：每维试 ±step（及半 step），接受改进；每轮 step *= shrink。

    rounds 与 shrink 实测调参：rounds=6/shrink=0.5 时线性模型只能到
    a=2.64（真值 2.5），因为步长最小只降到 0.25*span*0.5^6≈0.004，
    而 a 的容差要求 0.02 以内需要更细。20 轮 0.6 收缩可到 3.6e-5*span。
    """
    r0, pd = start
    spans = {k: (bounds[k][1] - bounds[k][0]) for k in pnames}
    step = {k: 0.20 * spans[k] for k in pnames}
    best = (r0, dict(pd))
    for _ in range(rounds):
        improved = False
        for k in pnames:
            lo, hi = bounds[k]
            for sgn in (+1, -1):
                for mult in (1.0, 0.5):
                    cand = dict(best[1])
                    v = cand[k] + sgn * mult * step[k]
                    if v < lo or v > hi:
                        continue
                    cand[k] = v
                    r = residual(fn, x, y, cand)
                    if r < best[0] - 1e-15:
                        best = (r, cand)
                        improved = True
        if not improved:
            for k in pnames:
                step[k] *= shrink
    return best


def _clip(pd, bounds, pnames):
    return {k: min(max(pd[k], bounds[k][0]), bounds[k][1]) for k in pnames}


def nelder_mead(fn, x, y, pnames, bounds, start, max_iter=800, tol=1e-13):
    """Nelder–Mead 单纯形。

    为什么需要：坐标下降逐维搜索，在参数强相关（如线性模型的斜率与截距）
    时会沿一条平坦谷缓慢爬行。实测 DWTS 的 placement~judge_avg 只得
    a=-1.2206，而最小二乘真值是 -1.2377，差 1.4%。单纯形走几何方向，
    对相关参数更稳。
    """
    n = len(pnames)

    def f(pd):
        return residual(fn, x, y, pd)

    simplex = [_clip(dict(start), bounds, pnames)]
    for k in pnames:
        p = dict(simplex[0])
        span = bounds[k][1] - bounds[k][0]
        step = 0.05 * span if span > 0 else 0.1
        p[k] = min(bounds[k][1], p[k] + step)
        if p[k] == simplex[0][k]:
            p[k] = max(bounds[k][0], p[k] - step)
        simplex.append(p)
    vals = [f(p) for p in simplex]

    for _ in range(max_iter):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) <= tol * max(1.0, abs(vals[0])):
            break
        cen = {k: sum(simplex[i][k] for i in range(n)) / n for k in pnames}
        worst = simplex[-1]
        xr = _clip({k: cen[k] + (cen[k] - worst[k]) for k in pnames}, bounds, pnames)
        fr = f(xr)
        if fr < vals[0]:
            xe = _clip({k: cen[k] + 2.0 * (cen[k] - worst[k]) for k in pnames},
                       bounds, pnames)
            fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = _clip({k: cen[k] + 0.5 * (worst[k] - cen[k]) for k in pnames},
                       bounds, pnames)
            fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    simplex[i] = _clip(
                        {k: simplex[0][k] + 0.5 * (simplex[i][k] - simplex[0][k])
                         for k in pnames}, bounds, pnames)
                    vals[i] = f(simplex[i])
    best = min(range(n + 1), key=lambda i: vals[i])
    return vals[best], simplex[best]


# ── 主流程 ──────────────────────────────────────────────────────────────
def fit(data, xcol, ycol, rhs, pnames, bounds, n_random=4000, seeds=(0, 1, 2)):
    x, y = load_xy(data, xcol, ycol)
    fn = make_fn(rhs, pnames)

    best = None
    for s in seeds:
        cand = random_search(fn, x, y, pnames, bounds, n=n_random // len(seeds), seed=s)
        if cand and (best is None or cand[0] < best[0]):
            best = cand
    if best is None:
        raise SystemExit("随机搜索没有找到可行解")
    # 随机搜索定位大致区域 -> Nelder-Mead 走几何方向 -> 坐标下降收尾
    best = nelder_mead(fn, x, y, pnames, bounds, best[1])
    best = coord_descent(fn, x, y, pnames, bounds, best, rounds=12)

    rmse = best[0]
    ybar = sum(y) / len(y)
    sst = sum((v - ybar) ** 2 for v in y)
    sse = rmse ** 2 * len(y)
    r2 = 1 - sse / sst if sst > 0 else float("nan")
    yhat = [fn(xi, best[1]) for xi in x]
    resid = [yi - yhi for yi, yhi in zip(y, yhat)]

    return dict(
        data=os.path.basename(data), x=xcol, y=ycol, model=rhs,
        n=len(x), params={k: round(float(v), 6) for k, v in best[1].items()},
        rmse=round(rmse, 6), r2=round(float(r2), 6),
        resid_sd=round(float((sum(r ** 2 for r in resid) / len(resid)) ** 0.5), 6),
        note="参数由随机搜索 + 坐标下降得到；本机无 scipy，故为启发式解，非全局最优保证",
    )


def parse_bounds(s, pnames):
    b = {}
    if not s:
        for k in pnames:
            b[k] = (-100.0, 100.0)
        return b
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        k, rng = part.split(":", 1)
        lo, hi = rng.split(",")
        b[k.strip()] = (float(lo), float(hi))
    for k in pnames:
        b.setdefault(k, (-100.0, 100.0))
    return b


def selftest():
    import tempfile
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    # 造数据：y = 2.5*x + 1.2，带小噪声
    import random
    rng = random.Random(7)
    rows = ["x,y"]
    truth = dict(a=2.5, b=1.2)
    xs = [i / 10.0 for i in range(1, 61)]
    for xv in xs:
        rows.append("%.3f,%.6f" % (xv, truth["a"] * xv + truth["b"] + rng.gauss(0, 0.01)))
    tmp = os.path.join(tempfile.mkdtemp(), "lin.csv")
    open(tmp, "w", encoding="utf-8").write("\n".join(rows))

    r = fit(tmp, "x", "y", "a*x + b", ["a", "b"],
            {"a": (-10, 10), "b": (-10, 10)}, n_random=1500)
    ck("线性参数还原 a≈2.5", abs(r["params"]["a"] - 2.5) < 0.02, r["params"]["a"])
    ck("线性参数还原 b≈1.2", abs(r["params"]["b"] - 1.2) < 0.05, r["params"]["b"])
    ck("R² 接近 1", r["r2"] > 0.999, r["r2"])

    # 指数衰减：y = 3*exp(-0.5*x)
    rows = ["x,y"]
    for xv in xs:
        rows.append("%.3f,%.6f" % (xv, 3.0 * math.exp(-0.5 * xv)))
    tmp2 = os.path.join(tempfile.mkdtemp(), "exp.csv")
    open(tmp2, "w", encoding="utf-8").write("\n".join(rows))
    r2 = fit(tmp2, "x", "y", "A*exp(-k*x)", ["A", "k"],
             {"A": (0, 10), "k": (0, 5)}, n_random=1500)
    ck("指数参数还原 A≈3", abs(r2["params"]["A"] - 3.0) < 0.05, r2["params"]["A"])
    ck("指数参数还原 k≈0.5", abs(r2["params"]["k"] - 0.5) < 0.02, r2["params"]["k"])

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="参数拟合（机理模型反演）")
    ap.add_argument("--data", required=True)
    ap.add_argument("--x", required=True)
    ap.add_argument("--y", required=True)
    ap.add_argument("--rhs", required=True, help="模型表达式，用 x 与参数名")
    ap.add_argument("--params", required=True, help="参数名，逗号分隔")
    ap.add_argument("--bounds", default="", help="如 a:-10,10;b:0,5")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    pnames = [s.strip() for s in a.params.split(",") if s.strip()]
    b = parse_bounds(a.bounds, pnames)
    r = fit(a.data, a.x, a.y, a.rhs, pnames, b)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("参数拟合：%s" % r["model"])
        print("  数据 %s  n=%d  x=%s  y=%s" % (r["data"], r["n"], r["x"], r["y"]))
        for k, v in r["params"].items():
            print("    %-4s = %g" % (k, v))
        print("  RMSE = %.6g   R² = %.6g   残差 sd = %.6g"
              % (r["rmse"], r["r2"], r["resid_sd"]))
        print("  注：%s" % r["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
