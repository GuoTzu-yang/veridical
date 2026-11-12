"""小规模混合整数规划：两阶段单纯形 + 分支定界。

为什么需要
----------
`mmkit solve` 只做连续优化。APMCM 的 D 题（量子机组组合）经典部分是
混合整数规划，A 题的关节/任务分配、排班、选址、背包也都是整数问题。
本机没有 scipy / pulp / ortools，所以自己实现。

实现
----
  1. `linprog_max`：两阶段单纯形，解 max cᵀx s.t. Ax ≤ b, x ≥ 0
     （b 允许为负：先加人工变量求可行基，再切回原目标）
  2. `mip`：分支定界。深度优先 + 最佳界剪枝，变量可为
     'cont'（连续）/ 'int'（整数）/ 'bin'（0-1）

正确性怎么保证
--------------
自检里同时做两件事：
  · 与**手算已知解**对比（小 LP、背包、指派）
  · 与**暴力枚举**对比（≤12 个 0-1 变量时枚举所有组合）
两条独立路径都过，才认为实现对。分支定界会把单纯形的错误成倍放大，
所以这里是「先证 LP 对，再证 BB 对」。

用法
    python tools/mip.py selftest
    # 代码里：
    from tools.mip import mip
    r = mip(c=[3,2,4], A=[[2,1,3]], b=[4], types=['bin','bin','bin'])
"""
import argparse
import itertools
import math
import sys

import numpy as np

EPS = 1e-9


# ══════════════════════════════════════════════════════════════════════
#  两阶段单纯形
# ══════════════════════════════════════════════════════════════════════
def _pivot(T, r, j):
    T[r] = T[r] / T[r, j]
    for i in range(T.shape[0]):
        if i != r and abs(T[i, j]) > EPS:
            T[i] -= T[i, j] * T[r]


def _simplex_core(T, basis, ncols, obj_row):
    """在给定 tableau 上迭代到最优。返回 (status)。"""
    m = T.shape[0] - 1
    for _ in range(5000):
        # Bland 规则防循环：选第一个负检验数
        j = -1
        for k in range(ncols):
            if T[obj_row, k] < -EPS:
                j = k
                break
        if j < 0:
            return "optimal"
        best = None
        for i in range(m):
            if T[i, j] > EPS:
                ratio = T[i, -1] / T[i, j]
                if best is None or ratio < best[0] - EPS:
                    best = (ratio, i)
        if best is None:
            return "unbounded"
        _pivot(T, best[1], j)
        basis[best[1]] = j
    return "maxiter"


def linprog_max(c, A, b):
    """max cᵀx s.t. Ax ≤ b, x ≥ 0。

    返回 dict(status, x, obj)。b 可为负（走两阶段）。
    """
    c = np.asarray(c, float)
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    m, n = A.shape

    # 先把 b<0 的行乘 -1，变成 ≥，需要剩余变量与人工变量 —— 统一走两阶段
    n_slack = m
    n_art = m
    total = n + n_slack + n_art + 1          # +1 是 RHS 列

    T = np.zeros((m + 1, total))
    for i in range(m):
        row_sign = 1.0
        if b[i] < 0:
            row_sign = -1.0
        T[i, :n] = A[i] * row_sign
        T[i, -1] = b[i] * row_sign
        # 松弛变量：≤ 加 +1，≥（原 b<0）加 -1
        T[i, n + i] = 1.0 if row_sign > 0 else -1.0
        # 人工变量
        T[i, n + n_slack + i] = 1.0

    basis = [n + n_slack + i for i in range(m)]

    # 阶段一：最小化人工变量之和
    T[m, :] = 0.0
    T[m, -1] = 0.0
    for i in range(m):
        T[m, :] -= T[i, :]                  # 目标行 = -Σ(人工行)
    for i in range(m):
        T[m, n + n_slack + i] = 0.0         # 人工变量自身系数归零（基变量）

    st1 = _simplex_core(T, basis, n + n_slack + n_art, m)
    if st1 not in ("optimal",):
        return dict(status=st1, x=None, obj=None)
    # 人工变量必须全部为 0
    art_sum = sum(T[i, -1] for i in range(m)
                  if basis[i] >= n + n_slack)
    if art_sum > 1e-7:
        return dict(status="infeasible", x=None, obj=None)

    # 阶段一结束：把仍在基里的人工变量**换出**。
    # 只把它们的检验数设成大正数是不够的 —— 人工变量占着基，对应的那一行
    # 在阶段二不参与约束，等价于那条约束被丢掉。实测后果：分支定界加的
    # x_i ≥ ceil 约束完全不生效，LP 反复返回同一个分数解，递归不终止。
    for i in range(m):
        if basis[i] >= n + n_slack:
            for j in range(n + n_slack):
                if abs(T[i, j]) > EPS:
                    _pivot(T, i, j)
                    basis[i] = j
                    break

    # 阶段二：把人工列从 tableau 里"赶走"（系数清零，不再参与）
    T[m, :] = 0.0
    T[m, :n] = -c
    T[m, -1] = 0.0
    for i in range(m):
        if basis[i] < n and abs(T[m, basis[i]]) > EPS:
            T[m, :] -= T[m, basis[i]] * T[i, :]
    # 禁止人工变量再次入基：把它们的检验数设成大正数
    for i in range(m):
        T[m, n + n_slack + i] = 1e6

    st2 = _simplex_core(T, basis, n + n_slack + n_art, m)
    if st2 not in ("optimal",):
        return dict(status=st2, x=None, obj=None)

    x = np.zeros(n + n_slack + n_art)
    for i in range(m):
        if basis[i] < n + n_slack:
            x[basis[i]] = T[i, -1]
    obj = float(np.dot(c, x[:n]))
    return dict(status="optimal", x=x[:n], obj=obj)


# ══════════════════════════════════════════════════════════════════════
#  分支定界
# ══════════════════════════════════════════════════════════════════════
def mip(c, A, b, types=None, maximize=True, max_nodes=20000):
    """混合整数规划。types: 'cont' / 'int' / 'bin'。"""
    c = np.array(c, float)
    A = np.array(A, float)
    b = np.array(b, float)
    n = len(c)
    types = types or ["cont"] * n
    if not maximize:
        c = -c

    # 0-1 变量必须显式加上界 x_i ≤ 1。
    # 早期版本漏了这一步，松弛解直接给 x2=4（背包 obj 从 6 涨到 8），
    # 分支定界于是永远剪不到正确解 —— 没有上界的整数变量不是 0-1 变量。
    extra_rows = []
    extra_b = []
    for i, t in enumerate(types):
        if t == "bin":
            row = np.zeros(n)
            row[i] = 1.0
            extra_rows.append(row)
            extra_b.append(1.0)
    if extra_rows:
        A = np.vstack([A] + extra_rows)
        b = np.concatenate([b, np.array(extra_b)])

    best = dict(obj=-np.inf, x=None)
    nodes = [0]
    lb_global = -np.inf

    def solve_node(A_extra, b_extra, ub):
        A2 = np.vstack([A, A_extra]) if len(A_extra) else A
        b2 = np.concatenate([b, b_extra]) if len(b_extra) else b
        r = linprog_max(c, A2, b2)
        return r

    def search(A_extra, b_extra, depth=0):
        nonlocal lb_global
        nodes[0] += 1
        if nodes[0] > max_nodes or depth > 60:
            return
        r = solve_node(A_extra, b_extra, None)
        if r["status"] != "optimal":
            return
        if r["obj"] <= lb_global + EPS:      # 界剪枝
            return
        # 检查整数性
        viol = -1
        for i in range(n):
            if types[i] == "cont":
                continue
            v = r["x"][i]
            if abs(v - round(v)) > 1e-6:
                viol = i
                break
        if viol < 0:
            if r["obj"] > best["obj"]:
                best["obj"] = r["obj"]
                best["x"] = r["x"].copy()
                lb_global = r["obj"]
            return
        # 分支：x_i ≤ floor  /  x_i ≥ ceil
        v = r["x"][viol]
        flo, cei = math.floor(v), math.ceil(v)
        e1 = np.zeros(n); e1[viol] = 1.0
        # x_i ≤ flo
        search(np.vstack([A_extra, e1]), np.append(b_extra, flo), depth + 1)
        # x_i ≥ cei  →  -x_i ≤ -cei
        search(np.vstack([A_extra, -e1]), np.append(b_extra, -cei), depth + 1)

    search(np.zeros((0, n)), np.zeros(0), 0)
    if best["x"] is None:
        return dict(status="infeasible", x=None, obj=None, nodes=nodes[0])
    obj = best["obj"] if maximize else -best["obj"]
    return dict(status="optimal", x=best["x"], obj=obj, nodes=nodes[0])


def brute_force(c, A, b, types, maximize=True):
    """枚举 0-1 / 小整数解，用于交叉验证。"""
    n = len(c)
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    ranges = []
    for t in types:
        if t == "bin":
            ranges.append([0, 1])
        elif t == "int":
            ranges.append(list(range(0, 6)))
        else:
            ranges.append([0])          # 连续变量不支持，测试时不用
    best, bestx = -np.inf, None
    for combo in itertools.product(*ranges):
        x = np.array(combo, float)
        if np.all(A @ x <= b + 1e-9):
            v = float(np.dot(c, x))
            if v > best:
                best, bestx = v, x
    if bestx is None:
        return dict(status="infeasible", x=None, obj=None)
    return dict(status="optimal", x=bestx,
                obj=best if maximize else -best)


# ══════════════════════════════════════════════════════════════════════
def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %-36s %s" % ("PASS" if cond else "FAIL", name, detail))

    # ── LP：先证单纯形对 ──
    r = linprog_max([1, 1], [[1, 0], [0, 1]], [1, 1])
    ck("LP max x+y, x≤1,y≤1 = 2", abs(r["obj"] - 2) < 1e-7, "%.6f" % r["obj"])

    r = linprog_max([3, 2], [[1, 1], [1, 0]], [4, 2])
    # max 3x+2y, x+y≤4, x≤2 → x=2,y=2 → 10
    ck("LP 顶点解 = 10", abs(r["obj"] - 10) < 1e-7, "%.6f" % r["obj"])

    r = linprog_max([1, 1], [[-1, -1]], [-5])
    # x+y ≥ 5（无上界）→ 无界
    ck("无界判定", r["status"] == "unbounded", r["status"])

    r = linprog_max([1], [[1], [-1]], [3, -5])
    # x ≤ 3 且 x ≥ 5 → 不可行
    ck("不可行判定", r["status"] == "infeasible", r["status"])

    r = linprog_max([1, 2], [[-1, -1]], [-2])
    # x+y ≥ 2, max x+2y → 无界
    ck("b<0 行也能识别无界", r["status"] == "unbounded", r["status"])

    # ── MIP：再证分支定界对 ──
    # 背包：max 3x1+2x2+4x3, 2x1+x2+3x3 ≤ 4, 0-1
    r = mip([3, 2, 4], [[2, 1, 3]], [4], ["bin", "bin", "bin"])
    ck("0-1 背包 = 6 (x2=x3=1)", abs(r["obj"] - 6) < 1e-7,
       "obj=%.4f x=%s" % (r["obj"], np.round(r["x"], 3).tolist()))

    # 与暴力枚举对比
    cases = [
        ([5, 4, 3, 7], [[2, 3, 1, 4]], [7]),
        ([1, 2, 3, 4, 5], [[1, 2, 2, 3, 1]], [5]),
        ([10, 13, 18, 31, 7, 15], [[1, 2, 3, 5, 1, 3]], [8]),
    ]
    for ci, (cc, AA, bb) in enumerate(cases, 1):
        t = ["bin"] * len(cc)
        r1 = mip(cc, AA, bb, t)
        r2 = brute_force(cc, AA, bb, t)
        same = (r1["status"] == r2["status"] and
                (r1["obj"] is None or abs(r1["obj"] - r2["obj"]) < 1e-7))
        ck("背包案例 %d 与枚举一致" % ci, same,
           "mip=%.3f bf=%.3f" % (r1["obj"] or 0, r2["obj"] or 0))

    # 整数变量（非 0-1）：max x1+x2, 2x1+3x2 ≤ 7, 整数
    r = mip([1, 1], [[2, 3]], [7], ["int", "int"])
    # 枚举：x1=2,x2=1 → 3；x1=0,x2=2 → 2；最佳 3
    ck("整数规划 = 3", abs(r["obj"] - 3) < 1e-7,
       "obj=%.4f x=%s" % (r["obj"], np.round(r["x"], 3).tolist()))

    # 指派问题（2×2）：max 3x11+5x12+4x21+2x22, 每行每列和为 1
    # 变量顺序 x11,x12,x21,x22；最优是 x12+x21 = 5+4 = 9
    # （另一分配 x11+x22 = 3+2 = 5）。这里用枚举交叉验证，不靠手算期望值 ——
    # 在此之前我已经两次把期望值算错（排队论、这里）。
    A = [[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0], [0, 1, 0, 1]]
    b = [1, 1, 1, 1]
    r = mip([3, 5, 4, 2], A, b, ["bin"] * 4)
    r2 = brute_force([3, 5, 4, 2], A, b, ["bin"] * 4)
    ck("指派问题与枚举一致", abs(r["obj"] - r2["obj"]) < 1e-7,
       "mip=%.3f bf=%.3f x=%s" % (r["obj"], r2["obj"],
                                  np.round(r["x"], 3).tolist()))
    # 断言行和列都恰好为 1
    xa = np.array(r["x"])
    rows_ok = abs(xa[0] + xa[1] - 1) < 1e-9 and abs(xa[2] + xa[3] - 1) < 1e-9
    cols_ok = abs(xa[0] + xa[2] - 1) < 1e-9 and abs(xa[1] + xa[3] - 1) < 1e-9
    ck("指派解满足行列约束", rows_ok and cols_ok,
       str(np.round(xa, 3).tolist()))

    # 最小化：min 2x+3y, x+y ≥ 4, 整数 → x=4,y=0 → 8
    r = mip([2, 3], [[-1, -1]], [-4], ["int", "int"], maximize=False)
    ck("最小化整数规划 = 8", abs(r["obj"] - 8) < 1e-7,
       "obj=%.4f x=%s" % (r["obj"], np.round(r["x"], 3).tolist()))

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="小规模 MIP（单纯形 + 分支定界）")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    if a.demo:
        r = mip([3, 2, 4], [[2, 1, 3]], [4], ["bin", "bin", "bin"])
        print("背包 demo: obj=%.4f  x=%s  nodes=%d"
              % (r["obj"], np.round(r["x"], 3).tolist(), r["nodes"]))
        return 0
    return selftest()


if __name__ == "__main__":
    raise SystemExit(main())
