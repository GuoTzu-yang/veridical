#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mmkit.py —— 数学建模插件的统一入口

解决的问题
----------
上一版有三个模块，各干各的：
    mm.py      算：体检 / 结构竞速 / 多目标 / 评价 / 灵敏度
    engine.py  算：ODE / 量纲 / 约束优化 / 不确定性
    lanes.py   验：八条通道并行，投票定结论

但 **mm.py 算完就完了** —— 它出的每条结论没人验；
lanes.py 能验，但要人手工把数据传进去。
中间那道缝，就是"算了一堆数，不知道哪条能写进论文"。

本文件把那道缝补上：
    算出来的东西 → 自动变成待验主张 → 并行验 → 出报告

一条命令
--------
    python mmkit.py run --data 附件.xlsx --y 热阻 --x 宽度,深高,排数

带主张（可判 reject）
    python mmkit.py run ... --claim 深高:负 --claim 宽度:负

关键设计：数据提示 ≠ 结论主张
--------------------------
不给 --claim 时，工具会算偏相关，但它**不会把这些当成结论**。
它会把它们标成「数据提示」并明确写：

    提示 = 数据里看到的；主张 = 你写进论文的。
    提示最多给到「中」，因为没人声明方向，direction 通道无从判起。

给了 --claim，才进入「可被推翻」的验证。

这是少幻觉的机制层做法：**不许工具替你造主张。**

跑法
----
    python mmkit.py run  --data X --y 热阻 --x 宽度,深高,排数
    python mmkit.py run  --data X --y 热阻 --x 宽度,深高,排数 --claim 深高:负
    python mmkit.py selftest
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import numpy as np
import re as _remod
_re_cjk = _remod.compile(r"[\u4e00-\u9fff]+")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lanes                                                        # noqa: E402
import paper as _paper                                             # noqa: E402
import i18n as _i18n                                             # noqa: E402
import advise as _advise                                          # noqa: E402
import multisrc as _ms                                            # noqa: E402
import video as _video                                            # noqa: E402
import mm                                                           # noqa: E402

def _say(*a, **kw):
    """提示输出。

    --json 时 main() 已经把 sys.stdout 指到 stderr，所以这里
    只要普通 print 就会走 stderr；JSON 另由 _emit 写真 stdout。
    """
    print(*a, **kw)


def _emit(obj):
    """JSON 输出：始终写真正的 stdout，不受 --json 重定向影响。

    入参可能是对象，也可能是已经 dumps 过的字符串（调用点两种都有）；
    对字符串再 dumps 一次会得到转义后的一长串，所以先判类型。
    """
    if isinstance(obj, str):
        print(obj, file=sys.__stdout__)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2,
                         default=str), file=sys.__stdout__)


DIR_WORD = {"正": +1, "增": +1, "上升": +1, "+": +1, "+1": +1,
            "负": -1, "减": -1, "下降": -1, "-": -1, "-1": -1}


# ══════════════════════════════════════════════════════════════════════
#  偏相关：方向判定的底层量
# ══════════════════════════════════════════════════════════════════════
def partial_corr(X: np.ndarray, y: np.ndarray, j: int) -> float | None:
    """第 j 个自变量对 y 的偏相关（控制其余自变量）。

    为什么不用简单相关：三个自变量互相关时，简单相关会把别人的效应
    算到这一个头上 —— 那正是辛普森悖论的入口。

    返回 None 的两种情况（都要报给用户，不能静默给个垃圾数）：
      · 这一列被其余列线性解释光了（共线，或本身就是常数）
      · y 是常数

    第 84 轮修：原来是 `if denom <= 0` 精确比较，
    但常数列残差化之后是 1e-11 量级的浮点噪声、不是精确 0，
    于是漏过去，返回 -7.86e-11 这种垃圾值，还被写成
    「与噪声不可区分」——真相比这严重：那列根本没有信息。
    现在用**相对**判定，与量纲无关。
    """
    n = len(y)
    if n < 5:
        return None
    others = np.delete(X, j, axis=1)
    A = np.hstack([np.ones((n, 1)), others]) if others.size else np.ones((n, 1))
    ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    rx = X[:, j] - A @ np.linalg.lstsq(A, X[:, j], rcond=None)[0]

    nx = float(np.sum(rx ** 2))
    ny = float(np.sum(ry ** 2))
    sx = float(np.sum(X[:, j] ** 2))
    sy = float(np.sum(y ** 2))
    # 残差相对总量小到浮点噪声级别 → 这一路没有可用信息
    if nx <= 1e-12 * max(1.0, sx) or ny <= 1e-12 * max(1.0, sy):
        return None
    denom = math.sqrt(nx * ny)
    if denom <= 0:
        return None
    return float(np.sum(rx * ry)) / denom


def all_partial(ds, yname: str, xnames: list[str]) -> list[dict]:
    """每个自变量对 y 的偏相关，**连同样本量和显著性一起给**。

    第 84 轮修：原来方向判定用固定阈值 |pc| >= 0.05，与样本量无关。
    在真实数据上（水厂 3145 行）这会把 r=0.088 报成「正相关」——
    它确实显著（p<0.001），但只解释 0.8% 的方差，拿来当结论毫无意义。
    反过来，n=30 时 r=0.3 反而不显著。

    同一个相关系数在不同 n 下含义不同，所以必须一起给三样：
        临界值 r_crit ≈ 1.96/√(n-k-1)   （α=0.05 双侧的大样本近似）
        是否显著  |pc| >= r_crit
        解释力    r² = pc²（决定这个方向值不值得写进结论）
    """
    X, y = ds.cols(xnames), ds.col(yname)
    n, k = X.shape[0], len(xnames)
    dof = max(1, n - k - 1)
    r_crit = float(1.96 / np.sqrt(dof)) if dof > 2 else 1.0
    out = []
    for j, nm in enumerate(xnames):
        pc = partial_corr(X, y, j)
        if pc is None:
            out.append(dict(name=nm, idx=j, pc=None, sign=0, n=n,
                            r_crit=r_crit, r2=None, significant=False,
                            usable=False,
                            note="算不出来：这列被其余列解释光了"
                                 "（常数，或与别的列完全共线）"))
            continue
        r2 = float(pc) * float(pc)
        sig = abs(pc) >= r_crit
        if not sig:
            sign = 0
            note = f"与噪声不可区分（|r|<临界 {r_crit:.4f}）"
        else:
            sign = 1 if pc > 0 else -1
            note = (f"显著，解释 {r2:.2%} 方差"
                    + ("—— 量级太小，不建议单独当结论" if r2 < 0.01 else ""))
        out.append(dict(name=nm, idx=j, pc=float(pc), sign=sign, n=n,
                        r_crit=r_crit, r2=r2, significant=sig,
                        usable=(sig and r2 >= 0.01), note=note))
    return out


# ══════════════════════════════════════════════════════════════════════
#  主张解析
# ══════════════════════════════════════════════════════════════════════
def parse_claims(specs: list[str], ds, xnames: list[str]) -> tuple[list[dict], list[str]]:
    """把 "深高:负" 这种写法解析成 {列索引: 方向}。

    返回 (主张列表, 解析不出来的项)。
    """
    claims, bad = [], []
    picked = ds.pick(xnames)
    for raw in specs or []:
        s = raw.strip()
        if not s:
            continue
        if ":" in s:
            head, tail = s.rsplit(":", 1)
        elif "=" in s:
            head, tail = s.rsplit("=", 1)
        else:
            bad.append(f"{raw}（没写方向，用 名字:正/负）")
            continue
        head, tail = head.strip(), tail.strip()
        want = DIR_WORD.get(tail) or DIR_WORD.get(tail.lower())
        if want is None:
            bad.append(f"{raw}（方向 {tail!r} 认不出，用 正/负）")
            continue
        # 模糊匹配列名
        hit = None
        for i, nm in enumerate(picked):
            if head and (head in nm or nm in head):
                hit = i
                break
        if hit is None:
            bad.append(f"{raw}（列名 {head!r} 匹配不到；有 {picked}）")
            continue
        claims.append(dict(name=picked[hit], idx=hit, want=want, raw=raw))
    return claims, bad


# ══════════════════════════════════════════════════════════════════════
#  约束优化求解（本轮新增）
# ══════════════════════════════════════════════════════════════════════
OPS = ("<=", ">=", "<", ">", "==")


def parse_constraint(s: str, ds) -> tuple[dict | None, str]:
    """把 "热阻<=0.74" 解析成 {col, op, val}。"""
    s = (s or "").strip()
    for op in OPS:
        if op in s:
            head, tail = s.split(op, 1)
            head, tail = head.strip(), tail.strip()
            try:
                val = float(tail)
            except ValueError:
                return None, f"{s!r}（右值 {tail!r} 不是数）"
            hit = None
            for i, nm in enumerate(ds.num_names):
                if head and (head in nm or nm in head):
                    hit = i
                    break
            if hit is None:
                return None, f"{s!r}（列名 {head!r} 匹配不到）"
            return dict(col=ds.num_names[hit], idx=hit, op=op, val=val), ""
    return None, f"{s!r}（没找到比较符 <= >= < > ==）"


def _fit_best(X, y):
    """按 K 折 CV 选结构，返回 (kind, coef, rmse)。"""
    best = None
    for kind in ("linear", "quad"):
        e = mm.kfold(X, y, kind)
        if e is None:
            continue
        rm = float(e.mean())
        if best is None or rm < best[2]:
            A = mm.design(X, kind)
            coef = np.linalg.lstsq(A, y, rcond=None)[0]
            best = (kind, coef, rm)
    return best


def solve_discrete(ds, xnames, obj, constraints, minimize=True) -> dict:
    """全离散自变量的组合搜索。

    为什么必须有这条路径：
        APMCM 附件里三个自变量都是离散的（5 / 4 / 6 个取值）。
        连续优化器会给出 (0.287, 3.67, 0.0) 这种**做不出来的参数组合** ——
        0.287 不是实验能设的值，3.67 更不是。
        对离散设计，正确的动作是**枚举组合**，不是跑到域中心去插值。

    诚实规则：枚举出来的组合分两类
        observed  —— 数据里真做过这一组，约束用**实测值**判
        predicted —— 数据里没有这一组，约束只能用**模型预测**判，
                     这类候选必须单独标出来，不许和观测点混在一起排名。
    """
    import itertools
    X = ds.cols(xnames)
    y_obj = ds.col(obj)
    p = X.shape[1]
    axes = [np.unique(X[:, j]) for j in range(p)]
    n_combos = int(np.prod([len(a) for a in axes]))

    # 观测索引：组合 → 行号
    idx_of = []
    for j in range(p):
        idx_of.append({float(v): i for i, v in enumerate(axes[j])})
    obs_map = {}
    for r in range(len(y_obj)):
        key = tuple(idx_of[j][float(X[r, j])] for j in range(p))
        obs_map.setdefault(key, []).append(r)

    cons = []
    bad = []
    for cs in constraints or []:
        c, why = parse_constraint(cs, ds)
        if c is None:
            bad.append(why)
        else:
            f = _fit_best(X, ds.col(c["col"]))
            cons.append(dict(**c, kind=(f[0] if f else None),
                             coef=(f[1] if f else None),
                             rmse=(f[2] if f else 0.0)))
    tol_map = {c["col"]: c["rmse"] for c in cons}

    def ok_actual(row):
        for c in cons:
            v = float(ds.col(c["col"])[row])
            if c["op"] == "<=" and not v <= c["val"] + 1e-12:
                return False
            if c["op"] == "<" and not v < c["val"]:
                return False
            if c["op"] == ">=" and not v >= c["val"] - 1e-12:
                return False
            if c["op"] == ">" and not v > c["val"]:
                return False
            if c["op"] == "==" and not abs(v - c["val"]) <= 1e-9:
                return False
        return True

    def ok_pred(x):
        for c in cons:
            if c["coef"] is None:
                return False
            A = mm.design(np.asarray(x).reshape(1, -1), c["kind"])
            pv = float((A @ c["coef"])[0])
            t = max(c["rmse"], 1e-12)
            if c["op"] == "<=" and pv > c["val"] + t:
                return False
            if c["op"] == "<" and pv > c["val"] + t:
                return False
            if c["op"] == ">=" and pv < c["val"] - t:
                return False
            if c["op"] == ">" and pv < c["val"] - t:
                return False
            if c["op"] == "==" and abs(pv - c["val"]) > t:
                return False
        return True

    kind_o, coef_o, rmse_o = _fit_best(X, y_obj)
    observed, predicted = [], []
    for combo in itertools.product(*(range(len(a)) for a in axes)):
        xx = [float(axes[j][combo[j]]) for j in range(p)]
        key = tuple(combo)
        if key in obs_map:
            for row in obs_map[key]:
                if ok_actual(row):
                    observed.append(dict(x=xx, obj=float(y_obj[row]),
                                         row=row + 1, kind="observed"))
        else:
            if ok_pred(xx):
                A = mm.design(np.asarray(xx).reshape(1, -1), kind_o)
                predicted.append(dict(x=xx, obj=float((A @ coef_o)[0]),
                                      row=None, kind="predicted"))

    key_f = (lambda d: d["obj"]) if minimize else (lambda d: -d["obj"])
    observed.sort(key=key_f)
    predicted.sort(key=key_f)
    return dict(ok=True, mode="discrete", kind=kind_o, rmse=rmse_o,
                n_combos=n_combos, n_observed_ok=len(observed),
                n_predicted_ok=len(predicted), constraints=cons, bad=bad,
                best_observed=observed[0] if observed else None,
                best_predicted=predicted[0] if predicted else None,
                top_observed=observed[:5], top_predicted=predicted[:5],
                axes=[a.tolist() for a in axes], tol_map=tol_map)


def print_solve_discrete(r: dict, xnames: list[str], obj: str) -> None:
    print()
    print(BAR)
    print(f"约束优化求解（离散组合搜索）· 目标 {obj}")
    print(BAR)
    print(f"  结构：{r['kind']}（CV RMSE={r['rmse']:.5f}）")
    print(f"  自变量全是离散取值：共 {r['n_combos']} 种组合")
    for nm, a in zip(xnames, r["axes"]):
        print(f"    {nm:<26}{len(a)} 个取值  例 {a[:6]}")
    print()
    if r["constraints"]:
        print("  约束：")
        for c in r["constraints"]:
            print(f"    {c['col']} {c['op']} {c['val']}"
                  f"（模型 CV RMSE {c['rmse']:.5f}）")
        print()
    print(f"  满足约束的**已观测**组合：{r['n_observed_ok']} 个")
    print(f"  满足约束的**未观测**组合（只能靠模型预测）："
          f"{r['n_predicted_ok']} 个")
    print()

    bo = r["best_observed"]
    bp = r["best_predicted"]
    if bo:
        print(f"  ★ 观测最优：第 {bo['row']} 行  {obj}={bo['obj']:.6f}")
        print(f"     {'  '.join(f'{nm}={v:.4g}' for nm, v in zip(xnames, bo['x']))}")
        print("     这是**真做过的**参数组合，可以直接写进论文。")
    else:
        print("  ✗ 没有任何已观测组合满足约束 —— 约束和数据打架，要回头查题。")
    print()
    if bp:
        print(f"  ? 预测最优：{obj}={bp['obj']:.6f}（**没做过**）")
        print(f"     {'  '.join(f'{nm}={v:.4g}' for nm, v in zip(xnames, bp['x']))}")
        if bo and (bp["obj"] < bo["obj"] if True else False):
            print("     模型说它比观测最优更好 —— 但这一组实验里没做过。")
            print("     论文里只能写成「模型预测」，不能写成「实验发现」。")
            print("     要写成发现，得补做这一组实验。")
    print()
    print("  为什么不用连续优化：这儿的自变量都是离散档位（实验只能设这几个值），")
    print("  连续优化会给出 0.287、3.67 这种做不出来的参数，那不是解，是插值产物。")


def solve_opt(ds, xnames: list[str], obj: str, constraints: list[str],
              minimize: bool = True, seed: int = 0) -> dict:
    """在约束下解最优（连续变量的路径）。

    全离散的自变量会先被路由到 solve_discrete —— 连续优化器对
    离散设计只会给出做不出来的中间值。
    """
    X0 = ds.cols(xnames)
    p0 = X0.shape[1]
    n_uniq = [len(np.unique(X0[:, j])) for j in range(p0)]
    if all(k <= 10 for k in n_uniq):
        return solve_discrete(ds, xnames, obj, constraints, minimize)

    # 以下是连续变量的路径。
    # 为什么不能只从帕累托前沿里挑：前沿只在观测点里选，
    # 而连续优化能在整个自变量域里找 —— 两者常常不是同一个点。
    # 代价是必须回答：**这个最优点是不是外推出来的？**
    # 所以结果里一定带 extrap 检查和最近观测点距离。
    import engine as eng

    X = ds.cols(xnames)
    y_obj = ds.col(obj)
    lo, hi = X.min(0), X.max(0)

    fit_obj = _fit_best(X, y_obj)
    if fit_obj is None:
        return dict(ok=False, why="目标列拟合失败")
    kind_o, coef_o, rmse_o = fit_obj

    cons = []
    bad = []
    for cs in constraints or []:
        c, why = parse_constraint(cs, ds)
        if c is None:
            bad.append(why)
        else:
            yc = ds.col(c["col"])
            f = _fit_best(X, yc)
            if f is None:
                bad.append(f"{cs!r}（约束列拟合失败）")
            else:
                cons.append(dict(**c, kind=f[0], coef=f[1], rmse=f[2]))

    BIG = 1e6

    def viol_vec(x):
        out = []
        for c in cons:
            A = mm.design(x.reshape(1, -1), c["kind"])
            pv = float((A @ c["coef"])[0])
            if c["op"] == "<=":
                out.append(max(0.0, pv - c["val"]))
            elif c["op"] == "<":
                out.append(max(0.0, pv - c["val"]))
            elif c["op"] == ">=":
                out.append(max(0.0, c["val"] - pv))
            elif c["op"] == ">":
                out.append(max(0.0, c["val"] - pv))
            else:
                out.append(abs(pv - c["val"]))
        return out

    # 先做可行性筛选：哪些**观测行**本来就满足全部约束
    if cons:
        flat = np.array([ds.col(c["col"]) for c in cons]).T
        masks = []
        for j, c in enumerate(cons):
            if c["op"] == "<=":
                masks.append(flat[:, j] <= c["val"])
            elif c["op"] == "<":
                masks.append(flat[:, j] < c["val"])
            elif c["op"] == ">=":
                masks.append(flat[:, j] >= c["val"])
            elif c["op"] == ">":
                masks.append(flat[:, j] > c["val"])
            else:
                masks.append(np.isclose(flat[:, j], c["val"], atol=1e-9))
        ok_rows = np.where(np.all(masks, axis=0))[0]
    else:
        ok_rows = np.arange(len(y_obj))

    # 求解策略：**从可行观测点出发做局部精化**，不是从域中心盲搜。
    #
    # 前面试过三版全局罚函数（单段平方 1e6、两段 1e4→1e9、线性+平方混合），
    # 三次都卡在约束外 5e-3 ~ 7e-3 下不来。
    # 根因不是罚项太小（罚项早就 1e4 量级，远大于目标 0.1），
    # 是 CMA 每次从域中心起步，三维里既要找盆地又要压约束，收敛不稳。
    #
    # 换一个更朴素也更可靠的办法：
    #   可行观测点 = 数据里本来就满足约束的行 —— 它们天然在数据支撑域内；
    #   从目标最好的几行出发做 NM 局部精化，只在附近挪动，不会跑到外推区。
    # 一个可行观测点都没有时，才退回全局 CMA。
    def _obj(x):
        A = mm.design(x.reshape(1, -1), kind_o)
        return float((A @ coef_o)[0])

    def _score(x):
        """硬约束：不可行直接判无穷。

        为什么不用罚函数：试过三版（平方 1e6 / 两段 1e4→1e9 / 线性+平方），
        全都卡在约束外 5e-3~7e-3。根因是**罚函数在可行域边界是断崖**，
        而 Nelder-Mead 的单纯形在断崖上会卡住 —— 罚项再大也没用，
        因为单纯形的顶点已经贴在崖上，收缩方向算不出来。
        硬拒绝让 inf 直接把单纯形推向可行侧，这才是对的。

        容差：约束边界和模型预测的差，量级可能小于模型自身的 CV RMSE。
        这种情况下"模型说越界"和"数据说不越界"会打架 ——
        实测第 46 行（热阻 0.7352、温度 0.7884）明明满足约束，
        二次模型却把它算成越界。所以容差取约束列拟合的 CV RMSE。
        """
        v = viol_vec(x)
        if v and max(v) > tol:
            return float("inf")
        return _obj(x) if minimize else -_obj(x)

    # 容差 = 约束模型自身的误差量级。比这更小的越界，模型没资格判。
    tol = max([c["rmse"] for c in cons], default=0.0) or 1e-12
    if not cons:
        tol = 1e-12

    # 起点：在连续域上粗采样，只留**模型认为可行**的点
    grid_n = 26 if X.shape[1] <= 3 else 12
    axes = [np.linspace(lo[i], hi[i], grid_n) for i in range(X.shape[1])]
    mesh = np.meshgrid(*axes, indexing="ij")
    pts = np.column_stack([mq.ravel() for mq in mesh])
    feas = []
    for p in pts:
        v = viol_vec(p)
        if not v or max(v) <= tol:
            feas.append(p)
    grid_feasible = len(feas)
    mode = "grid"
    if feas:
        feas = np.array(feas)
        vals = np.array([_obj(p) for p in feas])
        order = np.argsort(vals if minimize else -vals)
        starts = feas[order[:5]]
    elif len(ok_rows):
        starts = X[ok_rows][:5]
        mode = "obs-only"
    else:
        starts = np.array([lo + (hi - lo) / 2])
        mode = "center-only"

    best = None
    best_v = float("inf")
    for s in starts:
        nm = eng.nelder_mead(_score, s, lo, hi,
                             step=0.05 * float(np.mean(hi - lo)),
                             iters=2000)
        cand = np.asarray(nm["x"], float)
        cv = _score(cand)
        if cv < best_v:
            best_v, best = cv, cand
    res = dict(x=best if best is not None else starts[0],
               n_feasible=grid_feasible, n_obs_feasible=int(len(ok_rows)),
               tol=tol, mode=mode)
    x_best = np.asarray(res["x"], float)
    A = mm.design(x_best.reshape(1, -1), kind_o)
    pred_obj = float((A @ coef_o)[0])
    vv = viol_vec(x_best)
    max_viol = max(vv) if vv else 0.0

    # 最近观测点：判断是不是"数据里本来就有"
    d = np.sqrt(((X - x_best) ** 2 / (hi - lo + 1e-12) ** 2).sum(1))
    near = int(np.argmin(d))
    ex = eng.extrap_check(X, x_best.reshape(1, -1))

    # 对照：满足约束的观测行里，目标最好的那一行
    obs_best = None
    if len(ok_rows):
        k = ok_rows[np.argmin(y_obj[ok_rows]) if minimize
                    else np.argmax(y_obj[ok_rows])]
        obs_best = dict(row=int(k) + 1, obj=float(y_obj[k]),
                        x=[float(v) for v in X[k]])

    # 这个解到底可不可信 —— 四条硬检验
    flags = []
    if max_viol > max(tol, 1e-9):
        flags.append(f"约束没满足（越界 {max_viol:.2e}）")
    if obs_best is not None:
        better_than_obs = (pred_obj < obs_best["obj"] - 1e-9) if minimize \
            else (pred_obj > obs_best["obj"] + 1e-9)
        if not better_than_obs:
            flags.append(
                f"优化解（{pred_obj:.6f}）还不如观测里第 {obs_best['row']} 行"
                f"（{obs_best['obj']:.6f}）—— 模型在这块区域不可信")
    if not ex["safe"] or float(d[near]) > 0.15:
        flags.append(f"离最近观测点太远（{float(d[near]):.3f}），属于外推")
    if cons and len(ok_rows) < 3:
        flags.append(
            f"满足全部约束的观测行只有 {len(ok_rows)} 行 —— "
            f"数据不足以支撑连续优化，建议直接采用观测最优")

    return dict(ok=True, kind=kind_o, rmse=rmse_o, x=[float(v) for v in x_best],
                pred=pred_obj, feasible=max_viol <= max(tol, 1e-9),
                max_violation=max_viol, tol=tol,
                constraints=cons, bad=bad,
                nearest_row=near + 1,
                nearest_dist=float(d[near]),
                inside_domain=bool(ex["safe"]),
                obs_best=obs_best,
                n_grid_feasible=res.get("n_feasible"),
                n_obs_feasible=res.get("n_obs_feasible"),
                solver=res.get("mode"),
                trustworthy=(len(flags) == 0), flags=flags)


def print_solve(r: dict, xnames: list[str], obj: str, ds=None) -> None:
    print()
    print(BAR)
    print(f"约束优化求解 · 目标 {obj}")
    print(BAR)
    if not r.get("ok"):
        print(f"  失败：{r.get('why')}")
        return
    print(f"  结构：{r['kind']}（CV RMSE={r['rmse']:.5f}）")
    print()
    # 离散变量提示：连续优化在只有几个取值的列上给出的中间值要就近取整
    disc = {}
    if ds is not None:
        for nm, v in zip(xnames, r["x"]):
            u = np.unique(ds.col(nm))
            if len(u) <= 10:
                nearest = float(u[np.argmin(np.abs(u - v))])
                disc[nm] = (len(u), nearest)
    for nm, v in zip(xnames, r["x"]):
        tail = ""
        if nm in disc:
            k, near = disc[nm]
            tail = (f"   ← 离散（{k} 个取值），最近合法值 {near:.4g}"
                    if abs(near - v) > 1e-9 else f"   ← 离散（{k} 个取值）")
        print(f"    {nm:<26}{v:.6f}{tail}")
    print()
    print(f"  预测 {obj} = {r['pred']:.6f}")
    if r["constraints"]:
        tol = r.get("tol", 0.0)
        if r["feasible"]:
            note = (f"越界 {r['max_violation']:.2e} ≤ 模型容差 {tol:.2e}"
                    if r["max_violation"] > 1e-9 else "严格满足")
            print(f"  约束：在模型容差内满足（{note}）")
        else:
            print(f"  约束：**违反**（越界 {r['max_violation']:.2e} "
                  f"> 容差 {tol:.2e}）")
        for c in r["constraints"]:
            print(f"    {c['col']} {c['op']} {c['val']}"
                  f"（该列模型 CV RMSE {c['rmse']:.5f}）")
    if r["bad"]:
        print(f"  解析不了的约束：{r['bad']}")
    print()
    print(f"  最近观测点：第 {r['nearest_row']} 行"
          f"（归一化距离 {r['nearest_dist']:.3f}）")
    print(f"  在观测域内：{'是' if r['inside_domain'] else '否 —— 这是外推'}")
    if r["obs_best"]:
        ob = r["obs_best"]
        print(f"  对照「观测里最好的一行」：第 {ob['row']} 行 "
              f"{obj}={ob['obj']:.6f}")
        delta = r["pred"] - ob["obj"]
        better = (delta < 0) if r["pred"] < ob["obj"] else (delta > 0)
        print(f"  连续优化比它{'低' if delta < 0 else '高'} {abs(delta):.6f}")
    print()
    if r.get("trustworthy"):
        print("  ✓ 这个解通过三条硬检验：约束满足、优于观测最优、未外推。")
    else:
        print("  ✗ 这个解**不能用**，原因：")
        for fl in r.get("flags", []):
            print(f"      · {fl}")
        print("    处理：要么加约束、要么换结构、要么直接采用观测里最好的那一行。")



BAR = "=" * 84
THIN = "-" * 84


def sec(title: str) -> None:
    print()
    print(BAR)
    print(title)
    print(BAR)


def verify_one(c: lanes.Claim) -> tuple[list, dict, dict]:
    votes = lanes.run_lanes(c)
    agg = lanes.aggregate(votes)
    v = lanes.to_verdict(c, agg)
    return votes, agg, v


def show_votes(votes: list) -> None:
    for v in votes:
        mark = {"support": "✓", "oppose": "✗", "unknown": "?"}[v.verdict]
        veto = "!" if getattr(v, "veto", False) else " "
        print(f"    {mark}{veto}{v.lane:<10}{v.verdict:<9}"
              f"{v.strength:.2f}  {v.why[:58]}")


def race_seeds(ds, yname: str, xnames: list[str], seeds=(0, 1, 2)) -> dict:
    """多种子算法竞速 + 残差诊断（从 craft.py 迁过来的两项独有检查）。

    为什么必须换种子：
        只跑一个种子，会把「折划分的运气」当成「算法更好」。
        APMCM 真题上实测过 —— 种子 0 选线性，种子 1/2 选二次，
        说明二次和线性在那份数据上根本分不出高下。
        论文里写「本文采用二次模型，因为拟合更好」就是踩了这个坑。

    为什么必须看残差：
        CV 只告诉你「预测误差多大」，不告诉你「误差有没有结构」。
        残差还能被预测值解释 → 模型没把规律抽干净。
    """
    X, y = ds.cols(xnames), ds.col(yname)
    cands = [("线性", "linear", 0.0), ("二次", "quad", 0.0),
             ("岭回归(λ=1)", "quad", 1.0), ("岭回归(λ=10)", "quad", 10.0)]
    table = []
    for label, kind, ridge in cands:
        per = []
        for s in seeds:
            e = mm.kfold(X, y, kind, seed=s, ridge=ridge)
            per.append(None if e is None else float(e.mean()))
        table.append(dict(label=label, kind=kind, ridge=ridge, per_seed=per,
                          mean=(None if any(v is None for v in per)
                                else float(np.mean(per)))))

    # 每个种子下最优是谁
    winners = []
    for si in range(len(seeds)):
        cols = [(t["label"], t["per_seed"][si]) for t in table
                if t["per_seed"][si] is not None]
        if cols:
            cols.sort(key=lambda t: t[1])
            winners.append(cols[0][0])
        else:
            winners.append(None)
    stable = len(set(winners)) == 1

    ok = [t for t in table if t["mean"] is not None]
    ok.sort(key=lambda t: t["mean"])
    best = ok[0] if ok else None
    gap = None
    if len(ok) >= 2:
        gap = (ok[1]["mean"] - ok[0]["mean"]) / ok[1]["mean"]

    # 残差诊断（用最优结构拟合）
    resid = None
    if best:
        A = mm.design(X, best["kind"])
        AtA = A.T @ A
        if best["ridge"] > 0:
            AtA = AtA + best["ridge"] * np.eye(AtA.shape[0])
        try:
            coef = np.linalg.solve(AtA, A.T @ y)
        except np.linalg.LinAlgError:
            coef = np.linalg.lstsq(A, y, rcond=None)[0]
        pred = A @ coef
        r = y - pred
        n = len(r)
        AA = np.hstack([np.ones((n, 1)), pred.reshape(-1, 1)])
        c1 = np.linalg.lstsq(AA, r, rcond=None)[0]
        rp = AA @ c1
        ss_res = float(np.sum((r - rp) ** 2))
        ss_tot = float(np.sum((r - r.mean()) ** 2))
        r2_struct = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        e2 = r ** 2
        c2 = np.linalg.lstsq(AA, e2, rcond=None)[0]
        p2 = AA @ c2
        ss2 = float(np.sum((e2 - p2) ** 2))
        st2 = float(np.sum((e2 - e2.mean()) ** 2))
        bp = n * (1 - ss2 / st2) if st2 > 0 else 0.0
        resid = dict(r2_structure=r2_struct, bp=bp, n=n,
                     homoscedastic=(bp <= 7.81),
                     no_structure=(r2_struct <= 0.1),
                     rmse=float(np.sqrt(np.mean(r ** 2))))

    return dict(table=table, seeds=list(seeds), winners=winners,
                stable=stable, best=best, gap=gap, resid=resid,
                n=len(y), p=X.shape[1])


def print_race(r: dict, yname: str) -> None:
    print()
    print(BAR)
    print(f"多种子竞速 + 残差诊断 · 目标 {yname}")
    print(BAR)
    print(f"  {'候选':<16}" + "".join(f"{'种子' + str(s):>12}"
                                     for s in r["seeds"]) + f"{'均值':>12}")
    for t in r["table"]:
        cells = "".join(
            f"{'不适用':>12}" if v is None else f"{v:>12.5f}"
            for v in t["per_seed"])
        mean = "—" if t["mean"] is None else f"{t['mean']:.5f}"
        print(f"  {t['label']:<16}{cells}{mean:>12}")
    print()
    print(f"  每个种子下选出的最优：{r['winners']}")
    if r["stable"]:
        print(f"  ✓ 换种子结论不变 —— 「{r['winners'][0]}」站得住")
    else:
        print("  ✗ 换种子结论就变 —— 说明这几个候选的差距在噪声内。")
        print("    论文里不许写「A 优于 B」，只能写「A/B 在本数据上不可区分」。")
    if r["gap"] is not None:
        print(f"  最优领先次优 {r['gap']:+.1%}"
              + ("（< 5%，噪声量级）" if abs(r["gap"]) < 0.05 else ""))
    res = r.get("resid")
    if res:
        print()
        print(f"  残差诊断（用「{r['best']['label']}」，RMSE={res['rmse']:.5f}）：")
        print(f"    残差还能被预测值解释 {res['r2_structure']:.3f}"
              + ("  ✓ 无残余结构" if res["no_structure"]
                 else "  ✗ 有残余结构，模型没抽干净"))
        print(f"    异方差 BP = {res['bp']:.2f}（自由度 {r['p']}，"
              f"0.05 临界 7.81）"
              + ("  ✓ 同方差" if res["homoscedastic"]
                 else "  ✗ 异方差，要换稳健标准误或对 y 取对数"))



# ══════════════════════════════════════════════════════════════════════
#  机理：安全表达式求值（ODE 用）
# ══════════════════════════════════════════════════════════════════════
ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "exp": math.exp, "log": math.log, "sqrt": math.sqrt,
    "abs": abs, "min": min, "max": max, "pow": pow,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "atan": math.atan, "asin": math.asin, "acos": math.acos,
}
ALLOWED_NAMES = {"pi": math.pi, "e": math.e, "t": 0.0}


def safe_expr(src: str):
    """把字符串编译成函数 f(t, y) → float。

    为什么不直接 eval：`--rhs` 是用户输入，eval 等于把 shell 递给输入。
    这里走 AST 白名单：只放行算术、比较、条件表达式和白名单函数名，
    Name 只认 t / y / pi / e。多一个节点类型都不放。
    这是"少幻觉"的另一面 —— 工具不该成为执行任意代码的通道。
    """
    import ast as _ast
    src = (src or "").strip()
    if not src:
        raise ValueError("表达式为空")
    tree = _ast.parse(src, mode="eval")

    ok_nodes = (_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant,
                _ast.Name, _ast.Load, _ast.Call, _ast.Add, _ast.Sub,
                _ast.Mult, _ast.Div, _ast.Pow, _ast.Mod, _ast.USub,
                _ast.UAdd, _ast.Compare, _ast.IfExp, _ast.Lt, _ast.Gt,
                _ast.LtE, _ast.GtE, _ast.Eq, _ast.NotEq, _ast.And, _ast.Or,
                _ast.BoolOp, _ast.Tuple)
    for node in _ast.walk(tree):
        if not isinstance(node, ok_nodes):
            raise ValueError(f"表达式里不允许 {type(node).__name__}")

    # 第 77 轮修的坑：`sin(t)` 的 AST 是 Call(Name('sin'), ...)，
    # 如果把 Call 的 func 当成"变量名"去查，sin 会被判未知名字。
    # 先把所有作为函数名的 Name 记下来，变量名检查要跳过它们。
    func_names = {id(n.func) for n in _ast.walk(tree)
                  if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}

    for node in _ast.walk(tree):
        if isinstance(node, _ast.Name) and id(node) not in func_names:
            if node.id not in ("t", "y") and node.id not in ALLOWED_NAMES:
                raise ValueError(f"未知名字 {node.id!r}（只认 t / y / pi / e）")
        if isinstance(node, _ast.Call):
            if not isinstance(node.func, _ast.Name):
                raise ValueError("只允许直接调用白名单函数")
            if node.func.id not in ALLOWED_FUNCS:
                raise ValueError(f"不允许调用 {node.func.id!r}"
                                 f"（可用：{sorted(ALLOWED_FUNCS)}）")
    code = compile(tree, "<rhs>", "eval")

    def rhs(t: float, y):
        env = dict(ALLOWED_NAMES)
        env["t"] = t
        env["y"] = y[0] if hasattr(y, "__len__") else y
        env.update(ALLOWED_FUNCS)
        return float(eval(code, {"__builtins__": {}}, env))       # noqa: S307
    return rhs


def ode_solve(rhs_src: str, y0: list[float], t0: float, t1: float,
              method: str = "rk45") -> dict:
    """解一阶 ODE 系统。rhs 只支持标量（单变量）—— 多元请直接用 engine。"""
    import engine as eng
    rhs = safe_expr(rhs_src)
    if method == "rk4":
        ts, ys = eng.rk4(rhs, [y0[0]], t0, t1, n=4000)
        stats = dict(steps=len(ts), rejected=0)
    else:
        ts, ys, stats = eng.rk45(rhs, [y0[0]], t0, t1)
    return dict(rhs=rhs_src, y0=y0, t0=t0, t1=t1, method=method,
                ts=ts, ys=ys[:, 0], stats=stats,
                y_end=float(ys[-1, 0]),
                y_min=float(ys[:, 0].min()), y_max=float(ys[:, 0].max()))


def print_ode(r: dict) -> None:
    print()
    print(BAR)
    print(f"ODE 求解 · y' = {r['rhs']}")
    print(BAR)
    print(f"  方法 {r['method']}   y(0)={r['y0'][0]:g}   t∈[{r['t0']:g}, {r['t1']:g}]")
    print(f"  步数 {r['stats']['steps']}（拒收 {r['stats']['rejected']} 次）")
    print(f"  y(末) = {r['y_end']:.6f}")
    print(f"  区间  [{r['y_min']:.6f}, {r['y_max']:.6f}]")
    print()
    n = len(r["ts"])
    idx = [0, n // 4, n // 2, 3 * n // 4, n - 1]
    print(f"  {'t':>10}{'y':>14}")
    for i in idx:
        print(f"  {r['ts'][i]:>10.4f}{r['ys'][i]:>14.6f}")
    print()
    print("  外推边界：ODE 只在给定区间内有效，区间外的预测没有依据。")


# ══════════════════════════════════════════════════════════════════════
#  机理：量纲分析
# ══════════════════════════════════════════════════════════════════════
def parse_dims(spec: str) -> tuple[float, dict[str, float]]:
    """把 "L*T^-2" 解析成 {L:1, T:-2}。

    也接受 "L*T^-2*M^0" 这种显式零次项（会被丢掉）。
    """
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("量纲为空")
    out: dict[str, float] = {}
    for part in spec.split("*"):
        part = part.strip()
        if not part:
            continue
        if "^" in part:
            base, exp = part.split("^", 1)
            e = float(exp)
        else:
            base, e = part, 1.0
        base = base.strip()
        if not base:
            raise ValueError(f"量纲项 {part!r} 空")
        out[base] = out.get(base, 0.0) + e
    return 1.0, {k: v for k, v in out.items() if abs(v) > 1e-12}


def dimension_analysis(vars_: list[tuple[str, str]]) -> dict:
    import engine as eng
    parsed = []
    for name, spec in vars_:
        _, dims = parse_dims(spec)
        parsed.append((name, dims))
    r = eng.buckingham(parsed)
    return dict(**r, input=parsed)


def print_dim(r: dict) -> None:
    print()
    print(BAR)
    print("量纲分析（Pi 定理）")
    print(BAR)
    print(f"  基本量纲 {r['dims']}")
    print(f"  变量 {r['n']} 个，矩阵秩 {r['rank']}，"
          f"独立无量纲组合 {r['n_pi']} 个")
    print()
    for nm, d in r["input"]:
        s = "·".join(f"{k}^{v:g}" for k, v in d.items()) or "无量纲"
        print(f"    {nm:<20}{s}")
    print()
    if r["n_pi"] == 0:
        print("  这组变量已经全是独立量纲，没有可构造的无量纲数。")
        print("  含义：每个变量都能单独定标，无法减少参数个数。")
    else:
        print(f"  可构造 {r['n_pi']} 个无量纲组合（指数向量，对应上面变量顺序）：")
        for i, p in enumerate(r["pis"], 1):
            terms = []
            for nm, e in zip(r["names"], p):
                if abs(e) > 1e-9:
                    terms.append(f"{nm}^{e:+.3g}")
            print(f"    Π{i} = " + " · ".join(terms))
        print()
        print("  用法：把实验数据按 Π 组合后，变量个数从 "
              f"{r['n']} 降到 {r['n_pi']}。")



# ══════════════════════════════════════════════════════════════════════
#  预测（第 78 轮补：数模四大题型里缺的那一块）
# ══════════════════════════════════════════════════════════════════════
def _lin_trend_fit(t: np.ndarray, y: np.ndarray):
    A = np.column_stack([np.ones_like(t), t])
    coef = np.linalg.lstsq(A, y, rcond=None)[0]
    return lambda tt: coef[0] + coef[1] * np.asarray(tt, float)


def _exp_smooth_fit(y: np.ndarray, alpha: float):
    """简单指数平滑。返回预测函数（水平值保持不变）。"""
    lvl = float(y[0])
    for v in y[1:]:
        lvl = alpha * float(v) + (1 - alpha) * lvl
    resid = y - lvl                       # 近似残差
    return (lambda tt: np.full(np.asarray(tt, float).shape, lvl)), lvl, resid


def _ma_fit(y: np.ndarray, k: int):
    k = max(1, min(k, len(y) - 1))
    lvl = float(np.mean(y[-k:]))
    resid = y[k:] - np.array([np.mean(y[i:i + k]) for i in range(len(y) - k)])
    return (lambda tt: np.full(np.asarray(tt, float).shape, lvl)), lvl, resid


def forecast(ds, yname: str, horizon: int = 5, tname: str | None = None) -> dict:
    """时间序列预测：三种方法竞速 + 留出验证 + 预测区间。

    为什么必须留出验证：
        趋势外推永远能画出一条"看起来对"的线。不留最后几期做检验，
        就无法回答「这个方法在这份数据上到底准不准」。

    为什么给区间不给点：
        点预测是幻觉的源头。残差有分布，预测就该有区间。
    """
    y = ds.col(yname)
    n = len(y)
    if n < 8:
        return dict(ok=False, why=f"只有 {n} 个点，太少，做不了留出验证")
    # 用行序当时间轴是个强假设，必须自己说出来。
    # APMCM 那份数据 84 行是实验参数组合，行序只是编号 ——
    # 对它做「预测未来 6 期」在物理上没有意义，工具不能装作没看见。
    warn = []
    if tname:
        t = ds.col(tname)
    else:
        t = np.arange(n, dtype=float)
        warn.append("没给 --t，用的是行序当时间轴")
        for nm in ds.num_names:
            c = ds.col(nm)
            if len(c) == n and np.allclose(np.sort(c), np.arange(1, n + 1)):
                warn.append(
                    f"列「{nm}」取值正好是 1..{n} —— 这说明行序是**编号**，"
                    f"不是时间。对它做趋势外推没有物理含义")
                break

    hold = max(2, min(horizon, n // 4))
    tr_t, tr_y = t[:-hold], y[:-hold]
    te_t, te_y = t[-hold:], y[-hold:]

    cands = []
    # 1) 线性趋势
    f_lin = _lin_trend_fit(tr_t, tr_y)
    pred_te = f_lin(te_t)
    rmse_lin = float(np.sqrt(np.mean((pred_te - te_y) ** 2)))
    resid_lin = tr_y - f_lin(tr_t)
    cands.append(dict(name="线性趋势", fn=f_lin, rmse=rmse_lin,
                      resid=resid_lin, params="y = a + b·t"))
    # 2) 指数平滑（挑 alpha）
    best_es = None
    for alpha in (0.1, 0.2, 0.3, 0.5, 0.7):
        fn, lvl, resid = _exp_smooth_fit(tr_y, alpha)
        pred = fn(te_t)
        rm = float(np.sqrt(np.mean((pred - te_y) ** 2)))
        if best_es is None or rm < best_es["rmse"]:
            best_es = dict(name=f"指数平滑(α={alpha})", fn=fn, rmse=rm,
                           resid=resid, params=f"水平 {lvl:.6g}")
    cands.append(best_es)
    # 3) 移动平均
    best_ma = None
    for k in (2, 3, 5):
        if k >= len(tr_y):
            continue
        fn, lvl, resid = _ma_fit(tr_y, k)
        pred = fn(te_t)
        rm = float(np.sqrt(np.mean((pred - te_y) ** 2)))
        if best_ma is None or rm < best_ma["rmse"]:
            best_ma = dict(name=f"移动平均(k={k})", fn=fn, rmse=rm,
                           resid=resid, params=f"水平 {lvl:.6g}")
    if best_ma:
        cands.append(best_ma)

    # 4) 朴素法：直接拿最后一个值
    naive_rmse = float(np.sqrt(np.mean((tr_y[-1] - te_y) ** 2)))
    cands.append(dict(name="朴素（取末期值）",
                      fn=lambda tt: np.full(np.asarray(tt, float).shape,
                                            float(tr_y[-1])),
                      rmse=naive_rmse, resid=tr_y - tr_y[-1],
                      params=f"末期值 {tr_y[-1]:.6g}"))

    ok = [c for c in cands if c["rmse"] is not None]
    ok.sort(key=lambda c: c["rmse"])
    best = ok[0]

    # 用全量数据重拟合最好的那个方法
    if best["name"] == "线性趋势":
        f_final = _lin_trend_fit(t, y)
        resid_final = y - f_final(t)
    elif best["name"].startswith("指数平滑"):
        alpha = float(best["name"].split("α=")[1].rstrip(")"))
        f_final, _lvl, resid_final = _exp_smooth_fit(y, alpha)
    elif best["name"].startswith("移动平均"):
        k = int(best["name"].split("k=")[1].rstrip(")"))
        f_final, _lvl, resid_final = _ma_fit(y, k)
    else:
        f_final = lambda tt: np.full(np.asarray(tt, float).shape, float(y[-1]))
        resid_final = y - y[-1]

    step = float(np.median(np.diff(t))) if n > 1 else 1.0
    fut_t = t[-1] + step * np.arange(1, horizon + 1)
    fut_y = np.asarray(f_final(fut_t), float)
    sd = float(np.std(resid_final, ddof=1)) if len(resid_final) > 1 else 0.0
    # 预测区间随步长变宽（这是时间序列的基本事实，不能给常数区间）
    widen = np.sqrt(1 + np.arange(1, horizon + 1) / max(1, n))
    lo = fut_y - 1.96 * sd * widen
    hi = fut_y + 1.96 * sd * widen

    # 「赢过朴素法」必须按数字比，不能只看名字。
    # 第一版写成 best["name"] != "朴素（取末期值）"，于是在真实数据上
    # 出现过「0.000000 → 0.000000 也算赢」的荒唐结论。
    naive_beaten = best["rmse"] < naive_rmse - 1e-12
    # 留出期全同值 → 任何方法都能得 RMSE=0，这个检验没有区分力
    hold_flat = float(np.std(te_y)) < 1e-12
    if hold_flat:
        warn.append(
            f"留出期 {len(te_y)} 个点的值完全相同"
            f"（都是 {float(te_y[0]):.6g}）—— 任何方法在这里都能得"
            f" RMSE=0，这个检验**没有区分力**")
    # 有警告时，这个预测的可信度整体打折 —— 结论强度要跟着降
    questionable = bool([w for w in warn if "编号" in w or "没有物理含义" in w])
    return dict(ok=True, y=yname, n=n, horizon=horizon, hold=hold,
                warn=warn, questionable=questionable,
                cands=[{k: v for k, v in c.items()
                        if k not in ("fn", "resid")} for c in cands],
                best=best["name"], best_rmse=best["rmse"],
                naive_rmse=naive_rmse, naive_beaten=naive_beaten,
                fut_t=fut_t.tolist(), fut_y=fut_y.tolist(),
                lo=lo.tolist(), hi=hi.tolist(), sd=sd, step=step,
                te_y=te_y.tolist(),
                best_te=np.asarray(best["fn"](te_t), float).tolist())


def print_forecast(r: dict) -> None:
    print()
    print(BAR)
    print(f"预测 · 目标 {r['y']}（{r['n']} 个点，留出最后 {r['hold']} 期做检验）")
    print(BAR)
    print(f"  {'方法':<22}{'留出 RMSE':>14}")
    for c in r["cands"]:
        mark = "  ← 选中" if c["name"] == r["best"] else ""
        print(f"  {c['name']:<22}{c['rmse']:>14.6f}{mark}")
    print()
    if r.get("warn"):
        print("  ⚠ 前提警告：")
        for w in r["warn"]:
            print(f"      · {w}")
        print()
    if r.get("questionable"):
        print("  ✗ **这份预测不能用**。上面的 RMSE 只在「行序就是时间」的假设下成立，")
        print("    而数据自己否认了这个假设。要么给 --t 指定真正的时间列，")
        print("    要么承认这是横截面数据、不做趋势外推。")
        print()
    if not r["naive_beaten"]:
        print("  ✗ 所有方法都没赢过「朴素法」—— 这份数据没有可提取的趋势。")
        print("    论文里不许写「预测未来 N 期」，只能写「历史均值/末期水平」。")
    else:
        print(f"  ✓ 「{r['best']}」赢过朴素法"
              f"（{r['naive_rmse']:.6f} → {r['best_rmse']:.6f}）")
    print()
    print(f"  {'步':>4}{'预测':>14}{'95% 下界':>14}{'95% 上界':>14}")
    for i, (tt, yy, l, h) in enumerate(zip(r["fut_t"], r["fut_y"],
                                           r["lo"], r["hi"]), 1):
        print(f"  {i:>4}{yy:>14.6f}{l:>14.6f}{h:>14.6f}")
    print()
    print(f"  残差标准差 {r['sd']:.6f}；区间随步长变宽"
          f"（√(1+k/n)，这是时间序列的基本约束）")
    print("  边界：只在历史区间的延续方向上有效。超出量级太多就是编。")



# ══════════════════════════════════════════════════════════════════════
#  聚类（第 79 轮补：C 题数据挖掘类的常用手段）
# ══════════════════════════════════════════════════════════════════════
def _kmeans(X: np.ndarray, k: int, seed: int = 0, iters: int = 300):
    """K-means++ 初始化 + Lloyd 迭代。"""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    k = max(1, min(k, n))
    centers = [X[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min(np.stack([((X - c) ** 2).sum(1) for c in centers]), axis=0)
        tot = float(d2.sum())
        probs = d2 / tot if tot > 0 else np.full(n, 1.0 / n)
        centers.append(X[rng.choice(n, p=probs)])
    C = np.array(centers, float)
    lab = np.zeros(n, dtype=int)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        new_lab = d.argmin(1)
        newC = np.array([
            X[new_lab == j].mean(0) if (new_lab == j).any() else C[j]
            for j in range(k)])
        if np.array_equal(new_lab, lab) and np.allclose(newC, C):
            lab = new_lab
            C = newC
            break
        lab, C = new_lab, newC
    inertia = float(((X - C[lab]) ** 2).sum())
    return lab, C, inertia


def _silhouette(X: np.ndarray, lab: np.ndarray) -> float:
    """轮廓系数。手写，n 大时可以抽样。"""
    n = X.shape[0]
    ks = np.unique(lab)
    if len(ks) < 2:
        return 0.0
    if n > 600:                       # O(n²) 的内存兜底
        idx = np.random.default_rng(0).choice(n, 600, replace=False)
        Xs, labs = X[idx], lab[idx]
    else:
        Xs, labs = X, lab
    D = np.sqrt(((Xs[:, None, :] - Xs[None, :, :]) ** 2).sum(2))
    out = []
    for i in range(len(Xs)):
        same = labs == labs[i]
        same[i] = False
        if same.sum() == 0:
            out.append(0.0)
            continue
        a = float(D[i, same].mean())
        bs = [float(D[i, labs == j].mean()) for j in ks if j != labs[i]]
        b = min(bs) if bs else 0.0
        out.append((b - a) / max(a, b) if max(a, b) > 1e-12 else 0.0)
    return float(np.mean(out))


def _null_silhouette(X: np.ndarray, k: int, seed: int = 0,
                     reps: int = 3) -> float:
    """零模型对照：同均值/协方差的高斯数据，同样的 k，能拿到多高轮廓系数。

    为什么必须有这一步：
        单个高斯团被 K-means 切成 2 份，轮廓系数能到 0.35。
        0.35 > 0.25 的门槛，于是「一个团」会被误判成「两簇」。
        轮廓系数衡量的不是"有没有簇"，是"当前划分好不好看" ——
        **任何数据都能被切出好看的划分。**

    零模型给的是「无结构数据在同一个 k 上的轮廓水平」。
    真实轮廓必须明显高出这个基线，才算真有结构。
    """
    rng = np.random.default_rng(seed)
    n, p = X.shape
    mu = X.mean(0)
    C = np.atleast_2d(np.cov(X.T)) if p > 1 else np.atleast_2d(
        np.array([[float(X[:, 0].var(ddof=1) or 1.0)]]))
    if p > 1 and C.shape != (p, p):
        C = np.eye(p)
    out = []
    for _ in range(reps):
        try:
            Xn = rng.multivariate_normal(mu, C, n)
        except (ValueError, np.linalg.LinAlgError):
            return 0.0
        lab, _, _ = _kmeans(Xn, k, seed=seed)
        out.append(_silhouette(Xn, lab))
    return float(np.mean(out)) if out else 0.0


def cluster(ds, xnames: list[str], k: int | None = None,
            kmax: int = 8) -> dict:
    """K-means 聚类 + 选 k + 轮廓系数。

    三件必须做的事，缺一件这个聚类就不可信：
      1. 标准化 —— 三个指标量级差 100 倍时，不标准化等于只看量级大的那个
      2. 选 k 有依据 —— 不能拍一个 3 就交差
      3. 给分离度 —— 轮廓系数低于 0.25 说明「分出来的组是硬分的」
    """
    X = ds.cols(xnames)
    n, p = X.shape
    if n < 2 * p:
        return dict(ok=False, why=f"{n} 行撑不起 {p} 个特征的聚类")

    mu, sd = X.mean(0), X.std(0, ddof=1)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd

    ks = [k] if k else list(range(2, min(kmax, n // 5) + 1))
    trials = []
    for kk in ks:
        lab, C, inertia = _kmeans(Z, kk)
        sil = _silhouette(Z, lab)
        sizes = [int((lab == j).sum()) for j in range(len(C))]
        trials.append(dict(k=kk, inertia=inertia, silhouette=sil,
                           sizes=sizes, lab=lab, centers=C))
    # 过滤掉「有空簇」的退化解 —— 注意不是过滤「各簇等大」。
    # 第一版写成 len(set(sizes)) > 1，把 [90, 90, 90] 这种**完美的均匀聚类**
    # 当退化解扔了，于是三簇数据被判成 k=4。均匀不是退化，空簇才是。
    ok = [t for t in trials if min(t["sizes"]) > 0 and len(t["sizes"]) == t["k"]]
    ok = ok or trials
    # 简约优先：轮廓系数最优值和它的差距在 0.03 以内时，选**最小的 k**。
    # 原因：把一个簇劈成两半，轮廓系数几乎总是略升 —— 那是切得更细，
    # 不是找到了更多结构。实测三簇数据 k=3 得 0.66、k=4 得 0.668，
    # 单看最大值会选 k=4，但 k=4 是把其中一簇劈开了。
    best_sil = max(t["silhouette"] for t in ok)
    near = [t for t in ok if t["silhouette"] >= best_sil - 0.03]
    pick = min(near, key=lambda t: t["k"])

    lab = pick["lab"]
    sizes = pick["sizes"]
    # 中心换回原量纲 —— 论文里写"第 1 类中心是热阻 0.73"才有意义
    centers_orig = []
    for j in range(pick["k"]):
        m = lab == j
        centers_orig.append([float(X[m, i].mean()) if m.any() else float("nan")
                             for i in range(p)])

    warn = []
    if pick["silhouette"] < 0.25:
        warn.append(f"轮廓系数 {pick['silhouette']:.3f} < 0.25 —— "
                    f"这几个组是硬分的，数据本身可能没有清晰的簇结构")
    if min(sizes) < max(2, int(0.05 * n)):
        warn.append(f"最小簇只有 {min(sizes)} 行（< 5%），可能是离群点被单列成一组")
    if k is None and len(trials) > 1:
        gap = sorted((t["silhouette"] for t in trials), reverse=True)
        if len(gap) > 1 and gap[0] - gap[1] < 0.03:
            warn.append(f"最优 k 与次优只差 {gap[0] - gap[1]:.3f}，"
                        f"k 的选择不稳固")
        # 轮廓系数在搜索上界仍单调上升 = 数据没有"自然的分组数"
        # 这是最容易被忽略的一种情况：k 越大轮廓越好看，但那不是结构，
        # 是"每个点自成一簇"的退化趋势。
        if pick["k"] >= max(t["k"] for t in trials):
            warn.append(
                f"轮廓系数到搜索上界 k={pick['k']} 仍在上升 —— "
                f"说明数据没有自然的簇数，继续加 k 只会让轮廓更好看")

    # 零模型对照：真实轮廓要明显高过高斯零模型才算有结构
    null_sil = _null_silhouette(Z, pick["k"])
    margin = pick["silhouette"] - null_sil
    if margin < 0.10:
        warn.append(
            f"轮廓系数 {pick['silhouette']:.3f} 只比同协方差高斯零模型"
            f"（{null_sil:.3f}）高 {margin:+.3f} —— "
            f"这个「结构」在无结构数据上也能拿到")

    no_structure = (pick["silhouette"] < 0.25) or (margin < 0.10) or (
        k is None and pick["k"] >= max(t["k"] for t in trials))

    return dict(ok=True, x=xnames, n=n, p=p, k=pick["k"],
                k_chosen="auto" if k is None else "manual",
                silhouette=pick["silhouette"], null_silhouette=null_sil,
                margin=margin, inertia=pick["inertia"],
                sizes=sizes, centers_orig=centers_orig,
                trials=[dict(k=t["k"], inertia=t["inertia"],
                             silhouette=t["silhouette"], sizes=t["sizes"])
                        for t in trials],
                labels=lab.tolist(), warn=warn, no_structure=no_structure,
                separability=("强" if pick["silhouette"] >= 0.5 else
                              "中" if pick["silhouette"] >= 0.25 else "弱"))


def print_cluster(r: dict) -> None:
    print()
    print(BAR)
    print(f"聚类 · {len(r['x'])} 个特征 × {r['n']} 行（已标准化）")
    print(BAR)
    print(f"  特征：{r['x']}")
    print()
    print(f"  {'k':>4}{'簇内平方和':>14}{'轮廓系数':>12}   各簇大小")
    for t in r["trials"]:
        mark = "  ← 选中" if t["k"] == r["k"] else ""
        print(f"  {t['k']:>4}{t['inertia']:>14.3f}{t['silhouette']:>12.4f}   "
              f"{t['sizes']}{mark}")
    print()
    print(f"  选 k={r['k']}（{r['k_chosen']}），"
          f"轮廓系数 {r['silhouette']:.4f}，分离度 **{r['separability']}**")
    if r.get("null_silhouette") is not None:
        print(f"  零模型基线 {r['null_silhouette']:.4f}"
              f"（同协方差高斯数据能拿到的水平），"
              f"实际高出 {r['margin']:+.4f}")
    print()
    print("  各簇中心（原量纲）：")
    head = "  " + "簇".ljust(5) + "".join(f"{nm[:10]:>12}" for nm in r["x"]) \
        + f"{'行数':>8}"
    print(head)
    for j, c in enumerate(r["centers_orig"]):
        print(f"  {j + 1:<5}" + "".join(f"{v:>12.5f}" for v in c)
              + f"{r['sizes'][j]:>8}")
    print()
    if r["warn"]:
        print("  ⚠ 警告：")
        for w in r["warn"]:
            print(f"      · {w}")
        print()
    if r.get("no_structure"):
        print("  ✗ **不建议把它写成「数据分为 k 类」**。")
        print("    轮廓系数低或在 k 上界仍上升，意味着没有自然的分组数，")
        print("    你能写的最多是「按 K-means 划分为 k 组，用于分箱/降维」。")
    elif r["warn"]:
        print("  这些警告不是「优化一下就好」，是**结论强度**的问题：")
        print("  轮廓系数低的时候，论文里只能写「按 K-means 划分出 k 组」，")
        print("  不能写「数据自然分为 k 类」—— 后者是数据的性质，前者是你的选择。")
    else:
        print("  ✓ 簇结构清晰，可以写「数据呈现出 k 组可区分的模式」。")
    print()
    print("  边界：K-means 假设簇是凸的、大小相近。细长/环形/密度差异大的簇，")
    print("        它会把它们切开。看到「轮廓系数低但图上有结构」时，换 DBSCAN。")


# ══════════════════════════════════════════════════════════════════════
#  绘图（第 79 轮补：环境没有 matplotlib，用 PIL 画）
# ══════════════════════════════════════════════════════════════════════
_FONT_CACHE: dict = {}
# 出图超采样：逻辑尺寸不变，实际像素在这个倍数上放大。
# 论文插图要能放大看，1 倍的 900x600 在 A4 上已经发糊。
PLOT_SCALE = 2
PALETTE = [(31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40),
           (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
           (188, 189, 34), (23, 190, 207)]


def _font(size: int = 16):
    # 字号跟着超采样一起放大，否则字会相对变小
    size = max(1, int(round(size * PLOT_SCALE)))
    """找一个能显示中文的字体。找不到就退回 PIL 默认（中文会变方框）。"""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    from PIL import ImageFont
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\simsun.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _FONT_CACHE[size] = f
                return f
            except OSError:
                continue
    f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


class _Plot:
    """极简坐标系。数据坐标 ↔ 像素坐标的换算全在这里。"""

    def __init__(self, w=900, h=600, title="", xlabel="", ylabel="",
                 pad=(96, 78, 62, 96)):
        from PIL import Image, ImageDraw
        # 超采样：论文插图要能放大看。逻辑尺寸不变，实际像素 xPLOT_SCALE
        self.W, self.H = w * PLOT_SCALE, h * PLOT_SCALE
        _pad = tuple(int(v * PLOT_SCALE) for v in pad)
        self.img = Image.new("RGB", (self.W, self.H), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img)
        self.left, self.top, self.right, self.bottom = _pad
        # 最终防线：任何含 CJK 的文字都不许进图。
        # 之前反复出现"改了 title 漏了 xlabel"，靠人盯不住，交给这里。
        self.title = _en_text(title)
        self.xlabel = _en_text(xlabel)
        self.ylabel = _en_text(ylabel)
        self.xlim = (0.0, 1.0)
        self.ylim = (0.0, 1.0)

    # 数据 → 像素
    def px(self, x):
        x0, x1 = self.xlim
        a, b = self.left, self.W - self.right
        return a + (b - a) * ((x - x0) / (x1 - x0) if x1 != x0 else 0.5)

    def py(self, y):
        y0, y1 = self.ylim
        a, b = self.H - self.bottom, self.top
        return a + (b - a) * ((y - y0) / (y1 - y0) if y1 != y0 else 0.5)

    def set_range(self, xs, ys, margin=0.06):
        def rng(v):
            lo, hi = float(np.min(v)), float(np.max(v))
            if hi == lo:
                return lo - 1, hi + 1
            m = (hi - lo) * margin
            return lo - m, hi + m
        self.xlim, self.ylim = rng(xs), rng(ys)

    def vtext(self, s, x, y, size=15, fill=(30, 30, 30)):
        """竖排文字（旋转 90°）。

        为什么需要：PIL 的 draw.text 不会旋转。直接横着画长标签，
        左边界会把「无量纲压降」裁成「纲压降」—— 这不是排版问题，
        是标签意思变了。
        """
        from PIL import Image, ImageDraw
        f = _font(size)
        bbox = self.d.textbbox((0, 0), s, font=f)
        w = max(1, int(bbox[2] - bbox[0]) + 8)
        h = max(1, int(bbox[3] - bbox[1]) + 8)
        tmp = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        ImageDraw.Draw(tmp).text((4 * PLOT_SCALE, 4 * PLOT_SCALE), s,
                                 font=f, fill=fill)
        tmp = tmp.rotate(90, expand=True)
        self.img.paste(tmp, (int(x - tmp.width / 2),
                             int(y - tmp.height / 2)), tmp)

    def axes(self, xticks=6, yticks=6, xlabels=True):
        """xlabels=False 时不画 x 刻度文字 —— 柱状图要自己写类目名，
        否则默认的 0/1/2/3 会和类目名叠在一起。
        """
        f = _font(13)
        d, L, R = self.d, self.left, self.W - self.right
        T, B = self.top, self.H - self.bottom
        for i in range(xticks + 1):
            xv = self.xlim[0] + (self.xlim[1] - self.xlim[0]) * i / xticks
            xp = self.px(xv)
            d.line([(xp, B), (xp, T)], fill=(226, 226, 226),
                       width=PLOT_SCALE)
            d.line([(xp, B), (xp, B + 4 * PLOT_SCALE)],
                       fill=(110, 110, 110), width=PLOT_SCALE)
            if xlabels:
                d.text((xp, B + 7 * PLOT_SCALE), f"{xv:.3g}", font=f,
                       fill=(45, 45, 45),
                       anchor="ma")
        for i in range(yticks + 1):
            yv = self.ylim[0] + (self.ylim[1] - self.ylim[0]) * i / yticks
            yp = self.py(yv)
            d.line([(L, yp), (R, yp)], fill=(226, 226, 226),
                       width=PLOT_SCALE)
            d.line([(L - 4 * PLOT_SCALE, yp), (L, yp)],
                       fill=(110, 110, 110), width=PLOT_SCALE)
            d.text((L - 8 * PLOT_SCALE, yp), f"{yv:.3g}", font=f,
                       fill=(45, 45, 45),
                   anchor="rm")
        d.rectangle([L, T, R, B], outline=(80, 80, 80),
                    width=max(2, 2 * PLOT_SCALE))
        if self.xlabel:
            d.text(((L + R) / 2, self.H - 22 * PLOT_SCALE), self.xlabel,
                   font=_font(15),
                   fill=(30, 30, 30), anchor="ma")
        if self.ylabel:
            self.vtext(self.ylabel, 16, (T + B) / 2)
        if self.title:
            d.text(((L + R) / 2, int(14 * PLOT_SCALE)),
                   self.title, font=_font(19),
                   fill=(0, 0, 0), anchor="ma")

    def scatter(self, xs, ys, colors=None, r=5):
        for i, (x, y) in enumerate(zip(xs, ys)):
            c = colors[i] if colors else (31, 119, 180)
            cx, cy = self.px(x), self.py(y)
            self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c,
                           outline=(255, 255, 255))

    def line(self, xs, ys, color=(31, 119, 180), width=None):
        width = width or max(2, 2 * PLOT_SCALE)
        pts = [(self.px(x), self.py(y)) for x, y in zip(xs, ys)]
        if len(pts) >= 2:
            self.d.line(pts, fill=color, width=width)

    def band(self, xs, lo, hi, color=(31, 119, 180)):
        pts = [(self.px(x), self.py(y)) for x, y in zip(xs, hi)]
        pts += [(self.px(x), self.py(y)) for x, y in zip(reversed(xs),
                                                         reversed(lo))]
        if len(pts) >= 3:
            self.d.polygon(pts, fill=tuple(int(c * 0.25 + 255 * 0.75)
                                           for c in color))

    def legend(self, items, x=None, y=None):
        f = _font(13)
        x = self.left + 14 if x is None else x
        y = self.top + 10 if y is None else y
        for i, (label, color) in enumerate(items):
            yy = y + i * 20
            self.d.rectangle([x, yy, x + 12 * PLOT_SCALE,
                          yy + 12 * PLOT_SCALE], fill=color)
            self.d.text((x + 18 * PLOT_SCALE, yy + 6 * PLOT_SCALE), label,
                        font=f, fill=(35, 35, 35),
                        anchor="lm")

    def save(self, path):
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        self.img.save(path)
        return path


def plot_scatter(ds, xname, yname, color_by=None, out="plot.png") -> dict:
    X, Y = ds.col(xname), ds.col(yname)
    p = _Plot(title=f"{_paper.describe(xname)[0]} vs "
                    f"{_paper.describe(yname)[0]}",
              xlabel=_paper.describe(xname)[0],
              ylabel=_paper.describe(yname)[0])
    p.set_range(X, Y)
    p.axes()
    colors = None
    items = None
    if color_by:
        r = cluster(ds, [xname, yname])
        if r.get("ok"):
            lab = np.array(r["labels"])
            colors = [PALETTE[int(i) % len(PALETTE)] for i in lab]
            items = [(f"cluster {j + 1} ({r['sizes'][j]} rows)",
                      PALETTE[j % len(PALETTE)]) for j in range(r["k"])]
            p.title = (f"{_paper.describe(xname)[0]} vs "
                   f"{_paper.describe(yname)[0]} "
                   f"(K-means k={r['k']})")
    p.scatter(X, Y, colors)
    if items:
        p.legend(items)
    p.save(out)
    return dict(path=out, n=len(X), kind="scatter")


def plot_forecast(ds, yname, horizon=5, out="forecast.png") -> dict:
    r = forecast(ds, yname, horizon)
    if not r.get("ok"):
        return dict(path=None, why=r.get("why"))
    t_hist = np.arange(r["n"], dtype=float)
    y_hist = ds.col(yname)
    fut_t = np.asarray(r["fut_t"])
    p = _Plot(title=f"Forecast of {_paper.describe(yname)[0]}",
              xlabel="Step", ylabel=_paper.describe(yname)[0])
    allx = np.concatenate([t_hist, fut_t])
    ally = np.concatenate([y_hist, np.asarray(r["hi"])])
    p.set_range(allx, np.concatenate([ally, np.asarray(r["lo"]),
                                      y_hist]))
    p.axes()
    p.band(fut_t, np.asarray(r["lo"]), np.asarray(r["hi"]))
    p.line(t_hist, y_hist, color=(31, 119, 180), width=2)
    p.line(fut_t, np.asarray(r["fut_y"]), color=(214, 39, 40), width=3)
    p.legend([("observed", (31, 119, 180)),
              (f"forecast ({_paper.label_en(r['best'])})",
                                         (214, 39, 40)),
              ("95% interval", tuple(int(c * 0.25 + 255 * 0.75)
                                for c in (31, 119, 180)))])
    p.save(out)
    return dict(path=out, kind="forecast", best=r["best"],
                questionable=r.get("questionable", False),
                warn=r.get("warn", []))


def plot_bar(names, values, title="", ylabel="", out="bar.png") -> dict:
    n = len(names)
    p = _Plot(title=title, xlabel="", ylabel=ylabel)
    lo = min(0.0, float(min(values)))
    hi = float(max(values))
    p.xlim, p.ylim = (0.0, float(n)), (lo, hi * 1.15 if hi > 0 else 1.0)
    p.axes(xticks=n, yticks=5, xlabels=False)
    for i, (nm, v) in enumerate(zip(names, values)):
        x0, x1 = p.px(i + 0.15), p.px(i + 0.85)
        y0, y1 = p.py(0.0), p.py(v)
        p.d.rectangle([x0, min(y0, y1), x1, max(y0, y1)],
                      fill=PALETTE[i % len(PALETTE)])
        p.d.text(((x0 + x1) / 2, p.py(v) - 8 if v >= 0 else p.py(v) + 8),
                 f"{v:.4g}", font=_font(13), fill=(30, 30, 30), anchor="mm")
        p.d.text(((x0 + x1) / 2, p.H - p.bottom + 20), nm[:12],
                 font=_font(12), fill=(40, 40, 40), anchor="ma")
    p.save(out)
    return dict(path=out, kind="bar", names=names,
                values=[float(v) for v in values])


def plot_pareto(ds, cols, minimize, out="pareto.png") -> dict:
    if len(cols) < 2:
        return dict(path=None, why="pareto needs at least two columns")
    M = ds.cols(cols)
    flags = [True] * len(cols) if minimize else [False] * len(cols)
    front = mm.pareto_idx(M, flags)
    p = _Plot(title=f"Pareto front "
                    f"({_paper.describe(cols[0])[0]} vs "
                    f"{_paper.describe(cols[1])[0]})",
              xlabel=_paper.describe(cols[0])[0],
              ylabel=_paper.describe(cols[1])[0])
    p.set_range(M[:, 0], M[:, 1])
    p.axes()
    mask = np.ones(len(M), dtype=bool)
    mask[front] = False
    p.scatter(M[mask, 0], M[mask, 1], [(190, 195, 200)] * int(mask.sum()))
    p.scatter(M[front, 0], M[front, 1],
              [(214, 39, 40)] * len(front), r=6)
    p.legend([("dominated", (190, 195, 200)),
              (f"Pareto front ({len(front)} points)", (214, 39, 40))])
    p.save(out)
    return dict(path=out, kind="pareto", n=len(M), front=len(front),
                cols=cols)




# ══════════════════════════════════════════════════════════════════════
#  灰色预测 GM(1,1)（第 81 轮补）
# ══════════════════════════════════════════════════════════════════════

def _shade_corr(r) -> tuple:
    """相关系数 → 颜色。正相关红、负相关蓝、0 接近白。"""
    a = min(1.0, abs(float(r)))
    base = (214, 39, 40) if r > 0 else (31, 119, 180)
    return tuple(int(255 - (255 - c) * a) for c in base)


def _short(s, n=10) -> str:
    """列名太长就截断 —— 画布里塞不下，会被裁成半个字。"""
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def plot_corr(ds, cols, out="corr.png") -> dict:
    """相关系数热力图。模块二明确要的第一张图。"""
    cols = ds.pick(cols) if cols else []
    if len(cols) < 2:
        return dict(path=None, why="热力图至少需要两个数值列")
    n = len(cols)
    M = ds.cols(cols)
    # 列数上限：261 列的 261x261 热力图，在 15 cm 版面上每格约 0.57 mm，
    # 读不出来；而且 cell 有 30 逻辑像素的下限，会把画布撑到
    # 10515x10387 = 1.09 亿像素（解码一次约 437 MB，触发了 PIL 的
    # DecompressionBomb 警告，也让 figcheck 的图检查一度评到假象）。
    # 按方差取前 24 列 —— 变化越大的变量，相关性越值得看。
    MAX_CELLS = 24
    _note = ""
    if n > MAX_CELLS:
        _order = sorted(range(n), key=lambda k: -float(np.var(M[:, k])))
        _keep = sorted(_order[:MAX_CELLS])
        _note = "显示 %d / %d 列（按方差取前 %d）" % (MAX_CELLS, n, MAX_CELLS)
        cols = [cols[k] for k in _keep]
        M = ds.cols(cols)
        n = len(cols)
    C = np.corrcoef(M.T)
    # 这些是"逻辑像素"，全部乘 PLOT_SCALE 后与 _Plot 的画布一致；
    # 传给 _Plot 的 w/h 再除回去，避免双重缩放。
    S = PLOT_SCALE
    cell = max(30, min(96, 900 // n)) * S
    pad_l, pad_t = 150 * S, 70 * S
    W = pad_l + cell * n + 40 * S
    H = pad_t + cell * n + 110 * S
    p = _Plot(w=max(1, W // S), h=max(1, H // S),
              title="Correlation heat map")
    d = p.d
    for i in range(n):
        for j in range(n):
            x0 = pad_l + j * cell
            y0 = pad_t + i * cell
            d.rectangle([x0, y0, x0 + cell - 2, y0 + cell - 2],
                        fill=_shade_corr(C[i, j]))
            if cell >= 40 * PLOT_SCALE:
                d.text((x0 + cell / 2 - 1, y0 + cell / 2 - 1),
                       f"{C[i, j]:.2f}", font=_font(11),
                       fill=(15, 15, 15), anchor="mm")
    # 行列标签
    for i in range(n):
        p.vtext(_short(_paper.describe(cols[i])[0], 15), pad_l - 12 * PLOT_SCALE,
                pad_t + i * cell + cell / 2, size=12)
        d.text((pad_l + i * cell + cell / 2, pad_t + n * cell + 10),
               _short(_paper.describe(cols[i])[0], 15),
               font=_font(11), fill=(40, 40, 40),
               anchor="ma")
    # 图例
    ly = H - 34 * PLOT_SCALE
    for k, (lab, r) in enumerate([("+1", 1.0), ("0", 0.0), ("-1", -1.0)]):
        x0 = pad_l + 40 * PLOT_SCALE + k * 60 * PLOT_SCALE
        d.rectangle([x0, ly, x0 + 34 * PLOT_SCALE, ly + 18 * PLOT_SCALE], fill=_shade_corr(r),
                    outline=(120, 120, 120))
        d.text((x0 + 17, ly + 26), lab, font=_font(11),
               fill=(40, 40, 40), anchor="ma")
    # plot_corr 直接画格子、不调 axes()，标题从没画过 —— 补上
    d.text((p.W / 2, int(14 * PLOT_SCALE)), p.title,
           font=_font(19), fill=(0, 0, 0), anchor="ma")
    p.save(out)
    return dict(path=out, kind="corr", n=n, cols=cols,
                note=_note,
                strong=[(cols[i], cols[j], float(C[i, j]))
                        for i in range(n) for j in range(i + 1, n)
                        if abs(C[i, j]) >= 0.5])


def plot_pred(ds, cols, yname, out="pred.png") -> dict:
    """真实值 vs 预测值。模块二明确要的第二张图。

    带 y=x 对角线：点贴着线才叫拟合好，偏离方向一看就知道系统性偏差。
    """
    cols = [c for c in cols if c in ds.num_names]
    if not cols or yname not in ds.num_names:
        return dict(path=None, why="pred 需要可用的 --x 与 --y")
    X = ds.cols(cols)
    y = ds.col(yname)
    fr = mm.fit(ds, yname, cols)
    best = fr.get("best") or {}
    kind = best.get("kind") or "linear"
    A = mm.design(X, kind)
    if A is None:
        A = mm.design(X, "linear")
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    pred = A @ beta
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    p = _Plot(title=f"Observed vs fitted "
                    f"({_paper.label_en(best.get('label', kind))})",
              xlabel="Observed", ylabel="Fitted")
    lo = float(min(y.min(), pred.min()))
    hi = float(max(y.max(), pred.max()))
    p.xlim = p.ylim = (lo, hi)
    p.axes()
    # y = x 参考线
    p.d.line([(p.px(lo), p.py(lo)), (p.px(hi), p.py(hi))],
             fill=(120, 120, 120), width=2)
    p.scatter(y, pred, [(31, 119, 180)] * len(y), r=4)
    p.d.text((p.px(hi) - 8, p.py(hi) + 150),
             f"$R^2$={r2:.4f}  RMSE={rmse:.5f}",
             font=_font(14), fill=(30, 30, 30), anchor="ra")
    p.legend([("observations", (31, 119, 180)),
              ("y = x", (120, 120, 120))])
    p.save(out)
    return dict(path=out, kind="pred", n=len(y), r2=float(r2),
                rmse=rmse, model=best.get("label"))


def plot_sens(items, out="sens.png") -> dict:
    """敏感性分析折线。模块二明确要的第三张图。

    items: [{label, base, plus, minus}] —— 参数名 + 原值 + 上下扰动后的结果
    """
    items = [it for it in (items or []) if it.get("plus") is not None]
    if not items:
        return dict(path=None, why="没有可画的敏感性结果")
    p = _Plot(title="Sensitivity to parameter perturbation",
              xlabel="Relative parameter change", ylabel="Objective value")
    xs = [-1, 0, 1]
    allv = []
    for it in items:
        allv += [it["plus"], it["base"], it["minus"]]
    allv = [v for v in allv if v is not None]
    lo, hi = min(allv), max(allv)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    m = (hi - lo) * 0.15
    p.xlim = (-1.4, 1.4)
    p.ylim = (lo - m, hi + m)
    p.axes(xticks=4, yticks=5)
    for k, it in enumerate(items):
        ys = [it["minus"], it["base"], it["plus"]]
        if None in ys:
            continue
        col = PALETTE[k % len(PALETTE)]
        pts = [(p.px(x), p.py(v)) for x, v in zip(xs, ys)]
        p.d.line(pts, fill=col, width=3)
        for (xp, yp), v in zip(pts, ys):
            p.d.ellipse([xp - 5, yp - 5, xp + 5, yp + 5], fill=col)
    p.legend([(_short(_paper.describe(it["label"])[0], 20),
               PALETTE[k % len(PALETTE)])
              for k, it in enumerate(items)])
    p.save(out)
    # 稳定性指标：最大相对变化
    rel = []
    for it in items:
        b = it.get("base")
        if b in (None, 0):
            continue
        d = max(abs((it["plus"] - b) / b), abs((it["minus"] - b) / b))
        rel.append((it["label"], float(d)))
    worst = max(rel, key=lambda t: t[1]) if rel else (None, 0.0)
    return dict(path=out, kind="sens", n=len(items),
                max_rel=worst[1], worst=worst[0],
                stable=worst[1] < 0.10)


def plot_flow(steps, out="flow.png") -> dict:
    """算法流程图。模块二明确要的第四张图。

    用方框 + 箭头竖排。不依赖 graphviz / mermaid 渲染器。
    """
    steps = [str(s) for s in (steps or [])]
    if len(steps) < 3:
        return dict(path=None, why="流程图至少 3 步")
    S = PLOT_SCALE
    bw, bh, gap = 420 * S, 62 * S, 34 * S
    W = bw + 120 * S
    H = 70 * S + len(steps) * (bh + gap) + 30 * S
    p = _Plot(w=max(1, W // S), h=max(1, H // S),
              title="Modelling workflow")
    d = p.d
    cx = W // 2
    boxes = []
    for i, s in enumerate(steps):
        y0 = 64 * S + i * (bh + gap)
        box = [cx - bw // 2, y0, cx + bw // 2, y0 + bh]
        boxes.append(box)
        first, last = (i == 0), (i == len(steps) - 1)
        fill = (232, 241, 250) if first else (
            (232, 248, 236) if last else (255, 255, 255))
        d.rounded_rectangle(box, radius=12, fill=fill,
                            outline=(90, 110, 130), width=2)
        d.text((cx, y0 + bh // 2), _short(s, 34), font=_font(14),
               fill=(25, 35, 45), anchor="mm")
    for i in range(len(boxes) - 1):
        y0 = boxes[i][3]
        y1 = boxes[i + 1][1]
        d.line([(cx, y0), (cx, y1)], fill=(90, 110, 130), width=3)
        d.polygon([(cx, y1), (cx - 8 * S, y1 - 12 * S),
                          (cx + 8 * S, y1 - 12 * S)],
                  fill=(90, 110, 130))
    p.save(out)
    return dict(path=out, kind="flow", steps=len(steps))




def plot_box(ds, cols, out="box.png") -> dict:
    """箱线图。模块二点名要的第二张（相关性热力图或箱线图）。

    为什么要看箱线图：均值会被极端值带跑，中位数和四分位距不会。
    数模里凭均值写结论是最常见的错。
    """
    cols = [c for c in cols if c in ds.num_names]
    if not cols:
        return dict(path=None, why="没有可画的数值列")
    cols = cols[:8]                      # 太多列会挤成一团
    data = [ds.col(c) for c in cols]
    p = _Plot(w=1000, h=620, title="Distribution of numeric variables",
              xlabel="", ylabel="Value")
    lo = min(float(d.min()) for d in data)
    hi = max(float(d.max()) for d in data)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    m = (hi - lo) * 0.08
    p.xlim, p.ylim = (0.0, float(len(cols))), (lo - m, hi + m)
    p.axes(xticks=len(cols), yticks=6, xlabels=False)
    stats = []
    for i, (nm, v) in enumerate(zip(cols, data)):
        q1, med, q3 = [float(x) for x in np.percentile(v, [25, 50, 75])]
        iqr = q3 - q1
        lo_w = max(float(v.min()), q1 - 1.5 * iqr)
        hi_w = min(float(v.max()), q3 + 1.5 * iqr)
        cx = i + 0.5
        w = 0.26
        col = PALETTE[i % len(PALETTE)]
        # 箱体
        p.d.rectangle([p.px(cx - w), p.py(q3), p.px(cx + w), p.py(q1)],
                      fill=col, outline=(60, 60, 60))
        # 中位线
        p.d.line([(p.px(cx - w), p.py(med)), (p.px(cx + w), p.py(med))],
                 fill=(255, 255, 255), width=3)
        # 须
        p.d.line([(p.px(cx), p.py(q3)), (p.px(cx), p.py(hi_w))],
                 fill=(80, 80, 80), width=2)
        p.d.line([(p.px(cx), p.py(q1)), (p.px(cx), p.py(lo_w))],
                 fill=(80, 80, 80), width=2)
        for yv in (hi_w, lo_w):
            p.d.line([(p.px(cx - w * 0.6), p.py(yv)),
                      (p.px(cx + w * 0.6), p.py(yv))],
                     fill=(80, 80, 80), width=2)
        # 离群点
        out_mask = (v < lo_w) | (v > hi_w)
        for yv in v[out_mask][:80]:
            xp, yp = p.px(cx), p.py(float(yv))
            p.d.ellipse([xp - 2, yp - 2, xp + 2, yp + 2],
                        fill=(214, 39, 40))
        p.d.text((p.px(cx), p.H - p.bottom + 18),
                  _short(_paper.describe(nm)[0], 16),
                 font=_font(11), fill=(40, 40, 40), anchor="ma")
        stats.append(dict(name=nm, q1=q1, median=med, q3=q3,
                          iqr=iqr, n_out=int(out_mask.sum()),
                          min=float(v.min()), max=float(v.max())))
    p.save(out)
    return dict(path=out, kind="box", stats=stats)


def plot_hist(ds, col, out="hist.png", bins=30) -> dict:
    """直方图 + 正态参考曲线。看分布形状，决定要不要变换。"""
    if col not in ds.num_names:
        return dict(path=None, why=f"{col!r} 不是数值列")
    v = ds.col(col).astype(float)
    cnt, edges = np.histogram(v, bins=bins)
    p = _Plot(w=980, h=600,
              title=f"Distribution of "
                    f"{_short(_paper.describe(col)[0], 30)}",
              xlabel="Value", ylabel="Count")
    p.xlim = (float(edges[0]), float(edges[-1]))
    p.ylim = (0.0, float(cnt.max()) * 1.18)
    p.axes(xticks=6, yticks=6)
    bw = (edges[1] - edges[0])
    for k, c in enumerate(cnt):
        x0, x1 = p.px(edges[k]), p.px(edges[k + 1])
        # 屏幕坐标 y 向下，PIL 要求 y1 >= y0，所以上边界在前
        p.d.rectangle([x0, p.py(float(c)), x1 - 1, p.py(0)],
                      fill=(31, 119, 180))
    # 正态参考：同样的均值方差
    mu, sd = float(v.mean()), float(v.std(ddof=1))
    if sd > 0:
        xs = np.linspace(float(edges[0]), float(edges[-1]), 160)
        pdf = (np.exp(-0.5 * ((xs - mu) / sd) ** 2)
               / (sd * np.sqrt(2 * np.pi)))
        scale = cnt.sum() * bw
        pts = [(p.px(float(x)), p.py(float(y) * scale))
               for x, y in zip(xs, pdf)]
        p.d.line(pts, fill=(214, 39, 40), width=3)
    p.legend([("observed", (31, 119, 180)),
              (f"normal($\\mu$={mu:.4g}, $\\sigma$={sd:.4g})",
               (214, 39, 40))])
    p.save(out)
    sk = float(np.mean(((v - mu) / sd) ** 3)) if sd > 0 else 0.0
    ku = float(np.mean(((v - mu) / sd) ** 4)) - 3 if sd > 0 else 0.0
    return dict(path=out, kind="hist", col=col, skew=sk, kurt=ku,
                mean=mu, std=sd,
                near_normal=(abs(sk) < 0.5 and abs(ku) < 1.0))


def plot_resid(ds, cols, yname, out="resid.png") -> dict:
    """残差图：残差 vs 拟合值。

    这是判断线性假设成立的**第一张该看的图**：
    有喇叭口 → 异方差；有弯曲 → 模型形式不对。
    """
    cols = [c for c in cols if c in ds.num_names]
    if not cols or yname not in ds.num_names:
        return dict(path=None, why="resid 需要 --x 与 --y")
    X, y = ds.cols(cols), ds.col(yname)
    A = mm.design(X, "linear")
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    pred = A @ beta
    res = y - pred
    p = _Plot(w=980, h=600, title="Residuals versus fitted values",
              xlabel="Fitted value", ylabel="Residual")
    lo, hi = float(pred.min()), float(pred.max())
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    m = (hi - lo) * 0.06
    rlo, rhi = float(res.min()), float(res.max())
    pad = (rhi - rlo) * 0.12 or 1.0
    p.xlim = (lo - m, hi + m)
    p.ylim = (rlo - pad, rhi + pad)
    p.axes()
    p.d.line([(p.px(p.xlim[0]), p.py(0)), (p.px(p.xlim[1]), p.py(0))],
             fill=(120, 120, 120), width=2)
    p.scatter(pred, res, [(31, 119, 180)] * len(pred), r=4)
    # 喇叭口检测：分四段看残差离散度
    order = np.argsort(pred)
    q = max(1, len(order) // 4)
    segs = [float(np.std(res[order[i * q:(i + 1) * q]], ddof=1))
            for i in range(4)]
    spread = (max(segs) / min(segs)) if min(segs) > 0 else float("inf")
    p.d.text((p.px(p.xlim[1]) - 6, p.py(p.ylim[1]) + 26),
             f"segment sd ratio = {spread:.2f}",
             font=_font(13), fill=(30, 30, 30), anchor="ra")
    p.save(out)
    return dict(path=out, kind="resid", n=len(res),
                sd_ratio=float(spread),
                hetero=(spread > 2.0))


def plot_qq(ds, yname, cols, out="qq.png") -> dict:
    """正态 Q-Q 图。残差是否近似正态 —— 决定 t 检验能不能信。"""
    cols = [c for c in cols if c in ds.num_names]
    if not cols or yname not in ds.num_names:
        return dict(path=None, why="qq 需要 --x 与 --y")
    X, y = ds.cols(cols), ds.col(yname)
    A = mm.design(X, "linear")
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    res = np.sort(y - A @ beta)
    n = len(res)
    # 理论分位数：用正态的逆 CDF 近似（不依赖 scipy）
    probs = (np.arange(1, n + 1) - 0.5) / n
    # Acklam 近似
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    q = np.where(probs < 0.5, probs, 1 - probs)
    t = np.sqrt(-2 * np.log(q))
    num = ((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]
    den = (((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1
    z = num / den
    z = np.where(probs < 0.5, z, -z)
    mu, sd = float(res.mean()), float(res.std(ddof=1))
    zs = mu + sd * z
    p = _Plot(w=760, h=680, title="Normal Q-Q plot of residuals",
              xlabel="Theoretical quantile", ylabel="Sample quantile")
    lo = float(min(zs.min(), res.min()))
    hi = float(max(zs.max(), res.max()))
    p.xlim = p.ylim = (lo, hi)
    p.axes()
    p.d.line([(p.px(lo), p.py(lo)), (p.px(hi), p.py(hi))],
             fill=(214, 39, 40), width=2)
    p.scatter(zs, res, [(31, 119, 180)] * n, r=3)
    p.legend([("residuals", (31, 119, 180)), ("normal reference",
                                              (214, 39, 40))])
    p.save(out)
    # 相关系数：|r| 越接近 1 越接近正态
    rr = float(np.corrcoef(zs, res)[0, 1]) if n > 2 else float("nan")
    return dict(path=out, kind="qq", n=n, r=rr, near_normal=(rr > 0.98))



def gm11(series, horizon: int = 5) -> dict:
    """灰色预测 GM(1,1)。适合**小样本、近似指数**的序列（4~10 个点）。

    为什么数模要它：
        当手里只有五六个历史点时，ARIMA 拟合不出来、回归的置信区间宽到没用。
        GM(1,1) 只要 4 个点就能跑，是这类题的常见答案。

    模型：设原始序列 x0，一次累加得 x1，
        dx1/dt + a·x1 = b
    最小二乘解 a、b 后，
        x̂1(k+1) = (x0(1) - b/a)·e^(-a·k) + b/a
        x̂0(k+1) = x̂1(k+1) - x̂1(k)        ← 累减还原

    检验（两个都要给，缺一个就没法判断可信度）：
        后验差比  C = S2 / S1        （S1 原始序列标准差，S2 残差标准差）
        小误差概率 P = P{|e - ē| < 0.6745·S1}
        C 越小越好；P 越大越好。
        好：C<0.35 且 P>0.95；合格：C<0.5 且 P>0.8；否则**不合格**。
    """
    x = np.asarray([float(v) for v in series], dtype=float)
    n = len(x)
    if n < 4:
        return dict(ok=False, why=f"只有 {n} 个点，GM(1,1) 至少要 4 个")
    if np.any(x <= 0):
        return dict(ok=False, why="序列含 0 或负数，GM(1,1) 要求全为正")
    if np.allclose(x, x[0]):
        return dict(ok=False, why="序列完全不变，没有可提取的趋势")

    x1 = np.cumsum(x)                       # 一次累加 AGO
    z1 = 0.5 * (x1[1:] + x1[:-1])           # 紧邻均值生成
    B = np.column_stack([-z1, np.ones(n - 1)])
    Y = x[1:]
    # 最小二乘
    coef, *_ = np.linalg.lstsq(B, Y, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    if abs(a) < 1e-12:
        return dict(ok=False, why="发展系数 a≈0，模型退化为常数，不适用")

    k = np.arange(n)
    x1_hat = (x[0] - b / a) * np.exp(-a * k) + b / a
    x0_hat = np.empty(n)
    x0_hat[0] = x1_hat[0]
    x0_hat[1:] = np.diff(x1_hat)

    resid = x - x0_hat
    s1 = float(np.std(x, ddof=1))
    s2 = float(np.std(resid, ddof=1))
    C = s2 / s1 if s1 > 0 else float("inf")
    e_bar = float(np.mean(resid))
    P = float(np.mean(np.abs(resid - e_bar) < 0.6745 * s1))

    if C < 0.35 and P > 0.95:
        grade = "好"
    elif C < 0.5 and P > 0.8:
        grade = "合格"
    else:
        grade = "不合格"

    kk = np.arange(n, n + horizon)
    x1_fut = (x[0] - b / a) * np.exp(-a * kk) + b / a
    last = x1_hat[-1]
    x0_fut = np.empty(horizon)
    prev = last
    for i in range(horizon):
        x0_fut[i] = x1_fut[i] - prev
        prev = x1_fut[i]

    warn = []
    if grade == "不合格":
        warn.append(f"后验差检验不合格（C={C:.3f}, P={P:.3f}）—— "
                    f"这个预测不能当作结论")
    if abs(a) < 0.05:
        warn.append(f"发展系数 a={a:.4f} 很小，序列接近平缓，"
                    f"此时预测的有效期很短")
    if n > 12:
        warn.append(f"{n} 个点已经偏多，GM(1,1) 的优势（小样本）没了，"
                    f"考虑用常规时间序列模型")

    return dict(ok=True, n=n, a=a, b=b, C=C, P=P, grade=grade,
                fitted=x0_hat.tolist(), resid=resid.tolist(),
                fut=np.asarray(x0_fut, float).tolist(),
                warn=warn, series=x.tolist())


def print_gm11(r: dict) -> None:
    print()
    print("=" * 84)
    print(f"灰色预测 GM(1,1)（{r['n']} 个历史点，外推 {len(r['fut'])} 步）")
    print("=" * 84)
    print(f"  发展系数 a = {r['a']:+.6f}    灰作用量 b = {r['b']:.6f}")
    # 时间响应式要按符号拼，不能直接 f"({x} - {b/a})" ——
    # b/a 为负时会打印成 "(2.87 - -82.39) + -82.39"，双负号读者会看错。
    coef = r["series"][0] - r["b"] / r["a"]
    tail = r["b"] / r["a"]
    tail_s = f"+ {tail:.4f}" if tail >= 0 else f"- {abs(tail):.4f}"
    print(f"  时间响应式：x̂1(k+1) = {coef:.4f}·e^({-r['a']:+.6f}k) {tail_s}")
    print()
    print(f"  {'期':>4}{'实测':>14}{'拟合':>14}{'残差':>14}")
    for i, (o, f_, e) in enumerate(zip(r["series"], r["fitted"], r["resid"]), 1):
        print(f"  {i:>4}{o:>14.6f}{f_:>14.6f}{e:>14.6f}")
    print()
    print(f"  后验差比 C = {r['C']:.4f}    小误差概率 P = {r['P']:.3f}    "
          f"精度等级 **{r['grade']}**")
    print(f"  （判据：好 C<0.35 且 P>0.95；合格 C<0.5 且 P>0.8；否则不合格）")
    print()
    print(f"  {'外推步':>8}{'预测':>16}")
    for i, v in enumerate(r["fut"], 1):
        print(f"  {i:>8}{v:>16.6f}")
    print()
    if r["warn"]:
        for w in r["warn"]:
            print(f"  ⚠ {w}")
        print()
    print("  边界：GM(1,1) 假设序列近似**指数**变化。S 形或周期序列会被它拉直，")
    print("        拟合值看着还行、外推却会跑飞 —— 所以后验差检验不能省。")



# ══════════════════════════════════════════════════════════════════════
#  图论（第 82 轮补）
# ══════════════════════════════════════════════════════════════════════
def parse_edges(spec: str) -> list[tuple[int, int, float]]:
    """"0-1:4,1-2:3" → [(0,1,4.0),(1,2,3.0)]。

    节点必须是整数下标；权重可以用 1/3 这种写法。
    """
    out = []
    for seg in (spec or "").split(","):
        seg = seg.strip()
        if not seg:
            continue
        if ":" not in seg:
            raise ValueError(f"边 {seg!r} 缺少权重（应为 u-v:w）")
        uv, _, w = seg.partition(":")
        if "-" not in uv:
            raise ValueError(f"边 {seg!r} 缺少端点（应为 u-v:w）")
        u, _, v = uv.partition("-")
        out.append((int(u.strip()), int(v.strip()),
                    float(safe_expr(w.strip())(0.0, [0.0]))))
    if not out:
        raise ValueError("没有解析出任何边")
    return out


def print_graph(r: dict, op: str) -> None:
    print()
    print("=" * 84)
    if op == "dijkstra":
        print(f"单源最短路（Dijkstra）· 起点 {r['src']}")
        print("=" * 84)
        if "dst" in r and r.get("unreachable"):
            print(f"  {r['src']} → {r['dst']}：**不可达**（没有通路）")
        elif "dst" in r:
            print(f"  {r['src']} → {r['dst']}  距离 {r['dist']:.6f}")
            print(f"  路径 {' → '.join(map(str, r['path']))}")
        else:
            print(f"  {'目标':>6}{'距离':>14}   路径")
            for t in sorted(r["paths"]):
                d = r["dist"][t]
                ds = "∞" if d == float("inf") else f"{d:.6f}"
                p = (" → ".join(map(str, r["paths"][t]))
                     if r["paths"][t] else "不可达")
                print(f"  {t:>6}{ds:>14}   {p}")
        print()
        print("  边界：Dijkstra 要求**非负权**。有负权会被它拒绝——")
        print("        负权图要用 Bellman-Ford，别把 Dijkstra 硬套上去。")
    elif op == "mst":
        print(f"最小生成树（Kruskal）· {r['n']} 个点")
        print("=" * 84)
        print(f"  权重合计 {r['weight']:.6f}，选了 {len(r['mst'])} 条边")
        print()
        print(f"  {'u':>5}{'v':>5}{'w':>12}")
        for u, v, w in r["mst"]:
            print(f"  {u:>5}{v:>5}{w:>12.6f}")
        if r["warn"]:
            print()
            for w in r["warn"]:
                print(f"  ⚠ {w}")
        else:
            print()
            print("  ✓ 图连通，这是一棵真正的生成树（边数 = 点数 - 1）")
    elif op == "flow":
        print(f"最大流（Edmonds-Karp）· {r['s']} → {r['t']}")
        print("=" * 84)
        print(f"  最大流 = {r['max_flow']:.6f}（{r['augmentations']} 次增广）")
        print()
        print("  边界：最大流只回答「最多能送多少」。管道长度、成本、时延")
        print("        都不在这个模型里 —— 那些要建最小费用流。")
    elif op == "tsp":
        print(f"旅行商（最近邻 + 2-opt）· {r['n']} 个点")
        print("=" * 84)
        print(f"  路径 {' → '.join(map(str, r['tour']))} → {r['tour'][0]}")
        print(f"  总长度 {r['length']:.6f}")
        print(f"  下界   {r['lower_bound']:.6f}（每点最短两边之和 /2）")
        print(f"  差距   {r['gap']:.2%}")
        print()
        if r["warn"]:
            for w in r["warn"]:
                print(f"  ⚠ {w}")
        else:
            print("  ✓ 与下界差距很小，可以当作最优解用")
        print()
        print("  边界：这是**近似解**，不保证最优。论文里要写「用 2-opt 近似」，")
        print("        不能写「求得最优路径」—— 除非你用 Held-Karp 跑了精确解。")
    print()



def to_markdown(rep: dict) -> str:
    """把一次运行的结果写成 markdown —— 直接能贴进论文的形态。

    不写花哨排版，只写三样：数字、判决、依据。
    论文里最容易被追问的就是这三样，先摆在这里。
    """
    L: list[str] = []
    A = L.append
    A(f"# 建模报告 · {rep.get('file', '')}")
    A("")
    A(f"- 数据：`{rep.get('file', '')}` / sheet `{rep.get('sheet', '')}`"
      f" / {rep.get('rows', '?')} 行")
    A(f"- 数值列：{', '.join(rep.get('cols', []))}")
    A("")

    # 体检
    if rep.get("eda"):
        e = rep["eda"]
        A("## 一、数据体检")
        A("")
        A("| 列 | min | max | mean | std | 取值数 | 异常值 | 分布 |")
        A("|---|---|---|---|---|---|---|---|")
        for c in e["per_col"]:
            dist = "近正态" if c["near_normal"] else "偏离"
            A(f"| {c['name']} | {c['min']:.4f} | {c['max']:.4f} | "
              f"{c['mean']:.4f} | {c['std']:.4f} | {c['n_unique']} | "
              f"{c['n_outlier']} | {dist} |")
        if e.get("id_cols"):
            A("")
            A(f"ID 列（不进 VIF）：{', '.join(e['id_cols'])}")
        A("")

    # 结构
    if rep.get("fit"):
        f = rep["fit"]
        A("## 二、结构竞速")
        A("")
        A(f"目标 `{f['y']}` ← 自变量 {', '.join(f['x'])}")
        A("")
        A("| 候选 | CV RMSE | 相对线性 |")
        A("|---|---|---|")
        for c in f["cands"]:
            if c.get("rmse") is None:
                A(f"| {c['label']} | 不适用 | — |")
            else:
                g = c.get("gain_vs_linear")
                A(f"| {c['label']} | {c['rmse']:.5f} | "
                  f"{'—' if g is None else f'{g:+.1%}'} |")
        A("")
        A(f"最优：**{f['best']}**，线性结构条件数 {f['cond_linear']:.2f}。")
        A("")

    # 验证
    if rep.get("verify"):
        A("## 三、结论验证（多通道并行）")
        A("")
        A("| 编号 | 结论 | 试判 | C | 判决 | 能怎么写 |")
        A("|---|---|---|---|---|---|")
        for r in rep["verify"]:
            if r.get("vetoed"):
                style = "被方向通道否决，改结论"
            elif r["refuted"]:
                style = "被数据推翻，改写法"
            elif r["final"] == "pass":
                style = "可断言"
            elif r["final"] == "degrade":
                style = "写进「局限」段"
            else:
                style = "证据不足"
            if not r.get("sign"):
                style = "提示，不是结论"
            A(f"| {r['cid']} | {r['text']} | {r['grade']} | {r['C']} | "
              f"**{r['final']}** | {style} |")
        A("")
        A("每条结论的通道级证据见屏幕输出；这里只留最终判决。")
        A("")

    # 跨主张
    if rep.get("conflicts") is not None:
        A("## 四、跨主张一致性")
        A("")
        if rep["conflicts"]:
            for c in rep["conflicts"]:
                A(f"- ⚠ {c['why']}")
        else:
            A("没有互斥主张同时对得上，这一组自洽。")
        A("")

    # 优化
    if rep.get("opt"):
        o = rep["opt"]
        A("## 五、多目标")
        A("")
        A(f"- 目标：{', '.join(o['cols'])}")
        A(f"- 帕累托前沿：{o['front']} / {o['n_rows']} 个点")
        A(f"- 权重扫描：{o['n_picks']} 组权重 → {o['n_solutions']} 个不同最优解")
        if o.get("most_stable"):
            A(f"- 最稳解：第 {o['most_stable']} 行，"
              f"占 {o['stable_share']:.0%} 权重空间")
        A("")

    if rep.get("solve"):
        s = rep["solve"]
        A("## 六、约束优化")
        A("")
        if s.get("mode") == "discrete":
            A(f"- 自变量全离散：{s['n_combos']} 种组合")
            A(f"- 满足约束的已观测组合：{s['n_observed_ok']} 个")
            A(f"- 满足约束的未观测组合：{s['n_predicted_ok']} 个")
            if s.get("best_observed"):
                bo = s["best_observed"]
                A(f"- **观测最优**：第 {bo['row']} 行，目标 = {bo['obj']:.6f}"
                  f"（真做过的组合）")
        A("")

    A("---")
    A("")
    A("## 边界声明")
    A("")
    A(f"- e3（可复现）= {'2 已声明重跑' if rep.get('reproduced') else '1 未重跑'}")
    A("- 未重跑时最高只能判 degrade：单份数据的内部一致性撑不起「可复现」")
    A("- 权重区间只说明「在这个区间内结论不变」，取哪个值是立场，不是数据")
    return "\n".join(L) + "\n"


# ══════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════

# JSON 模式下诊断信息必须走 stderr（第 92 轮）。
# 原来 _data_note 的每一行都 print 到 stdout，而 mmkit run --json 的
# JSON 也写 stdout —— 只要有一道题触发丢行/非数值列/时间轴/准常数列
# 其中任意一条，输出就不可解析。smoke 测试的样例恰好一条都没触发，
# 所以这个洞一直没暴露；第 92 轮我在 _data_note 里加了一行「用的是哪个
# 数据文件」，立刻把 JSON 弄坏了，才把整件事翻出来。
_JSON_OUT = False


def _note(msg: str) -> None:
    print(msg, file=(sys.stderr if _JSON_OUT else sys.stdout))


def _data_note(ds) -> None:
    """把「丢了多少行 / 哪些列不参与建模 / 哪些列不能当变量」打出来。

    悄悄丢数据是最容易导致错误结论的事：真实 CSV 里一个稀疏列
    就能让九成行消失，用户如果看不到这个提示，会把
    「只剩 300 行」当成「本来就只有 300 行」。

    第 88 轮在 A 题真实附件上补了两条：
      · TIME 列会被当成数值列 —— 有人真的会拿它当目标变量
      · CLR 这类准常数列（355 行里 354 个是 5.0）进模型只会制造噪声

    第 92 轮补：**说清用的是哪个文件**。
    `mm.find_xlsx()` 扫的是整个工作区，里面 20 多个 xlsx；不传 prefer 时
    返回遍历顺序第一个，对每道题都是同一个文件，而且永远不返回空 ——
    第 83 轮因此白跑一轮（22/23 道题的泄漏检查其实查的是同一张表）。
    函数契约不改，但这一层必须把选择说出来。
    """
    try:
        import datapath as _dp
        lp = getattr(_dp, "LAST_PICK", {}) or {}
        if lp.get("path") and os.path.abspath(lp["path"]) == \
                os.path.abspath(getattr(ds, "path", "") or ""):
            n = int(lp.get("n_candidates") or 0)
            if n > 1:
                _note(f"  ⚠ 工作区里找到 {n} 个 xlsx，本次用的是 "
                      f"{os.path.basename(lp['path'])}"
                      + (f"（按关键字 {lp['prefer']!r} 选的）"
                         if lp.get("prefer") else "（按遍历顺序取的）")
                      + " —— 要指定请加 --data")
            elif n == 1:
                _note(f"  · 数据文件 {os.path.basename(lp['path'])}")
    except Exception:                                   # noqa: BLE001
        pass
    note = getattr(ds, "drop_note", lambda: "")()
    if note:
        _note(f"  ⚠ {note}")
    nn = getattr(ds, "non_numeric_note", lambda: "")()
    if nn:
        _note(f"  · {nn}")
    try:
        _nr = mm.non_response_cols(ds)
    except Exception:                                   # noqa: BLE001
        _nr = []
    tc = [c for c, k in _nr if k == "time"]
    _ids = [c for c, k in _nr if k == "id"]
    if tc:
        _note(f"  ⚠ 时间轴列 {tc} —— 这是时间，不是被解释变量。"
              f" 不要把它当 --y（真要用时间序列，用 forecast 子命令）")
    if _ids:
        # 第 109 轮：标识列与时间轴分开说。原来并在一起，
        # 对着「方案编号」说「这是时间」，话是错的。
        _note(f"  · 标识列 {_ids} —— 这是编号，既不是被解释变量，也不该当因子")
    try:
        dg = ds.degenerate_cols()
    except Exception:                                   # noqa: BLE001
        dg = []
    if dg:
        _note(f"  ⚠ 准常数列 {dg} —— 九成以上是同一个值，"
              f"方差近 0，当自变量没有意义")







def _q5_ctx(ds, min_cols: str, xs, q4):
    """问题 5：加工误差对选定设计的影响。

    设计点取问题 4 的 minimax-regret 解 —— 题目说「在前述研究基础上」，
    所以这里扰动的必须是前面选出来的那一个设计，不是别的点。
    """
    try:
        import q5 as _q5
        # 局部取一次 paper：模块级的 `_paper` 在这条调用链上没解析到
        # （实测 NameError: name '_paper' is not defined）。
        import paper as _pap
        ys = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
        ys = [c for c in ds.pick(ys)] if ys else []
        ys = [c for c in ys if c in ds.num_names]
        _xs = [c for c in ds.pick(list(xs))] if xs else []
        if not ys or not _xs or not (q4 or {}).get("robust"):
            return {}
        row = int(q4["robust"]["idx"])
        res = _q5.design_sensitivity(ds, _xs, ys, row)
        res["summary"] = _q5.summary(
            res, translate=lambda c: (_pap.describe(c)[0]
                                      if _pap.describe(c) else str(c)))
        # 边界上那个因子往内移一格，代价多少
        if res.get("at_bound"):
            _f, _v, _lo, _hi = res["at_bound"][0]
            _target = _hi - 0.05 * (_hi - _lo)
            res["tradeoff"] = _q5.margin_tradeoff(
                ds, _xs, ys, row, _f, _target)
        return res
    except Exception:                               # noqa: BLE001
        return {}

def _q4_ctx(ds, min_cols: str, ycol: str, xs):
    """问题 4 的数据：权重扫描 + minimax regret 鲁棒设计。

    题目要求「权重变化对最优方案的影响」和「对偏好变化不敏感的鲁棒方案」。
    指标取 --min 给的三列；不足三列时退化为「y 加前两个因子」不合理，
    所以只在前瞻到两个以上目标时才做。
    """
    try:
        import q4 as _q4
        import numpy as _np
        cols = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
        cols = [c for c in ds.pick(cols)] if cols else []
        cols = [c for c in cols if c in ds.num_names]
        if len(cols) < 2:
            return {}
        M = _np.column_stack([_np.asarray(ds.col(c), dtype=float)
                              for c in cols])
        sw = _q4.weight_sweep(M, [True] * len(cols))
        rb = _q4.robust_design(M, [True] * len(cols))
        n = len(M)
        return dict(
            cols=cols,
            sweep=dict(n_weights=sw["n_weights"],
                       n_rows=sw["n_rows"],
                       dist=sw["dist"]),
            robust=rb,
            # 便于论文说「在 66 个场景里 X% 由同一个方案胜出」
            top_share=(sw["dist"][0][1] / sw["n_weights"]
                       if sw["dist"] else 0.0),
        )
    except Exception:                               # noqa: BLE001
        return {}


def _multimodel_ctx(ds, min_cols: str, ycol: str, xs):
    """三指标分别建模。题目问题 2 要「代理模型」，而我们之前只建了热阻。

    实测三个指标的最优形式不同（热阻线性、压降与温度二次），
    所以不能报一个模型覆盖三个指标。
    """
    try:
        import multimodel as _mm3

        def _tr(x):
            s = str(x)
            if s in ("线性", "二次", "对数", "幂律") or s.startswith("岭"):
                return _paper.label_en(s)
            d = _paper.describe(s)
            return d[0] if d else s

        ys = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
        ys = [c for c in ds.pick(ys)] if ys else []
        ys = [c for c in ys if c in ds.num_names]
        if len(ys) < 2:
            return {}
        _xs = list(xs) if xs else []
        res = _mm3.fit_all(ds, ys, _xs, translate=_tr)
        res["lines"] = _mm3.summary_lines(res)
        return res
    except Exception:                               # noqa: BLE001
        return {}


def _signs_ctx(ds, min_cols: str, xs):
    """机理预测方向 vs 观测符号。题目问题 1 要「结合机理」，
    而机理只有能被数据推翻才算真用了。

    预测来自守恒律（能量/动量），见论文 Mechanistic basis 一节：
      热阻  R = R_cond + 1/(hA)：针肋增面积、扰边界层 → 降
            歧管深高比：深分配层但压缩通道层，方向不唯一 → 记 "?"
      压降  Darcy-Weisbach：歧管缩短 L → 降；针肋加 ΣK 且压缩流通面积
            使 u 上升（平方项）→ 升
      温度  歧管改善分配 → 降；针肋增混合但有阻塞，方向不唯一 → "?"
    """
    try:
        import numpy as _np
        ys = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
        ys = [c for c in ds.pick(ys)] if ys else []
        ys = [c for c in ys if c in ds.num_names]
        _xs = [c for c in ds.pick(list(xs))] if xs else []
        if not ys or not _xs:
            return {}

        # 预测：key 是 (指标关键词, 因子关键词)，值是 "+"/"-"/"?"
        PRED = {
            ("热阻", "宽度"): "-",
            ("热阻", "深高"): "?",
            ("热阻", "排数"): "-",
            ("压降", "宽度"): "+",
            ("压降", "深高"): "-",
            ("压降", "排数"): "+",
            ("温度", "宽度"): "-",
            ("温度", "深高"): "-",
            ("温度", "排数"): "?",
        }

        def _key(name, table):
            for k, v in table.items():
                if k in name:
                    return v
            return "?"

        rows, n_pred, n_hit, mismatch = [], 0, 0, []
        for yc in ys:
            yv = _np.asarray(ds.col(yc), dtype=float)
            for xc in _xs:
                X = _np.column_stack(
                    [_np.asarray(ds.col(c), dtype=float) for c in _xs])
                A = _np.column_stack([_np.ones(len(yv)), X])
                b, *_ = _np.linalg.lstsq(A, yv, rcond=None)
                j = _xs.index(xc) + 1
                coef = float(b[j])
                obs = "+" if coef > 0 else ("-" if coef < 0 else "0")
                # 两级查表：指标关键词 + 因子关键词
                pred = "?"
                for (yk, xk), pv in PRED.items():
                    if yk in yc and xk in xc:
                        pred = pv
                        break
                rows.append(dict(
                    y_en=_paper.describe(yc)[0] if _paper.describe(yc)
                    else yc,
                    x_en=_paper.describe(xc)[0] if _paper.describe(xc)
                    else xc,
                    # key 必须是单个符号，不能写成 " + "（前后带空格）——
                    # 那样 "+" 永远匹配不上，三条增大的预测会全变成
                    # not fixed，看着像「机理没给方向」，其实是查表写错。
                    pred={"+": "increase", "-": "decrease",
                          "?": "not fixed"}.get(pred, "not fixed"),
                    obs="increase" if obs == "+" else (
                        "decrease" if obs == "-" else "flat"),
                    coef=coef,
                    match=(pred == obs) if pred != "?" else None,
                ))
                if pred != "?":
                    n_pred += 1
                    if pred == obs:
                        n_hit += 1
                    else:
                        mismatch.append(
                            f"{_paper.describe(yc)[0]} moves the wrong way "
                            f"against {_paper.describe(xc)[0]} "
                            f"(coefficient {coef:+.4f}), which the "
                            f"leading-order balance does not predict.")
        return dict(rows=rows, n_pred=n_pred, n_hit=n_hit,
                    mismatch=mismatch)
    except Exception:                               # noqa: BLE001
        return {}




def _cond_raw(ds, xs):
    """原始尺度条件数（含量纲差异），用来解释「为什么不能直接读它」。"""
    try:
        import dataprof as _dp
        if not xs:
            return None
        return _dp.condition_numbers(ds, list(xs)).get("raw")
    except Exception:                               # noqa: BLE001
        return None


def _spans(ds, xs):
    """各因子的取值跨度 —— 量纲差异的来源，逐个数出来比手写可靠。"""
    try:
        out = []
        for c in (xs or []):
            v = [np.asarray(ds.col(c), dtype=float)]
            out.append(float(v[0].max() - v[0].min()))
        return out
    except Exception:                               # noqa: BLE001
        return []


def _cases_ctx(kind_res, ds, problem):
    """按题型与方法检索相似历史案例。"""
    try:
        import cases as _cases
        kinds = (kind_res or {}).get("kinds") or []
        methods = ["pareto", "cv", "sens", "resid", "interval", "surrogate"]
        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]
        return _cases.find(kinds=kinds, methods=methods,
                           cols=cols, problem=problem or "", top=3)
    except Exception:                               # noqa: BLE001
        return []


def _kind_ctx(problem, ds, xs, ycol, n_obj=None):
    """题型识别：题目描述 + 数值列 + **结构信号** → 题型与所需模块。

    识别结果决定 paper.py 走 full / brief / none 哪条机理分支。
    结构信号（目标个数、行数、有没有时间维度）比列名可靠：
    列名是用户起的，pop2005 这种名字谁都无法据此判类型。
    """
    try:
        import kind as _kind
        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]
        n_rows = int(getattr(ds, "n_rows", 0) or 0)
        # 时间维度：列名里出现年份/月份这类词
        _low = " ".join(cols).lower()
        has_time = any(w in _low for w in (
            "date", "time", "year", "month", "week", "quarter",
            "period", "day"))
        return _kind.detect(problem or "", cols, ycol,
                            n_obj=n_obj, n_rows=n_rows,
                            has_time=has_time)
    except Exception:                               # noqa: BLE001
        return {}

def _pi_ctx(ds, min_cols: str, xs):
    """三个指标的 95% 预测区间。"""
    try:
        ys = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
        ys = [c for c in ds.pick(ys)] if ys else []
        ys = [c for c in ys if c in ds.num_names]
        _xs = [c for c in ds.pick(list(xs))] if xs else []
        if not ys or not _xs:
            return {}
        rows = []
        for yc in ys:
            r = mm.pred_interval(ds, yc, _xs)
            d = _paper.describe(yc)
            rows.append(dict(y=yc, y_en=(d[0] if d else yc), **r))
        return dict(rows=rows, level=0.95)
    except Exception:                               # noqa: BLE001
        return {}



def _obj_cols(ds, min_cols):
    """目标列（取自 --min），去真实列名。"""
    cols = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
    cols = ds.pick(cols) if cols else []
    return [c for c in cols if c in ds.num_names]


def _diag_ctx(ds, min_cols: str, xs):
    """每个指标的残差诊断。"""
    try:
        ys = _obj_cols(ds, min_cols)
        _xs = [c for c in ds.pick(list(xs))] if xs else []
        if not ys or not _xs:
            return {}
        rows = []
        for yc in ys:
            # y 若同时出现在 --x 里（用户把目标也当解释变量），
            # 设计矩阵共线，diag_report 返回空 —— 整节残差诊断
            # 就静默消失。剔除自身再算。实测 review_microwave
            # 的 --min 含 star_rating 而 --x 也有它，一行都没出。
            _xs_y = [c for c in _xs if c != yc]
            if not _xs_y:
                continue
            r = mm.diag_report(ds, yc, _xs_y)
            if r:
                d = _paper.describe(yc)
                r["y_en"] = d[0] if d else yc
                r["x_en"] = [_paper.describe(c)[0] if _paper.describe(c) else c
                             for c in _xs_y]
                rows.append(r)
        return dict(rows=rows)
    except Exception:                               # noqa: BLE001
        return {}


def _front_ctx(ds, min_cols: str):
    """前沿计算过程。"""
    try:
        cols = _obj_cols(ds, min_cols)
        if len(cols) < 2:
            return {}
        import numpy as _np
        M = _np.column_stack([_np.asarray(ds.col(c), dtype=float)
                               for c in cols])
        d = mm.front_detail(M, [True] * len(cols))
        d["cols_en"] = [_paper.describe(c)[0] if _paper.describe(c) else c
                        for c in cols]
        # 展平成浅层键：collect 只收 depth<=2 或 key 命中的项，
        # 嵌套 list 的坐标会被漏掉（实测 3 个前沿坐标未溯源）。
        d["coords_flat"] = {
            f"c{_i}_{_j}": float(_v)
            for _i, _row in enumerate(d.get("coords") or [])
            for _j, _v in enumerate(_row)}
        return d
    except Exception:                               # noqa: BLE001
        return {}



def _is_id_like(name) -> bool:
    """是不是 ID 列（编号/序号/ID）。

    ID 列进敏感性分析或当因子，是评审一眼能看出的错：
    它对响应没有物理意义，只会让图多一条无解释的线。
    """
    t = str(name).lower()
    return any(k in t for k in ("编号", "序号", "id", "index", "no.", "_no"))


def _cond_scaled(ds, xs):
    """标准化后的条件数 —— 共线的判据。

    原始条件数把量纲差异算进去（三因子跨度 0.3/1.5/10 → 92.9），
    标准化后只剩相关性结构（实测 1.23）。用原始值说「正交」是错的。
    """
    try:
        import dataprof as _dp
        if not xs:
            return None
        return _dp.condition_numbers(ds, list(xs)).get("scaled")
    except Exception:                               # noqa: BLE001
        return None


def _front_n(ds, mins_csv) -> int | None:
    """给定 --min 的多目标列，返回帕累托前沿点数。

    评审指出「84 个样本做 Pareto 前沿会极不平滑」。
    这个数字要写进论文的局限性，不能只写"样本不足"。
    """
    if not mins_csv:
        return None
    raw = mins_csv
    if isinstance(raw, (list, tuple)):
        cols = [str(c).strip() for c in raw if str(c).strip()]
    else:
        cols = [c.strip() for c in str(raw).split(",") if c.strip()]
    cols = ds.pick(cols) if cols else []
    if len(cols) < 2:
        return None
    import numpy as np
    try:
        M = np.column_stack([ds.col(c) for c in cols])
        idx = mm.pareto_idx(M, [True] * len(cols))
        return len(idx)
    except Exception:                                   # noqa: BLE001
        return None



def _knee(ds, mins_csv: str):
    """算膝点。返回 dict 或 None。"""
    if not mins_csv:
        return None
    try:
        # 必须用 ds.pick 做模糊匹配 —— 用户传「热阻」，实际列名是
        # 「无量纲热阻」。用 c in ds.num_names 会精确匹配失败，
        # 膝点静默变成 None（其他分支都用 pick，这里漏了）。
        _raw = [c.strip() for c in mins_csv.split(",") if c.strip()]
        cols = ds.pick(_raw) if _raw else []
        if len(cols) < 2:
            return None
        import numpy as _np
        M = _np.column_stack([_np.asarray(ds.col(c), dtype=float)
                              for c in cols[:2]])
        front = mm.pareto_idx(M, [True] * 2)
        kn = mm.knee_point(M, front, [True] * 2)
        if kn is None:
            return None
        kn["cols"] = cols[:2]
        return kn
    except Exception:                               # noqa: BLE001
        return None


def _en_text(s) -> str:
    """把任何要进图的文字变成英文（最终防线）。

    三层：无 CJK 直接返回；有 CJK 但 describe 认得就用英文；
    仍认不出就整段替换成 value —— 绝不让中文进 PNG。
    逐个调用点改防不住（已经漏过三次），所以放在这里兜底。
    """
    import re as _re
    s = str(s or "")
    if not _re.search(r"[\u4e00-\u9fff]", s):
        return s
    try:
        en, ok = _paper.describe(s)
        if ok and not _re.search(r"[\u4e00-\u9fff]", en):
            return en
    except Exception:                               # noqa: BLE001
        pass
    return _re.sub(r"[\u4e00-\u9fff]+", "value", s)


def _cell(v) -> str:
    """一个单元格值 → CSV 文本。

    第 89 轮真踩到：A 题附件里 DATE 列是 datetime.datetime，
    float(datetime) 直接 TypeError，整个 merge 崩掉、
    CSV 写了一半，后面 clean 读到空表还报"成功"。
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return '"' + v.replace('"', '""') + '"'
    if isinstance(v, bool):
        return "1" if v else "0"
    try:
        fv = float(v)
        return f"{fv:.10g}"
    except (TypeError, ValueError):
        import datetime as _dt
        if isinstance(v, (_dt.datetime, _dt.date)):
            return '"' + v.isoformat() + '"'
        return '"' + str(v).replace('"', '""') + '"'


def _fig_hint(ctx, data_path="", yname="", xnames=(), mins=()):
    """没有图时给一条可直接复制执行的命令。

    冷启动实测：run --compile 会生成一篇 400 KB 的 PDF，里面一张图都没有，
    而输出里完全不提出图 —— 用户以为交稿了。图要单独跑 plot。
    """
    if ctx.get("figures"):
        return ""
    xl = data_path or "<数据文件>"
    xs = ",".join(xnames) if xnames else "<x1,x2>"
    ms = ",".join(mins) if mins else "<m1,m2>"
    return ("\n  提示：还没有图，PDF 里只有正文。生成一套（12 张）：\n"
            "    python mmkit.py plot --kind hist --data %s --y %s "
            "--x %s --min %s --out-png out/fig/hist\n"
            "  其余 kind：box corr resid qq pred sens cand tornado "
            "surfaces pareto flow（同样参数，换 --kind 与输出名）"
            % (xl, yname or "<y>", xs, ms))


_FIG_KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
              "cand", "tornado", "surfaces", "pareto", "flow")


def _auto_figs(ds, ycol, xs, min_cols, tex_path):
    """把 12 张图直接生成到 tex 同级目录的 fig/ 下。

    冷启动实测：只跑 run --compile 会得到一篇 400 KB、一张图都没有的 PDF。
    光给提示不够 —— 「直通」的意思是一条命令出完整稿，不是出稿再加 12 条命令。
    """
    import subprocess
    base = os.path.dirname(os.path.abspath(tex_path))
    figd = os.path.join(base, "fig")
    os.makedirs(figd, exist_ok=True)
    data = getattr(ds, "path", "") or ""
    # 必须用**原始列名**：plot 是按列名去读数据文件的，而
    # describe() 会把中文翻译成英文（热阻 -> thermal resistance），
    # 数据里没有那一列，于是 12 张里只有 3 张不需要列名的能出来。
    ys = str(ycol)
    xnames = ",".join(str(c) for c in xs)
    mins = ",".join(str(c) for c in (min_cols or []))
    ok = 0
    for k in _FIG_KINDS:
        out = os.path.join(figd, k)
        try:
            subprocess.run(
                [sys.executable, os.path.abspath(__file__), "plot",
                 "--kind", k, "--data", data, "--y", ys, "--x", xnames,
                 "--min", mins, "--out-png", out],
                capture_output=True, timeout=120)
        except Exception:                           # noqa: BLE001
            continue
        if os.path.exists(out + ".pdf") and os.path.getsize(out + ".pdf") > 1000:
            ok += 1
    return ok


def _collect_figures(tex_path: str) -> dict:
    """把已生成的图收进论文。

    图由 mmkit plot 产出；这里只回答"有哪些图能用"。
    缺的图不会被编造 —— 论文里自然就不出现那一节。
    """
    base = os.path.dirname(os.path.abspath(tex_path))
    cand = {}
    # 只在本题自己的目录里找图。原来还有第三个兜底
    # out/fig —— 那是仓库里默认那道题的图，结果别的题会引用
    # ../../fig/box.pdf 这种路径：图是热沉的箱线图，论文讲的是
    # 销量预测。缺图就不显示那一节，比放错图好。
    for d in (os.path.join(base, "fig"), base):
        if not os.path.isdir(d):
            continue
        for nm in sorted(os.listdir(d)):
            if not nm.lower().endswith((".png", ".pdf", ".jpg")):
                continue
            kind = os.path.splitext(nm)[0]
            if kind in cand:
                continue
            rel = os.path.relpath(os.path.join(d, nm), base)
            cand[kind] = rel.replace(os.sep, "/")
    return cand


def run(data: str, yname: str, xnames: list[str], claim_specs: list[str],
        mins: list[str], maxs: list[str], delta: float,
        reproduced: bool, as_json: bool, out_path: str = "",
        benefit: list[str] | None = None,
        cost: list[str] | None = None,
        tex_path: str = "",
        team: str = "000000",
        problem: str = "",
        mechanism: str = "auto",
        lang: str = "en",
        no_figs: bool = False,
        min_cols: str = "",
        strict: bool = False,
        compile_pdf: bool = False,
        no_gate: bool = False) -> int:
    path = data or mm.find_xlsx()
    if not path or not os.path.exists(path):
        print(f"找不到数据：{path!r}；用 --data 指定")
        return 2
    ds = mm.DS(path)
    _data_note(ds)
    ycol = ds.pick([yname])[0] if yname else None
    # 拿时间轴当目标变量是硬错误：每一步计算都对，整个模型没有意义。
    # 实测 A 题附件里 TIME 列（07:00/09:00…）会被当数值列，
    # 于是 `--y TIME` 能跑通并输出一堆"显著"的偏相关。
    if ycol is not None:
        try:
            _nr = dict(mm.non_response_cols(ds))
        except Exception:                       # noqa: BLE001
            _nr = {}
        _kind = _nr.get(ycol)
        if _kind == "time":
            print(f"  拒绝：{ycol!r} 是时间轴，不能当被解释变量。")
            print("    时间序列预测请用：mmkit.py forecast --y <指标>")
            print("    或把 --y 换成真正的目标列（某个测量值）")
            return 2
        if _kind == "id":
            # 标识列不是时间轴，措辞要分开（第 109 轮）。
            print(f"  拒绝：{ycol!r} 是行标识（编号），不能当被解释变量。")
            print("    它每行一个序号，解释它没有意义；请换成真正的测量列")
            return 2
    xs = ds.pick(xnames) if xnames else []
    rep: dict = dict(file=os.path.basename(path), sheet=ds.sheet,
                     rows=ds.n_rows, cols=ds.num_names)

    if not as_json:
        sec(f"数学建模插件 · {rep['file']}")
        print(f"  sheet={ds.sheet}  表头第 {ds.header_row + 1} 行  "
              f"{ds.n_rows} 行 × {len(ds.num_names)} 数值列")
        if ycol:
            print(f"  目标 y = {ycol}")
        if xs:
            print(f"  自变量 = {xs}")

    # ---------- 1 体检 ----------
    e = mm.eda(ds)
    rep["eda"] = dict(
        rows=e["rows"],
        per_col=[{k: v for k, v in c.items()} for c in e["per_col"]],
        id_cols=e.get("id_cols", []),
        vif_note="ID 列已排除在 VIF 之外")
    if not as_json:
        print()
        mm.print_eda(ds, e)

    # ---------- 2 评价（熵权 + TOPSIS）----------
    # 放在 y/x 检查之前：评价题只需要指标列，不需要指定自变量/因变量。
    # 第 78 轮发现这块功能在 mm.py 里、mmkit 没接 —— 而且被 y/x 检查挡在外面。
    if benefit or cost:
        ben = ds.pick(benefit) if benefit else []
        cst = ds.pick(cost) if cost else []
        if ben or cst:
            sc = mm.score(ds, ben, cst)
            top = [(int(i) + 1, float(sc["score"][i]))
                   for i in sc["order"][:10]]
            rep["score"] = dict(cols=sc["cols"],
                                weights=[float(w) for w in sc["weights"]],
                                top=[dict(row=r, score=s) for r, s in top],
                                n=ds.n_rows)
            if not as_json:
                print()
                mm.print_score(ds, sc)

    if not ycol or not xs:
        if as_json:
            _emit(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        else:
            print("\n没给 --y / --x，跳过建模段（体检与评价已做）")
        return 0

    # ---------- 2 结构竞速 ----------
    fr = mm.fit(ds, ycol, xs)
    rep["fit"] = dict(y=fr["y"], x=fr["x"],
                      cands=[{k: v for k, v in c.items() if k != "fold_rmse"}
                             for c in fr["cands"]],
                      best=(fr["best"]["label"] if fr["best"] else None),
                      best_rmse=(fr["best"]["rmse"] if fr["best"] else None),
                      cond_linear=fr["cond_linear"],
                      # 别在这里逐个挑字段 —— 每层重构 dict 就丢一次。
                      # baseline_rmse 就是这样丢的，三模型那一节一直拿不到。
                      baseline_rmse=fr.get("baseline_rmse"),
                      n=fr.get("n"),
                      leak_bad=fr.get("leak_bad") or [])
    # 自变量里混进了响应的组成部分 → 这题算出来的 R² 没有解释意义。
    # 与其让它一路走到 gate 才被拦，在建模入口就停住（--strict 时硬拒）。
    _lb = fr.get("leak_bad") or []
    if _lb:
        msg = ("自变量里有响应的组成部分：%s。"
               "删掉这些列后重跑；保留它们的系数没有解释意义。" % "、".join(_lb))
        if strict:
            print("\n[拒绝] " + msg)
            return 2
        print("\n[警告] " + msg)
    if not as_json:
        print()
        mm.print_fit(fr)

    # ---------- 3 灵敏度 ----------
    sr = mm.sens(ds, ycol, xs, delta)
    rep["sens"] = dict(kind=sr["kind"], rmse=sr["rmse"], base=sr["base"],
                       delta=sr["delta"],
                       items=[{k: v for k, v in it.items()} for it in sr["items"]])
    if not as_json:
        print()
        mm.print_sens(sr)

    # ---------- 4 方向：主张 or 提示 ----------
    X, y = ds.cols(xs), ds.col(ycol)
    parsed, bad = parse_claims(claim_specs, ds, xs)
    hints = all_partial(ds, ycol, xs)

    if parsed and not as_json:
        sec("四、你声明的主张（可被推翻）")
        for p in parsed:
            print(f"    {p['name']} 方向 {'正' if p['want'] > 0 else '负'}"
                  f"   ← {p['raw']}")
        if bad:
            print(f"    解析不了：{bad}")
    elif not as_json:
        sec("四、数据提示（**不是结论**）")
        print("    你没给 --claim，所以下面这些只是数据里看到的，")
        print("    工具不会替你把它当成主张。要验方向请加 --claim 名字:正/负")
        print()
        if hints:
            h0 = hints[0]
            print(f"    n = {h0['n']}，α=0.05 的显著临界 |r| ≈ "
                  f"{h0['r_crit']:.4f}")
            print(f"    （样本越大临界越低 —— 但「显著」不等于「重要」，"
                  f"看最后一列的解释力）")
            print()
        # 中文字符串的显示宽度和字符数不等，用 f-string 对齐会错位
        print("    自变量                     偏相关   方向    判定")
        print("    " + "-" * 66)
        for h in hints:
            pcs = "—" if h["pc"] is None else f"{h['pc']:+.4f}"
            d = {1: "正", -1: "负", 0: "—"}[h["sign"]]
            print(f"    {h['name']:<24} {pcs:>8}   {d:<4}  {h['note']}")

    # ---------- 5 多通道并行验证 ----------
    items = []
    results = []
    if parsed:
        if not as_json:
            sec("五、多通道并行验证（你声明的主张）")
        for i, p in enumerate(parsed, 1):
            # 编号按**声明顺序**，不按列索引 —— 否则用户按 K1/K2 找不着
            c = lanes.Claim(f"K{i}", f"{p['name']} 对 {ycol} 的影响方向"
                            f"为{'正' if p['want'] > 0 else '负'}",
                            X=X, y=y, sign={p["idx"]: p["want"]})
            votes, agg, v = verify_one(c)
            v["reproduced"] = reproduced
            if reproduced:
                v = lanes.to_verdict(c, agg, reproduced=True)
            results.append(dict(cid=c.cid, text=c.text, sign={p["idx"]: p["want"]},
                                grade=agg["grade"], final=v["final"], C=v["C"],
                                refuted=v["refuted"], why=v["why"],
                                vetoed=agg.get("vetoed", False),
                                votes=[dict(lane=x.lane, verdict=x.verdict,
                                            strength=round(x.strength, 3),
                                            why=x.why) for x in votes]))
            items.append((c.cid, c, v))
            if not as_json:
                print()
                print(f"  【{c.cid}】{c.text}")
                show_votes(votes)
                print("    ── 按来源汇总")
                print(lanes.fmt_aggregate(agg))
                print(f"    ── 闸门：{v['final']}  C={v['C']}"
                      + ("  〔被推翻〕" if v["refuted"] else ""))
    else:
        # 提示模式：也跑通道，但明确不许当结论
        if not as_json:
            sec("五、多通道并行验证（提示模式 —— 不许出结论）")
            print("    提示模式下不跑 direction（没声明方向），其余通道照跑。")
            print("    这些票的含义是「这个线性模型在这份数据上站不站得住」，")
            print("    不是「你的结论对不对」。")
        for i, h in enumerate(hints, 1):
            c = lanes.Claim(f"H{i}",
                            f"（提示）{h['name']} 与 {ycol} 存在可建模的关系",
                            X=X, y=y, sign={})     # 空 sign → direction 必然 UNKNOWN
            votes = lanes.run_lanes(c)
            agg = lanes.aggregate(votes)
            v = lanes.to_verdict(c, agg)
            results.append(dict(cid=c.cid, text=c.text, sign={},
                                grade=agg["grade"], final=v["final"], C=v["C"],
                                refuted=v["refuted"], why=v["why"],
                                vetoed=agg.get("vetoed", False),
                                hint=dict(pc=h["pc"], sign=h["sign"]),
                                votes=[dict(lane=x.lane, verdict=x.verdict,
                                            strength=round(x.strength, 3),
                                            why=x.why) for x in votes]))
            if not as_json:
                pc_s = "—" if h["pc"] is None else f"{h['pc']:+.3f}"
                print()
                print(f"  【{c.cid}】{h['name']}  偏相关 {pc_s}")
                show_votes(votes)
                print(f"    ── 闸门：{v['final']}  C={v['C']}（提示模式上限）")

    rep["verify"] = results

    # ---------- 6 跨主张一致性 ----------
    if items:
        conflicts = lanes.cross_check(items)
        rep["conflicts"] = conflicts
        if not as_json:
            sec("六、跨主张一致性")
            print(lanes.fmt_cross(conflicts))

    # ---------- 6.5 变换稳健性 ----------
    # 放在多目标之前：先让人知道哪些结论是脆的，再谈优化。
    # 第 84 轮加这一节的原因见 mm.robustness 的文档字符串 ——
    # 诊断出异方差之后不给稳健标准误、也不检验结论对尺度的敏感性，
    # 等于"知道有病还接着算"。
    if ycol and xs and not as_json:
        try:
            robs = mm.robustness(ds, ycol, xs)
        except (ValueError, np.linalg.LinAlgError):
            robs = None
        if robs is not None:
            # 不用 sec()：print_robustness 自己会打标题和分隔线，
            # 两个一起用会出现重复的 ==== 标题
            mm.print_robustness(robs)
            rep["robustness"] = dict(
                r2=robs["base"]["r2"], bp=robs["base"]["bp"],
                bp_crit=robs["base"]["bp_crit"],
                n_stable=robs["n_stable"], n_total=robs["n_total"],
                flips=[r["name"] for r in robs["rows"] if not r["stable"]],
                warn=robs["warn"])

    # ---------- 7 多目标 ----------
    if mins or maxs:
        mn = ds.pick(mins) if mins else []
        mx = ds.pick(maxs) if maxs else []
        if len(mn) + len(mx) >= 2:
            orr = mm.opt(ds, mn + mx, [True] * len(mn) + [False] * len(mx))
            top = sorted(orr["uniq"].items(), key=lambda kv: -len(kv[1]))
            rep["opt"] = dict(cols=orr["cols"], front=len(orr["front"]),
                              n_rows=len(orr["M"]), n_picks=orr["n_picks"],
                              n_solutions=len(orr["uniq"]),
                              most_stable=(top[0][0] + 1 if top else None),
                              stable_share=(len(top[0][1]) / orr["n_picks"]
                                            if top else 0.0))
            if not as_json:
                print()
                mm.print_opt(ds, orr)
    # ---------- 8 论文怎么写 ----------
    if not as_json:
        sec("八、这张表对应论文怎么写")
        print(f"  {'编号':<6}{'结论':<40}{'判决':<10}{'能怎么写'}")
        print(f"  {THIN[:80]}")
        for r in results:
            if r.get("vetoed"):
                style = "被方向通道否决，改结论"
            elif r["refuted"]:
                style = "被数据推翻，改写法"
            elif r["final"] == "pass":
                style = "可断言"
            elif r["final"] == "degrade":
                style = "写进'局限'段"
            else:
                style = "证据不足，先补"
            if not r["sign"]:
                style = "提示，不是结论" if r["final"] != "reject" else style
            print(f"  {r['cid']:<6}{r['text'][:38]:<40}{r['final']:<10}{style}")
        print()
        print("  三条线：")
        print("    pass      → 进结论段")
        print("    degrade   → 进「局限与展望」段，写成本文条件下成立")
        print("    reject    → 不许写；要么改结论，要么改主张")

    # ---------- 9 诚实边界 ----------
    if not as_json:
        sec("九、这份报告管到哪")
        print("  能管：")
        print("    · 结构竞速、方向验证、多目标前沿、灵敏度、跨主张一致性")
        print("    · 每一条都给了通道级证据（谁支持、谁反对、谁不知道）")
        print()
        print("  不管：")
        print("    · 目标该有哪几个 —— 题意")
        print("    · 权重取多少 —— 工具只给稳定区间，取点是立场")
        print("    · 模型创新 —— 工具验已有的，不发明新的")
        print()
        print(f"  e3（可复现）={'2 已声明重跑' if reproduced else '1 未重跑'}")
        if reproduced:
            print("  → 可以判 pass。注意这个 2 是你声明的，工具没法替你验证；")
            print("    写进论文时要把「怎么重跑的」一并交代。")
        else:
            print("  → 最高只能是 degrade。这不是缺陷，是闸门在守一句实话："
                  "单份数据的内部一致性撑不起「可复现」。")

    rep["reproduced"] = reproduced
    if out_path:
        md = to_markdown(rep)
        try:
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(md)
            if not as_json:
                print()
                print(f"  报告已写入 {out_path}（{len(md)} 字符，"
                      f"{md.count(chr(10))} 行）")
        except OSError as e:
            print(f"  写报告失败：{e}")

    # ---------- 10 生成 LaTeX 论文 ----------
    # 把这一路算出来的东西翻译成论文里的话。拿不到的写 [TODO]，不编号。
    if tex_path:
        # 没有图就先自己出图 —— 一条命令出完整稿。
        _figs_pre = _collect_figures(tex_path)
        if (not _figs_pre) and tex_path and not no_figs:
            _n = _auto_figs(ds, ycol, xs, min_cols, tex_path)
            if _n:
                _figs_pre = _collect_figures(tex_path)
                print(f'  图：自动生成 {_n} 张 -> '
                      f'{os.path.dirname(os.path.abspath(tex_path))}'
                      f'{os.sep}fig')
        ctx = dict(
            title=f"Modelling Report: {_paper.describe(ycol)[0]}",
            pareto_front_n=_front_n(ds, min_cols),
    knee=_knee(ds, min_cols),
            # 问题 4：权重敏感性与鲁棒设计（原来完全缺失）
            q4=_q4_ctx(ds, min_cols, ycol, xs),
            # 三指标分别建模（题目问题 2 的代理模型）
            multimodel=_multimodel_ctx(ds, min_cols, ycol, xs),
            # 机理预测符号 vs 观测符号（题目问题 1 的检验）
            signs=_signs_ctx(ds, min_cols, xs),
            q5=_q5_ctx(ds, min_cols, xs,
                       _q4_ctx(ds, min_cols, ycol, xs)),
            lang=lang,
            team=team,
            problem=(problem or f"the modelling of {ycol} from the measured "
                                f"factors"),
            y=ycol, x=list(xs),
            n_rows=ds.n_rows, n_cols=len(ds.num_names),
            eda=rep.get("eda") or {},
            fit=rep.get("fit") or {},
            # 标准化后的条件数 —— 共线的判据。原始值是量纲产物
            # （三因子跨度 0.3/1.5/10 → 92.9），标准化后才是真的结构。
            cond_scaled=_cond_scaled(ds, list(xs)),
            cond_raw=_cond_raw(ds, list(xs)),
            spans=_spans(ds, list(xs)),
            # 适用区间必须**在这里**算（第 96 轮踩过）：
            # 原来只在后面冻结那一块算，而那时论文已经写完 ——
            # 于是 rep["applicability"] 有值、正文里却没有这一节。
            # 生成用的 ctx 与冻结用的 rep 是两条路，数字要先算，两边都拿得到。
            applicability=mm.applicability(ds, list(xs), ycol),
            pred_int=_pi_ctx(ds, min_cols, xs),
            problem_kind=_kind_ctx(problem, ds, xs, ycol,
                                            n_obj=len(min_cols or [])),
            cases=_cases_ctx(_kind_ctx(problem, ds, xs, ycol),
                             ds, problem),
            mechanism_mode=str(mechanism or "auto"),
            diag=_diag_ctx(ds, min_cols, xs),
            front_detail=_front_ctx(ds, min_cols),
            # 报告层可能裁字段，这里显式带一份 —— 三模型那一节要用它
            baseline_rmse=(rep.get("fit") or {}).get("baseline_rmse"),
            robustness=rep.get("robustness") or {},
            optimize=rep.get("opt") or {},
            sensitivity=rep.get("sens") or {},
            figures=_figs_pre,
            commands=[f"python mmkit.py run --data DATASET.xlsx"
                      f" --y \"{_paper.describe(ycol)[0]}\""
                      f" --x \"{','.join('x' + str(i + 1) for i in range(len(xs)))}\"",
                      "python mmkit.py plot --kind bar --cost <indicators>",
                      "python mmkit.py plot --kind pareto --min <objectives>"],
        )
        # ── 主动证伪：每条「X 与 y 同向」的主张，局部站不站得住 ──
        # falsify.counterexamples 会滑窗找区间内符号相反的反例；
        # 论文据此决定这条结论该写成结论还是写成局限。
        # 原来 paper.py 完全不知道 falsify（0 次引用），
        # 于是 gate 报「3 组边际反例仍矛盾」，论文照旧把它写成结论。
        _fal = {}
        try:
            import falsify as _fl
            _yv = ds.col(ycol)
            for _x in xs:
                try:
                    _xv = ds.col(_x)
                    _a = np.asarray(_xv, dtype=float)
                    _b = np.asarray(_yv, dtype=float)
                    _m2 = ~(np.isnan(_a) | np.isnan(_b))
                    _rho = (float(np.corrcoef(_a[_m2], _b[_m2])[0, 1])
                            if _m2.sum() > 2 else 0.0)
                    _sg = 1 if (_rho or 0) >= 0 else -1
                    _r = _fl.counterexamples(_xv, _yv, sign=_sg)
                    _fal[_x] = dict(
                        ok=bool(_r.get("ok")),
                        n=int(_r.get("n") or 0),
                        n_violating=int(_r.get("n_violating") or 0),
                        sign=_sg,
                        segs=[(round(s2.get("start"), 2),
                               round(s2.get("end"), 2),
                               round(s2.get("rho"), 3))
                              for s2 in (_r.get("segments") or [])[:3]])
                except Exception:                   # noqa: BLE001
                    continue
        except Exception:                           # noqa: BLE001
            _fal = {}
        ctx["falsify"] = _fal

        # LLM 写的正文：按「原文前 40 字」注入；没有就回落到模板文本。
        # 不设时行为完全不变 —— 22 道题的回归因此不受影响。
        # 注意：run() 里没有 argparse 的 a（那是 main() 的局部变量），
        # 所以只读环境变量。实测在这里写 getattr(a, ...) 会 NameError。
        _ov_path = os.environ.get("MMKIT_OVERRIDES", "")
        if _ov_path and os.path.exists(_ov_path):
            try:
                _ov = json.load(open(_ov_path, encoding="utf-8"))
            except Exception:                       # noqa: BLE001
                _ov = {}
            _paper.set_overrides(_ov)
            _say(f"  正文覆盖 {len(_ov)} 段 <- {_ov_path}")
        else:
            _paper.set_overrides(None)

        tex = _paper.build(ctx)

        # skeleton 模式：只导骨架，不出稿。
        # 必须放在 build 之后 —— 段落是在 build 里生成的。
        if globals().get("_SKELETON_ONLY"):
            _sk = [(k, t) for k, t in _paper.dump_skeleton()
                   if k and not k.startswith("__")]
            _say(f"  可替换的正文段落：{len(_sk)} 段")
            for k, t in _sk:
                _say(f"\n  [{k}]")
                _say(f"    {t[:150]}")
            return 0
        # 最后一道总闸：任何残留中文都替成中性词。
        # 中文列名会从十几条路径漏进 tex（题面/notation/符号稳健/案例/
        # 表格头…），逐个堵不可靠 —— 实测漏一处就是 23 个
        # "Unicode character" 编译错误。放在这里是因为所有出稿路径
        # 都经过这一行，比在各个 return 点分别兜底稳。
        # 这道总闸只对英文模式成立。
        # 之前它无条件生效，结果 --lang zh 的章节标题刚被 _localize
        # 换成中文，下一行就被替成 variable —— 多语言功能被自己
        # 加的安全网闷死了，产出的是「英文论文 + 两个 variable 标题」。
        _lang_now = str(ctx.get("lang") or "en").lower()
        if _lang_now.startswith("en"):
            if _re_cjk.search(tex):
                tex = _re_cjk.sub("variable", tex)
            # 全角标点也必须换掉：把中文列名「针肋宽度比（m）」替成
            # variable 之后，括号还是全角 U+FF08 —— pdfLaTeX 直接报
            # "Unicode character （ not set up"（实测 4 处错误）。
            for _a, _b in (("（", "("), ("）", ")"), ("，", ", "),
                           ("：", ": "), ("；", "; "), ("、", ", "),
                           ("～", "~"), ("－", "-"), ("　", " ")):
                if _a in tex:
                    tex = tex.replace(_a, _b)
        else:
            # 非英文：中文是预期的，不许替。但要用中文排版就得有
            # ctex/xeCJK，缺了会编出一堆问号 —— 说清楚，别静默。
            try:
                _need = list(_i18n.LANGS.get(_lang_now[:2], {})
                              .get("needs") or [])
            except Exception:
                _need = []
            if _need:
                print(f"  ⚠ 语言 {_lang_now} 需要宏包 "
                      f"{', '.join(_need)}；本机 MiKTeX 若未安装，"
                      f"中文会排成问号。")

        info = _paper.lint(tex)

        # ── 数字冻结（P17）：出稿时自动冻结整份 rep ──
        # 只冻 mm.fit 是不够的：论文里还有 EDA 的均值/标准差、因子的
        # 取值水平、稳健性统计量。实测 44 个数里 20 个找不到出处，
        # 缺的全是这些。所以这里冻的是完整的 rep，不是某一个子字典。
        try:
            import freeze as _freeze
            # 问题 4/5 与三指标模型的数字也要冻。它们在 ctx 里现算，
            # 不在 rep 里，所以 0.283 / 0.391 / 8.1% 这些数在冻结表里
            # 找不到出处（实测 58 个数 11 个未溯源，全是这一类）。
            try:
                rep["q4"] = _q4_ctx(ds, min_cols, ycol, xs)
                # 因子的跨度也是论文里引用的数（量纲差异的来源），
                # 算得出但不在 rep 里，冻进去才可溯源。
                rep["spans"] = _spans(ds, list(xs))
                # 适用区间：论文要写，gate 要查（第 96 轮）
                rep["applicability"] = mm.applicability(ds, list(xs), ycol)
                # 预测区间的数字同样要冻，否则论文里新加的
                # 0.014935 / 4.0% 会立刻变成「找不到出处」。
                rep["pred_int"] = _pi_ctx(ds, min_cols, xs)
                # 残差诊断与前沿计算过程里的数也要冻
                rep["diag"] = _diag_ctx(ds, min_cols, xs)
                rep["front_detail"] = _front_ctx(ds, min_cols)
                # 前沿坐标要放顶层：collect 只收 depth<=2 的项，
                # 嵌在 front_detail 里就够不到（实测 3 个坐标未溯源）。
                rep["front_coords"] = (
                    (rep.get("front_detail") or {}).get("coords_flat")
                    or {})
                rep["multimodel"] = _multimodel_ctx(ds, min_cols, ycol, xs)
                rep["q5"] = _q5_ctx(ds, min_cols, xs,
                                  rep.get("q4") or {})
                # ── E（第 122 轮）：ctx 与 rep 是两本账，这里把它对齐 ──
                # paper.py 从 **ctx** 取数印进正文，冻结表却只从 **rep**
                # 取数。两本账没对齐的每一处，就是一个「印了但无法归属」
                # 的数。实测 5 篇模板卷 152 个未溯源里 43 个是这一类：
                #   · cond_scaled / cond_raw —— 正文「condition number 26.29」
                #     写的是它们，而 rep 里只有 fit.cond_linear（另一个量）
                #   · falsify.segs —— 正文「the clearest violation is
                #     x in [246.51, 459.2] with local correlation -0.191」
                #   · q5.tradeoff —— 正文「moving it from 2.38 to 5.95e+05」
                #
                # 登记原则：**paper.py 印什么，就把 ctx 里那一份原样冻进去**，
                # 不重算（重算可能与正文那时的取值不同，那就又对不上了）。
                # 摊平成 depth<=2 的键：collect 只对 depth<=2 或命中
                # KEY_HINTS 的值收录，嵌套了就拿不到。
                _cnd = dict(scaled=ctx.get("cond_scaled"),
                            raw=ctx.get("cond_raw"))
                rep["cond"] = {k: v for k, v in _cnd.items()
                               if isinstance(v, (int, float))
                               and not isinstance(v, bool)}
                _tr = ((ctx.get("q5") or {}).get("tradeoff") or {})
                if _tr:
                    _flat = {}
                    for _k in ("frm", "to", "shift"):
                        if isinstance(_tr.get(_k), (int, float)):
                            _flat[_k] = float(_tr[_k])
                    if _flat:
                        rep["q5_tradeoff"] = _flat
                _fs = {}
                for _nm, _v in (ctx.get("falsify") or {}).items():
                    if not isinstance(_v, dict):
                        continue
                    for _i, _sg in enumerate((_v.get("segs") or [])[:3]):
                        if not isinstance(_sg, (list, tuple)) or len(_sg) < 3:
                            continue
                        _fs[f"{_nm}_seg{_i}_lo"] = _sg[0]
                        _fs[f"{_nm}_seg{_i}_hi"] = _sg[1]
                        _fs[f"{_nm}_seg{_i}_rho"] = _sg[2]
                if _fs:
                    rep["falsify"] = _fs
                # 适用区间里「直线在多远处穿过零点」也要冻：正文会印
                # 「the same straight line reaches zero at x = 58.2481」，
                # 而那个数在 applicability[i].cross_at（depth 3），
                # collect 够不到 —— 实测 icm2006c 就卡在这一个数上，
                # 而且它的书写精度是 4 位小数，交稿目录的单点严判会判死。
                #
                # 注意 mm.applicability 返回的是 **list**（每个因子一项），
                # 不是 dict。第一版在这里写成 .get("absurd") 直接
                # AttributeError，被外层 except 静默吞掉 —— 两处登记都没执行，
                # 而 gate 照样显示「通过」，只是 numbers 还差那几个数。
                # 所以这段自己 try，失败时打印，不连累同块的其他登记。
                try:
                    _app = ctx.get("applicability") or []
                    if isinstance(_app, dict):
                        _app = list(_app.values())
                    for _ai, _aa in enumerate(list(_app)[:6]):
                        if not isinstance(_aa, dict):
                            continue
                        for _ak in ("cross_at", "lo", "hi", "slope"):
                            _av = _aa.get(_ak)
                            if isinstance(_av, (int, float)) \
                                    and not isinstance(_av, bool):
                                rep[f"appl{_ai}_{_ak}"] = float(_av)
                except Exception as _ae:            # noqa: BLE001
                    print(f"  ⚠ 冻结 applicability 失败：{_ae}")
                # 「最简结构反而最好」那段印的 gap 是**两个 rmse 之比**，
                # 不是任何一个已有的 rmse，所以 collect 抓不到
                # （实测 nflis 剩的就是它：205.5 percent worse out of sample）。
                # 这里按 paper._explain_model_choice 的同一算法算一次并登记，
                # 保证正文印的值与冻结值是同一个数。
                try:
                    _cs = [c for c in
                           ((rep.get("fit") or {}).get("cands") or [])
                           if isinstance(c, dict) and c.get("rmse") is not None]
                    if len(_cs) >= 2:
                        _bs = min(_cs, key=lambda c: c["rmse"])
                        _wr = [c for c in _cs if c is not _bs
                               and c["rmse"] > _bs["rmse"]]
                        if _wr:
                            rep["model_gap_pct"] = float(
                                (_wr[0]["rmse"] / _bs["rmse"] - 1.0) * 100.0)
                except Exception as _ge:            # noqa: BLE001
                    print(f"  ⚠ 冻结 model_gap 失败：{_ge}")
            except Exception:                       # noqa: BLE001
                pass
            _fz = _freeze.freeze(rep, os.path.basename(path or "") + " · run",
                                 y=ycol, x=list(xs))
            _fd = os.path.dirname(os.path.abspath(tex_path))
            # 冻结在写 tex 之前跑，此时目录可能还不存在 —— 不建就静默失败
            if _fd:
                os.makedirs(_fd, exist_ok=True)
            # 题型识别结果落盘，gate 读它做「必做项」检查
            _kp = os.path.join(_fd, "题型.json")
            try:
                import json as _kj
                _kj.dump(_kind_ctx(problem, ds, xs, ycol),
                        open(_kp, "w", encoding="utf-8",
                             newline="\n"),
                        ensure_ascii=False, indent=2)
            except Exception:               # noqa: BLE001
                pass
            _fp = os.path.join(_fd, "冻结数字.json")
            with open(_fp, "w", encoding="utf-8", newline="\n") as _fh:
                json.dump(_fz, _fh, ensure_ascii=False, indent=2)
            rep["frozen"] = dict(path=_fp, n=_fz["n"])
            if not as_json:
                print(f"  数字冻结 {_fz['n']} 项 → {_fp}")
        except Exception as _e:                     # noqa: BLE001
            rep["frozen"] = dict(error=f"{type(_e).__name__}: {_e}")

        # ── 竞赛规则检查（P02）：出稿前必须过 ──
        # 不接进流程的话，rules.py 只是个摆设 —— 换个用法就漏。
        # 默认只警告（探索阶段可能故意不完整）；--strict 时拒绝出稿。
        _rr = None
        try:
            import rules as _rules
            _rr = _rules.check(tex)
            rep["rules"] = dict(ok=_rr["ok"], passed=_rr["passed"],
                                total=_rr["total"],
                                failed=[x["id"] for x in _rr["results"]
                                        if not x["ok"]],
                                manual=[m[0] for m in _rr["manual"]])
        except Exception as _e:                     # noqa: BLE001
            _rr = None
            rep["rules"] = dict(ok=None, why=f"{type(_e).__name__}: {_e}")
        if _rr is not None and not _rr["ok"]:
            _bad = [x for x in _rr["results"] if not x["ok"]]
            if not as_json:
                print()
                print(f"  竞赛规则未通过（{_rr['passed']}/{_rr['total']}）：")
                for _x in _bad:
                    print(f"    ✗ {_x['id']} {_x['name']}")
                    print(f"       {str(_x['detail'])[:76]}")
            if strict:
                print("  --strict：拒绝出稿（先修完上面几条）")
                return 2
        try:
            d = os.path.dirname(os.path.abspath(tex_path))
            if d:
                os.makedirs(d, exist_ok=True)
            with open(tex_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(tex)
            if not as_json:
                print()
                print("=" * 84)
                print(f"LaTeX 论文已写入 {tex_path}")
                print(f"  {info['lines']} 行 / {info['chars']} 字符 / "
                      f"{info['n_env']} 个环境")
                if info["ok"]:
                    print("  结构自检：全部通过"
                          + (f"（{info['n_todo']} 处待补）"
                             if info["n_todo"] else ""))
                else:
                    print("  ✗ 结构自检发现问题：")
                    for p in info["problems"]:
                        print(f"      · {p}")
                if _rr is not None:
                    _mark = "✓" if _rr["ok"] else "✗"
                    print(f"  竞赛规则：{_mark} "
                          f"{_rr['passed']}/{_rr['total']} 通过"
                          + ("" if _rr["ok"] else "（见上）"))
                    for _m in (_rr.get("manual") or []):
                        print(f"     [人工] {_m[0]} {_m[1]}")
                print("  编译：默认不编译（加 --compile 会就地编译）")
        except OSError as e:
            print(f"  写 LaTeX 失败：{e}")

        # ── 编译（可选）──
        _figdir = os.path.dirname(os.path.abspath(tex_path))
        if compile_pdf:
            import shutil as _sh
            import subprocess as _sp
            # 引擎按语言选：i18n 里每种语言自己声明了 engine。
            # 原来硬编码 pdflatex，于是 --lang zh 的中文标题在
            # pdflatex 下全变成 "Unicode character" 错误（43 个）——
            # pdflatex 根本不认 Unicode，中文必须走 xelatex。
            _engine = "pdflatex"
            try:
                _engine = _i18n.engine(ctx.get("lang") or "en")
            except Exception:
                _engine = "pdflatex"
            if _sh.which(_engine):
                _ok = False
                for _ in range(2):      # 两遍，交叉引用才稳
                    _p = _sp.run(
                        [_engine, "--enable-installer",
                         "-interaction=nonstopmode", "paper.tex"],
                        cwd=_figdir, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
                    _ok = _p.returncode == 0
                if not as_json:
                    print(f"  编译 {'成功' if _ok else '有错误'}："
                          f"{os.path.join(_figdir, 'paper.pdf')}")
                rep["compiled"] = _ok
            elif not as_json:
                print("  没找到 pdflatex，跳过编译")

        # ── 全量质量门（P22）──
        # 9 项：compile / pdf / code / numbers / rules / abstract
        #      + ai_taste / figures / falsify
        # 不接进流程的话，gate.py 和 rules.py 一样只是摆设。
        if not no_gate:
            try:
                import gate as _gate
                # 必须把 data 传下去：leakage 检查要读当前这份数据。
                # 不传就回退 mm.find_xlsx()，会读到别的题的表 —— 实测
                # 表现为「没有数值列 '销量'」的 KeyError，leakage 恒为 N/A。
                _g = _gate.run_all(_figdir, data=data or "")
                rep["gate"] = dict(ok=_g["all_pass"],
                                   hard_fail=_g["hard_fail"],
                                   warns=_g["warns"], na=_g["na"])
                if not as_json:
                    print()
                    print(f"  质量门："
                          f"{'通过' if _g['all_pass'] else '未通过'}"
                          f"（硬门失败 {len(_g['hard_fail'])}，"
                          f"警告 {len(_g['warns'])}，"
                          f"未适用 {len(_g['na'])}）")
                    _mk = {"PASS": "OK  ", "FAIL": "FAIL",
                           "WARN": "WARN", "N/A": "-   "}
                    for _c in _g["checks"]:
                        _t = "硬" if _c["tier"] == "hard" else "软"
                        print(f"    [{_mk[_c['status']]}] {_t} "
                              f"{_c['id']:<9}{_c['detail'][:60]}")
                # ── 记一轮评审账本（P23）──
                # 单次打分看不出趋势；账本的价值在跨稿比较。
                try:
                    import review as _review
                    _rp = _review.run_round(_figdir, gate_result=_g)
                    rep["review"] = dict(round=_rp.get("round"),
                                         new=_rp.get("new"),
                                         dup=_rp.get("dup"),
                                         blocking=_rp.get("blocking"),
                                         score=_rp.get("score"),
                                         converged=_rp.get("converged"),
                                         reason=_rp.get("reason"))
                    if not as_json:
                        print(f"  评审账本：第 {_rp.get('round')} 轮，"
                              f"分数 {_rp.get('score')}，"
                              f"新增 {_rp.get('new')}"
                              f"（重复 {_rp.get('dup')}），"
                              f"阻断 {_rp.get('blocking')}")
                        if _rp.get("converged"):
                            print(f"    收敛：{_rp.get('reason')}")
                    # 冷启动实测：出稿成功但一张图都没有，而输出里不提。
                    # 给一条能直接复制的命令。注意缩进 —— 它不属于
                    # 「收敛」分支，否则没收敛时就不提示了。
                    # run 的参数名是 data，不是 data_path。
                    # 写错名字会抛 NameError，然后被外面那层
                    # try/except 吞掉 —— 提示静默消失，很难查。
                    _fh = _fig_hint(ctx, data, yname,
                                    xnames, mins)
                    if _fh:
                        print(_fh)
                except Exception as _e:             # noqa: BLE001
                    rep["review"] = dict(error=f"{type(_e).__name__}: {_e}")

                if strict and not _g["all_pass"]:
                    print("  --strict：质量门未通过，拒绝出稿")
                    return 2
            except Exception as _e:                 # noqa: BLE001
                rep["gate"] = dict(error=f"{type(_e).__name__}: {_e}")
                if not as_json:
                    print(f"  质量门跳过：{type(_e).__name__}: {_e}")

    if as_json:
        _emit(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    return 0


# ══════════════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════════════
def _raises(fn) -> bool:
    """跑 fn，抛异常返回 True。用来断言「该报错的地方确实报错」。"""
    try:
        fn()
        return False
    except Exception:
        return True


def selftest() -> int:
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    n_ok = n_bad = 0

    def ck(name, cond, detail=""):
        nonlocal n_ok, n_bad
        if cond:
            n_ok += 1
            print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
        else:
            n_bad += 1
            print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))

    print(BAR)
    print("mmkit.py 自检")
    print(BAR)

    # ---------- 偏相关 ----------
    print("\n一、偏相关")
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.uniform(0, 1, n)
    x2 = x1 * 0.9 + rng.normal(0, 0.05, n)      # 与 x1 高度共线
    y = 2 * x1 - 3 * x2 + rng.normal(0, 0.1, n)
    X = np.column_stack([x1, x2])
    p0 = partial_corr(X, y, 0)
    p1 = partial_corr(X, y, 1)
    ck("x1 偏相关为正", p0 is not None and p0 > 0, f"{p0:+.3f}")
    ck("x2 偏相关为负", p1 is not None and p1 < 0, f"{p1:+.3f}")
    # 简单相关会给出相反印象（辛普森入口）
    simple1 = float(np.corrcoef(x1, y)[0, 1])
    ck("简单相关与偏相关不同（共线时）",
       (simple1 > 0) != (p0 > 0) or abs(simple1 - p0) > 0.3,
       f"simple={simple1:+.3f} partial={p0:+.3f}")

    # ---------- 主张解析 ----------
    print("\n二、主张解析")
    fake = type("D", (), {"pick": staticmethod(lambda names: list(names))})()
    xs = ["针肋宽度比", "歧管深高比", "针肋排数"]
    got, bad = parse_claims(["深高:负", "宽度:正"], fake, xs)
    ck("解析出两条", len(got) == 2, str([g["name"] for g in got]))
    ck("深高匹配到第 2 列", got[0]["idx"] == 1 and got[0]["want"] == -1,
       str(got[0]))
    ck("宽度匹配到第 1 列", got[1]["idx"] == 0 and got[1]["want"] == 1,
       str(got[1]))
    ck("没有解析失败项", bad == [], str(bad))
    _, bad2 = parse_claims(["深高"], fake, xs)
    ck("没写方向要报错", len(bad2) == 1, str(bad2))
    _, bad3 = parse_claims(["不存在:正"], fake, xs)
    ck("列名匹配不到要报错", len(bad3) == 1, str(bad3))
    _, bad4 = parse_claims(["深高:乱七八糟"], fake, xs)
    ck("方向词认不出要报错", len(bad4) == 1, str(bad4))
    got5, _ = parse_claims(["排数=减"], fake, xs)
    ck("支持 = 分隔符", len(got5) == 1 and got5[0]["want"] == -1, str(got5))

    # ---------- 真数据全链路 ----------
    print("\n三、真数据全链路")
    Xa, ya, _ = lanes.load_apmcm()
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        ycol = ds.pick(["热阻"])[0]
        xsd = ds.pick(["宽度", "深高", "排数"])
        ck("真数据列匹配", len(xsd) == 3, str(xsd))

        fl = all_partial(ds, ycol, xsd)
        ck("三个偏相关都算出来了",
           all(h["pc"] is not None for h in fl),
           str([f"{h['pc']:+.3f}" for h in fl]))
        # 深高对热阻：真题里是正的（和"深高↑热阻↓"相反）
        ck("深高对热阻偏相关为正（真题事实）",
           fl[1]["pc"] > 0, f"{fl[1]['pc']:+.3f}")

        # 声明"深高↑热阻↓" → 应被推翻
        c = lanes.Claim("T1", "深高对热阻方向为负", X=Xa, y=ya, sign={1: -1})
        _, agg, v = verify_one(c)
        ck("反方向主张被否决", agg["vetoed"] is True, agg["why"][:50])
        ck("反方向主张判 reject", v["final"] == "reject", v["final"])
        # 声明"深高↑热阻↑" → 方向对
        c2 = lanes.Claim("T2", "深高对热阻方向为正", X=Xa, y=ya, sign={1: +1})
        _, agg2, v2 = verify_one(c2)
        ck("正方向主张不被否决", agg2["vetoed"] is False, v2["final"])
    else:
        ck("真数据可用（没附件则跳过）", True, "跳过")

    # ---------- 提示 ≠ 结论 ----------
    print("\n四、提示模式不许出结论")
    if Xa is not None:
        c = lanes.Claim("H1", "（提示）有可建模关系", X=Xa, y=ya, sign={})
        votes, agg, v = verify_one(c)
        d = {x.lane: x for x in votes}["direction"]
        ck("空 sign 时 direction 必然 UNKNOWN",
           d.verdict == "unknown", d.why)
        ck("提示模式拿不到 reject", v["final"] != "reject", v["final"])

    # ---------- 离散 vs 连续 ----------
    print("\n五、离散设计要走组合搜索，不走连续优化")
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        xs = ds.pick(["宽度", "深高", "排数"])
        objc = ds.pick(["压降"])[0]
        cons = ["热阻<=0.74", "温度<=0.79"]
        rd = solve_opt(ds, xs, objc, cons)
        ck("全离散数据被路由到 discrete",
           rd.get("mode") == "discrete", rd.get("mode"))
        ck("组合数算对（5×4×6=120）",
           rd.get("n_combos") == 120, rd.get("n_combos"))
        bo = rd.get("best_observed")
        ck("给出观测最优", bo is not None, str(bo)[:60])
        if bo:
            ck("观测最优是第 62 行", bo["row"] == 62, f"第 {bo['row']} 行")
            ck("解全是离散档位里的值",
               all(v in [float(t) for t in ds.col(nm)]
                   for nm, v in zip(xs, bo["x"])),
               str(bo["x"]))
        # 预测最优如果存在，必须和观测区分开
        bp = rd.get("best_predicted")
        ck("预测最优单独标注（有则必须 kind=predicted）",
           bp is None or bp["kind"] == "predicted",
           str(bp)[:60] if bp else "没有预测候选")

        # 连续路径：造一份连续数据验证它仍可用
        rng2 = np.random.default_rng(1)
        Xc = rng2.uniform(0, 1, (120, 2))
        yc = Xc[:, 0] * 2 + Xc[:, 1] * -1 + rng2.normal(0, 0.02, 120)
        import types
        fake = types.SimpleNamespace(
            cols=lambda names: Xc, col=lambda nm: yc,
            num_names=["a", "b", "y"], n_rows=120, pick=lambda ns: ns)
        rc = solve_opt(fake, ["a", "b"], "y", [])
        ck("全连续数据不走 discrete",
           rc.get("mode") != "discrete", rc.get("mode"))

    print("\n六、约束解析与容差")
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        c1, why1 = parse_constraint("热阻<=0.74", ds)
        ck("约束解析成功", c1 is not None and c1["op"] == "<=", why1 or str(c1))
        ck("约束列匹配到全名",
           c1 and c1["col"] == "无量纲热阻", c1["col"] if c1 else "")
        _, why2 = parse_constraint("热阻~0.74", ds)
        ck("怪符号要报错", bool(why2), why2)
        _, why3 = parse_constraint("不存在<=1", ds)
        ck("未知列要报错", bool(why3), why3[:60])

    print("\n七、机理：ODE 与量纲分析")
    # ODE：指数增长有解析解 y=e^{kt}
    ro = ode_solve("0.7*y", [1.0], 0.0, 5.0)
    # 容差按相对误差：rk45 的 rtol=1e-7，末值 33 量级 → 允许 1e-5 相对误差
    ck("ODE 指数增长与解析解一致",
       abs(ro["y_end"] - math.exp(3.5)) / math.exp(3.5) < 1e-5,
       f"y(5)={ro['y_end']:.6f} vs e^3.5={math.exp(3.5):.6f}，"
       f"相对误差 {abs(ro['y_end'] - math.exp(3.5)) / math.exp(3.5):.1e}")
    ck("ODE 自适应步长步数少", ro["stats"]["steps"] < 100,
       f"{ro['stats']['steps']} 步")
    ro2 = ode_solve("sin(t)", [0.0], 0.0, math.pi)
    ck("ODE 三角函数可用",
       abs(ro2["y_end"] - 2.0) < 1e-6, f"∫sin={ro2['y_end']:.6f}")

    # 安全表达式：必须挡住任意代码执行
    for bad in ("__import__('os').system('echo x')",
                "open('mmkit.py').read()",
                "y[0]",
                "(lambda: 1)()",
                "exec('x=1')",
                "unknown_name"):
        blocked = False
        try:
            safe_expr(bad)
        except (ValueError, SyntaxError):
            blocked = True
        ck(f"拒绝危险表达式 {bad[:26]}", blocked)
    for good in ("sin(t)", "exp(-t)*y", "t if t > 1 else 0", "pi*2",
                 "max(y, 0)"):
        passed = True
        try:
            safe_expr(good)
        except Exception:
            passed = False
        ck(f"放行合法表达式 {good}", passed)

    # 量纲：单摆
    rd = dimension_analysis([("周期", "T"), ("长度", "L"),
                             ("重力", "L*T^-2"), ("质量", "M")])
    ck("单摆 n=4 rank=3 → 1 个 Pi", rd["n_pi"] == 1,
       f"rank={rd['rank']} n_pi={rd['n_pi']}")
    if rd["pis"]:
        p = rd["pis"][0]
        A = np.array([[0, 1, 1, 0], [0, 0, 0, 1], [1, 0, -2, 0]], float)
        ck("Pi 确实无量纲", np.allclose(A @ p, 0, atol=1e-8),
           f"A·p={np.round(A @ p, 10)}")
        ck("Pi 里质量指数为 0（周期与质量无关）",
           abs(p[3]) < 1e-8, f"{p[3]:.2e}")
    _, dd = parse_dims("L*T^-2")
    ck("量纲串解析正确", dd == {"L": 1.0, "T": -2.0}, str(dd))
    ck("空量纲要报错", _raises(lambda: parse_dims("")), "空串")

    print("\n八、预测（时间序列）")
    # 8a 真数据是横截面 → 必须自己指出「不能用」
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        yc = ds.pick(["热阻"])[0]
        rf = forecast(ds, yc, horizon=5)
        ck("横截面数据被判 questionable",
           rf.get("questionable") is True, str(rf.get("warn"))[:80])
        ck("指出样本编号不是时间",
           any("编号" in w for w in rf.get("warn", [])),
           str(rf.get("warn")))
        ck("给出朴素法基线",
           any("朴素" in c["name"] for c in rf["cands"]), "对照组不能缺")

    # 8b 造一份真时间序列：线性 + 噪声，看能不能学到趋势
    import types as _t
    rng3 = np.random.default_rng(11)
    tt = np.arange(60, dtype=float)
    yy = 3.0 + 0.5 * tt + rng3.normal(0, 0.3, 60)
    fake_ts = _t.SimpleNamespace(
        col=lambda nm: (tt if nm == "t" else yy),
        num_names=["t", "v"], n_rows=60, pick=lambda ns: ns,
        cols=lambda ns: np.column_stack([tt, yy]) if ns else np.zeros((60, 0)))
    rf2 = forecast(fake_ts, "v", horizon=5, tname="t")
    ck("真时间序列不被判 questionable",
       rf2.get("questionable") is False, str(rf2.get("warn")))
    ck("学到上升趋势（斜率 0.5）",
       rf2["fut_y"][0] > yy[-1] - 0.5,
       f"末期 {yy[-1]:.2f} → 预测 {rf2['fut_y'][0]:.2f}")
    ck("预测区间随步长变宽",
       all(rf2["hi"][i] <= rf2["hi"][i + 1]
           for i in range(len(rf2["hi"]) - 1)),
       str([round(v, 4) for v in rf2["hi"]]))
    ck("预测值与残差同量级（没跑飞）",
       all(abs(v - (3.0 + 0.5 * (60 + i))) < 2.0
           for i, v in enumerate(rf2["fut_y"], 1)),
       str([round(v, 2) for v in rf2["fut_y"]]))

    print("\n九、评价（熵权 + TOPSIS）")
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        cost = ds.pick(["热阻", "压降", "温度"])
        sc = mm.score(ds, [], cost)
        ck("熵权权重和为 1",
           abs(float(np.sum(sc["weights"])) - 1.0) < 1e-9,
           f"{float(np.sum(sc['weights'])):.10f}")
        ck("三个指标都有正权重",
           all(w > 0 for w in sc["weights"]),
           str([round(float(w), 4) for w in sc["weights"]]))
        ck("TOPSIS 得分在 [0,1]",
           all(0.0 <= s <= 1.0 for s in sc["score"]),
           f"min={min(sc['score']):.3f} max={max(sc['score']):.3f}")
        ck("排名第一是 #64",
           int(sc["order"][0]) + 1 == 64, f"第 {int(sc['order'][0]) + 1} 行")
        # 信息量大的指标权重高：压降方差最大
        i_p = cost.index("无量纲压降")
        ck("压降（方差最大）权重最高",
           float(sc["weights"][i_p]) == float(np.max(sc["weights"])),
           f"压降 {sc['weights'][i_p]:.4f} vs 最高 "
           f"{float(np.max(sc['weights'])):.4f}")

    print("\n十、聚类")
    # 10a 造三簇可分数据（三个高斯球，不是环 —— 环会让 K-means 切开）
    rng4 = np.random.default_rng(23)
    cent3 = np.array([[0.0, 0.0], [12.0, 0.0], [0.0, 12.0]])
    Xc3 = np.vstack([rng4.normal(c, 1.0, (90, 2)) for c in cent3])
    fake_c = _t.SimpleNamespace(
        cols=lambda ns: Xc3, col=lambda nm: Xc3[:, 0],
        num_names=["a", "b"], n_rows=len(Xc3), pick=lambda ns: ns)
    rc = cluster(fake_c, ["a", "b"])
    ck("三簇可分数据找到 3 个簇", rc["k"] == 3, f"k={rc['k']}")
    ck("可分数据轮廓系数高", rc["silhouette"] > 0.5,
       f"{rc['silhouette']:.3f}（分离度 {rc['separability']}）")
    ck("可分数据不报「无结构」", rc["no_structure"] is False,
       str(rc["warn"]))
    ck("每簇大小接近（90/90/90）",
       max(rc["sizes"]) - min(rc["sizes"]) <= 12, str(rc["sizes"]))
    ck("可分数据明显高过零模型",
       rc["margin"] > 0.10,
       f"实际 {rc['silhouette']:.3f} vs 零模型 {rc['null_silhouette']:.3f}")

    # 10b 单团数据 → 必须承认没有结构（零模型对照的意义就在这里）
    blob = rng4.normal(0, 1, (90, 2))
    fake_b = _t.SimpleNamespace(
        cols=lambda ns: blob, col=lambda nm: blob[:, 0],
        num_names=["a", "b"], n_rows=90, pick=lambda ns: ns)
    rb = cluster(fake_b, ["a", "b"])
    ck("单个高斯团被判定为无结构", rb["no_structure"] is True,
       f"k={rb['k']} sil={rb['silhouette']:.3f} "
       f"零模型={rb['null_silhouette']:.3f} 差={rb['margin']:+.3f}")

    # 10c 真数据（实验设计的离散网格）
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        xs_c = ds.pick(["宽度", "深高", "排数"])
        rd_c = cluster(ds, xs_c)
        ck("离散网格数据被判无自然簇数",
           rd_c["no_structure"] is True,
           f"k={rd_c['k']} sil={rd_c['silhouette']:.3f}")
        ck("簇中心换回原量纲（宽度落在 0~0.3）",
           all(-0.01 <= c[0] <= 0.31 for c in rd_c["centers_orig"]),
           str([round(c[0], 3) for c in rd_c["centers_orig"]]))

    print("\n十一、绘图（PIL，环境无 matplotlib）")
    import tempfile as _tf
    tdir = _tf.mkdtemp(prefix="mmkit_plot_")
    if Xa is not None:
        ds = mm.DS(mm.find_xlsx())
        _data_note(ds)
        # 散点
        r1 = plot_scatter(ds, ds.pick(["宽度"])[0], ds.pick(["热阻"])[0],
                          out=os.path.join(tdir, "s.png"))
        ck("散点图生成", os.path.exists(r1["path"]),
           f"{os.path.getsize(r1['path'])} 字节")
        # 折线（预测）
        r2 = plot_forecast(ds, ds.pick(["热阻"])[0], 5,
                           out=os.path.join(tdir, "f.png"))
        ck("预测折线图生成", os.path.exists(r2["path"]),
           f"{os.path.getsize(r2['path'])} 字节")
        ck("预测图带上「不可用」警告", r2["questionable"] is True,
           str(r2["warn"])[:60])
        # 柱状（权重）
        sc2 = mm.score(ds, [], ds.pick(["热阻", "压降", "温度"]))
        r3 = plot_bar(sc2["cols"], sc2["weights"],
                      title="熵权法权重", out=os.path.join(tdir, "b.png"))
        ck("柱状图生成", os.path.exists(r3["path"]),
           f"{os.path.getsize(r3['path'])} 字节")
        # 帕累托
        pc = ds.pick(["热阻", "压降"])
        r4 = plot_pareto(ds, pc, True, out=os.path.join(tdir, "p.png"))
        ck("帕累托图生成", os.path.exists(r4["path"]),
           f"{os.path.getsize(r4['path'])} 字节")
        # 前沿点数必须和图里用的是同一套算法，不能写死
        # （2 个目标的前沿和 3 个目标的前沿点数不同：9 vs 12）
        expect_front = len(mm.pareto_idx(ds.cols(pc), [True, True]))
        ck("帕累托图前沿点数与 mm.pareto_idx 一致",
           r4["front"] == expect_front,
           f"图 {r4['front']} vs 计算 {expect_front}")
        r4b = plot_pareto(ds, ds.pick(["热阻", "压降", "温度"]), True,
                          out=os.path.join(tdir, "p3.png"))
        ck("三目标前沿是 12 个点", r4b["front"] == 12, f"{r4b['front']}")
        ck("两目标前沿少于三目标（加目标只会更多点被支配）",
           r4["front"] <= r4b["front"], f"{r4['front']} <= {r4b['front']}")
        # PNG 头校验：不是空文件、是真 PNG
        with open(r4["path"], "rb") as fh:
            magic = fh.read(8)
        ck("生成的是真 PNG", magic == b"\x89PNG\r\n\x1a\n", str(magic))
        # 中文字体可用（否则标题会是方框）
        ck("找到中文字体（否则中文会是方框）",
           _font(16).getbbox("测试")[2] > 20,
           str(_font(16).getbbox("测试")))
    else:
        ck("绘图（无数据则跳过）", True, "跳过")

    print()
    print(BAR)
    print(f"{'ALL PASS' if n_bad == 0 else 'FAILED'}  {n_ok} 通过 / {n_bad} 失败")
    print(BAR)
    return 0 if n_bad == 0 else 1


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════
def _plot_via_mpl(a, ds, out):
    """用 matplotlib 出图。返回 None 表示这个 kind 不支持，调用方回退 PIL。

    为什么优先 mpl：PIL 版出的是 72 dpi 位图，没有 PDF，字体也无法嵌入。
    实测 out/fig 下 10 张图全部 72dpi、缺 PDF、极端像素 74.9%~95.3%
    （字被渲染成了方块）。matplotlib 一并解决，还能渲染希腊字母这类符号。
    """
    try:
        import plot_mpl as M
    except Exception:                               # noqa: BLE001
        return None

    base = out[:-4] if out.lower().endswith(".png") else out
    kind = a.kind

    def _en(names):
        return [_paper.describe(c)[0] for c in names]

    try:
        if kind == "box":
            cols = ds.pick(a.cost.split(",")) if a.cost else ds.num_names[:6]
            if not cols:
                return None
            paths = M.plot_box([ds.col(c) for c in cols], _en(cols),
                               out=base, ylabel="value",
                               title="Distribution by factor")
        elif kind == "hist":
            if not a.y:
                return None
            yc = ds.pick([a.y])[0]
            paths = M.plot_hist(ds.col(yc), out=base, xlabel=_en([yc])[0],
                                title="Distribution")
        elif kind == "corr":
            cols = (ds.pick(a.cost.split(",")) if a.cost
                    else [c for c in ds.num_names if "编号" not in c])
            if len(cols) < 2:
                return None
            Mx = np.corrcoef(np.column_stack([ds.col(c) for c in cols]).T)
            paths = M.plot_corr(Mx, _en(cols), out=base,
                                title="Pairwise correlation")
        elif kind == "resid":
            if not a.y or not a.x:
                return None
            xs = ds.pick(a.x.split(","))
            yc = ds.pick([a.y])[0]
            X = ds.cols(xs)
            yv = ds.col(yc)
            A = np.column_stack([np.ones(len(yv)), X])
            beta, *_ = np.linalg.lstsq(A, yv, rcond=None)
            paths = M.plot_resid(A @ beta, yv - A @ beta, out=base)
        elif kind == "pareto":
            if not a.min:
                return None
            cols = ds.pick(a.min.split(","))
            if len(cols) < 2:
                return None
            Mo = np.column_stack([ds.col(c) for c in cols[:2]])
            fi = mm.pareto_idx(Mo, [True, True])
            paths = M.plot_pareto(Mo, fi, _en(cols[:2]), out=base,
                                  title="Pareto front")
        elif kind == "sens":
            if not a.y:
                return None
            yc = ds.pick([a.y])[0]
            # 优先用 --x 传的因子；没传才退回数值列，且必须排除 ID 列 ——
            # 否则「样本编号」会被当成因子画进敏感性图（实测过，
            # 而论文自己的 VIF 表写着「样本编号：ID 列，不进模型」）。
            if a.cost:
                pcols = ds.pick(a.cost.split(","))
            elif getattr(a, "x", None):
                pcols = ds.pick(a.x.split(","))
            else:
                pcols = list(ds.num_names)
            pcols = [c for c in pcols
                     if c != yc and not _is_id_like(c)][:4]
            if not pcols:
                return None
            X = ds.cols(pcols)
            yv = ds.col(yc)
            A = mm.design(X, "linear")
            beta = np.linalg.lstsq(A, yv, rcond=None)[0]
            curves, labels = [], []
            grid = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
            for i, nm in enumerate(pcols):
                sd = float(np.std(X[:, i])) or 1.0
                ys = [float(beta[0] + beta[i + 1] * g * sd) for g in grid]
                curves.append(dict(x=grid.tolist(), y=ys))
                labels.append(_en([nm])[0])
            paths = M.plot_sens(curves, labels, out=base,
                                xlabel="displacement (standard deviations)",
                                ylabel=_en([yc])[0])
        elif kind == "bar":
            cols = ds.pick(a.cost.split(",")) if a.cost else []
            if not cols:
                return None
            sc = mm.score(ds, [], cols)
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4.8, 3.6))
            names = [_en([c])[0] for c in sc["cols"]]
            ax.bar(range(len(names)), sc["weights"], color="#4c72b0",
                   edgecolor="black", linewidth=0.5)
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, rotation=18, ha="right")
            ax.set_ylabel("weight")
            ax.set_title("Entropy weights")
            for i, w in enumerate(sc["weights"]):
                ax.text(i, w, f"{w:.3f}", ha="center", va="bottom",
                        fontsize=8)
            paths = M._save(fig, base)
        elif kind == "pred":
            if not a.y or not a.x:
                return None
            xs = ds.pick(a.x.split(","))
            yc = ds.pick([a.y])[0]
            X = ds.cols(xs)
            yv = ds.col(yc)
            A = np.column_stack([np.ones(len(yv)), X])
            beta, *_ = np.linalg.lstsq(A, yv, rcond=None)
            paths = M.plot_pred(yv, A @ beta, out=base,
                                title="Fitted against observed")
        elif kind == "cand":
            # 候选模型的 CV 误差对比：表要逐行读，图一眼看出差距
            if not a.y or not a.x:
                return None
            _xs2 = ds.pick(a.x.split(","))
            _fr = mm.fit(ds, ds.pick([a.y])[0], _xs2)
            _cs = [c for c in (_fr.get("cands") or [])
                   if c.get("rmse") is not None]
            if not _cs:
                return None
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            _cs = sorted(_cs, key=lambda c: float(c["rmse"]))
            # 用 paper.label_en，不是 _en_text —— 后者是给列名用的，
            # 不认识「线性/二次/幂律」这些结构名，会一律返回 "value"。
            _labs = [_paper.label_en(str(c.get("label") or "")) for c in _cs]
            _vals = [float(c["rmse"]) for c in _cs]
            fig, ax = plt.subplots(figsize=(5.6, max(2.4, 0.5 * len(_cs) + 1.4)))
            _cols = ["#c44e52" if i == 0 else "#4c72b0"
                     for i in range(len(_vals))]
            ax.barh(range(len(_vals)), _vals, color=_cols,
                    edgecolor="black", linewidth=0.6, alpha=0.85)
            ax.set_yticks(range(len(_vals)))
            ax.set_yticklabels(_labs)
            ax.invert_yaxis()
            ax.set_xlabel("cross-validated RMSE")
            ax.set_title("Candidate structures (lower is better)")
            for i, v in enumerate(_vals):
                ax.text(v, i, f"  {v:.5g}", va="center", ha="left",
                        fontsize=8)
            ax.set_xlim(0, max(_vals) * 1.25 if _vals else 1)
            ax.grid(axis="x", alpha=0.25)
            paths = M._save(fig, base)
        elif kind == "surfaces":
            # 三个指标各一张，拼成一张三联图
            _ys = ds.pick(a.y.split(",")) if a.y else []
            _ys = [c for c in _ys if c in ds.num_names]
            _xss = ds.pick(a.x.split(",")) if a.x else []
            _sfs = []
            for _yc in _ys:
                _s = mm.surface(ds, _yc, _xss)
                if not _s:
                    continue
                _s = dict(_s)
                for _k in ("x_name", "y_name", "fixed_name"):
                    if _s.get(_k):
                        _s[_k] = _en_text(str(_s[_k]))
                _d = _paper.describe(_yc)
                _s["y_en"] = _d[0] if _d else _yc
                _sfs.append(_s)
            if _sfs:
                paths = M.plot_surface_trio(_sfs, base)
        elif kind == "surface":
            if not a.y or not a.x:
                return None
            _sf = mm.surface(ds, ds.pick([a.y])[0],
                             ds.pick(a.x.split(",")))
            if _sf:
                # 轴标签必须转英文：列名是中文，进 LaTeX 会报
                # Unicode character 错（中文进正文踩过 7 次）。
                _sf = dict(_sf)
                for _k in ("x_name", "y_name", "fixed_name"):
                    if _sf.get(_k):
                        _sf[_k] = _en_text(str(_sf[_k]))
                paths = M.plot_surface(
                    _sf, base, title=f"{_en_text(a.y)} response surface")
        elif kind == "tornado":
            if not a.y:
                return None
            _xs = ds.pick(a.x.split(",")) if a.x else [
                c for c in ds.num_names if c != a.y and "编号" not in c][:3]
            _d = float(getattr(a, "delta", 0.3) or 0.3)
            _sr = mm.sens(ds, ds.pick([a.y])[0], _xs, _d)
            # 转成英文再交给绘图函数（LaTeX 里不能有中文）
            _it = []
            for _x in (_sr.get("items") or []):
                _c = dict(_x)
                _c["name"] = _en_text(str(_x.get("name", "")))
                _it.append(_c)
            paths = M.plot_tornado(
                _it, _sr.get("base") or 0.0, out=base, delta=_d,
                title=f"Sensitivity of {_en_text(a.y)} to each factor")
        elif kind == "flow":
            # 技术路线图。PIL 版是 72dpi 位图，进 LaTeX 会糊。
            _steps = getattr(a, "steps", "") or ""
            _lst = ([x.strip() for x in _steps.split(",") if x.strip()]
                    if _steps else
                    ["Problem reading", "Framework design", "Derivation",
                     "Coding and running", "Independent verification",
                     "Paper writing", "Review"])
            if len(_lst) < 3:
                return None
            paths = M.plot_flow(_lst, out=base, title="Technical route")
        elif kind == "qq":
            if not a.y:
                return None
            yc = ds.pick([a.y])[0]
            yv = np.asarray(ds.col(yc), dtype=float)
            n = len(yv)
            # 标准化残差 vs 理论分位数（正态）
            z = (yv - yv.mean()) / (yv.std() or 1.0)
            zs = np.sort(z)
            # 用 Acklam 近似算正态分位数
            q = [(i - 0.5) / n for i in range(1, n + 1)]
            from statistics import NormalDist
            th = np.array([NormalDist().inv_cdf(p) for p in q])
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4.6, 4.2))
            ax.plot(th, zs, "o", ms=4, color="#4c72b0", alpha=0.75)
            lo, hi = float(th.min()), float(th.max())
            ax.plot([lo, hi], [lo, hi], "--", color="#d62728", lw=1.2)
            ax.set_xlabel("theoretical quantile")
            ax.set_ylabel("standardised value")
            ax.set_title(r"Q--Q plot against normal")
            ax.set_aspect("equal", adjustable="box")
            paths = M._save(fig, base)
        else:
            return None
    except Exception as e:                          # noqa: BLE001
        return dict(path="", why=f"matplotlib 失败，回退 PIL："
                                 f"{type(e).__name__}: {e}")

    return dict(path=paths["png"]["path"], pdf=paths["pdf"]["path"],
                engine="matplotlib", warn=[])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="数学建模插件：算 + 验 + 出报告")
    # choices 里只能放**真的有 dispatch 分支**的子命令。
    #
    # 原来还放着 cand / surface / formula：
    #   · cand、surface 是 `plot --kind` 的取值，不是子命令
    #   · formula 根本没有实现
    # argparse 会接受它们，然后一路走到 main() 末尾的 run() 兜底 ——
    # 实测 `mmkit.py cand --y 热阻 --x 宽度` **直接跑出整篇论文**，
    # 调它的人（尤其是不看源码的 LLM）会以为图出好了。
    # 从 choices 移除后，argparse 立刻报 invalid choice 并列出全部合法值。
    ap.add_argument("cmd", nargs="?", default="run",
                    choices=["run", "solve", "race", "ode", "dim", "forecast",
                             "cluster", "plot", "profile", "ahp", "grey", "graph",
                             "greyrel", "fuzzy", "video", "clean", "merge", "advise",
                             "selftest", "hints", "experiment", "contract",
                             "skeleton"])
    ap.add_argument("--directions", default="",
                    help="greyrel 的指标方向，如 1,-1,1（越大越好 / 越小越好）")
    ap.add_argument("--ref", default="",
                    help="greyrel 的参考序列（留空用理想解）")
    ap.add_argument("--rho", type=float, default=0.5,
                    help="greyrel 的分辨系数，默认 0.5")
    ap.add_argument("--normalize", default="mean",
                    choices=["init", "mean", "range"],
                    help="greyrel 的归一化方式")
    ap.add_argument("--weights", default="",
                    help="fuzzy 的权重，如 0.3,0.3,0.4")
    ap.add_argument("--membership", default="",
                    help="fuzzy 的隶属度矩阵，行用 ; 隔开")
    ap.add_argument("--grades", default="",
                    help="fuzzy 的等级分值，如 95,85,75")
    ap.add_argument("--operator", default="weighted",
                    choices=["weighted", "maxmin"],
                    help="fuzzy 的合成算子")
    ap.add_argument("--op", default="dijkstra",
                    choices=["dijkstra", "mst", "flow", "tsp"],
                    help="graph 的算法")
    ap.add_argument("--edges", default="",
                    help='边表： "0-1:4,1-2:3"（graph 用）')
    ap.add_argument("--matrix", default="",
                    help='距离矩阵，行用 | 隔开（tsp 用）')
    ap.add_argument("--from", dest="src", type=int, default=None,
                    help="graph 的起点 / 源点")
    ap.add_argument("--to", dest="dst", type=int, default=None,
                    help="graph 的终点 / 汇点")
    ap.add_argument("--nodes", type=int, default=0,
                    help="节点数（留空按边里的最大下标推断）")
    ap.add_argument("--ahp", default="",
                    help='两两比较矩阵，行用 | 分隔： "1,3,5|1/3,1,2|1/5,1/2,1"')
    ap.add_argument("--names", default="", help="AHP 的指标名，逗号分隔")
    ap.add_argument("--series", default="",
                    help="grey 的时间序列，逗号分隔： 2.874,3.278,...")
    ap.add_argument("--kind", default="scatter",
                    choices=["scatter", "forecast", "bar", "pareto",
                             "corr", "pred", "sens", "flow",
                             "box", "hist", "resid", "qq", "tornado",
                             "cand", "surface", "surfaces"],
                    help="plot 的图型")
    ap.add_argument("--out-png", default="", help="图片输出路径")
    ap.add_argument("--k", type=int, default=0,
                    help="cluster 的簇数；0 = 自动选")
    # 不能叫 --h：argparse 的 -h 是 help 的简写，--h 会被吃成 help
    ap.add_argument("--horizon", "-n", type=int, default=5,
                    help="forecast 的预测步数")
    ap.add_argument("--t", default="", help="forecast 的时间列（留空用行序）")
    ap.add_argument("--rhs", default="", help="ODE 右端，如 -0.7*y 或 sin(t)")
    ap.add_argument("--y0", type=float, default=1.0, help="初值 y(t0)")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=10.0)
    ap.add_argument("--method", default="rk45", choices=["rk45", "rk4"])
    ap.add_argument("--var", action="append", default=[],
                    help="dim 的变量，形如 周期=T 或 重力=L*T^-2")
    ap.add_argument("--data", default="")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--y", default="")
    ap.add_argument("--x", default="")
    ap.add_argument("--obj", default="", help="solve 的目标列（留空用 --y）")
    ap.add_argument("--constraint", action="append", default=[],
                    help="形如 热阻<=0.74，可重复")
    ap.add_argument("--maximize", action="store_true", help="solve 求最大")
    ap.add_argument("--claim", action="append", default=[],
                    help="名字:正/负，可重复")
    ap.add_argument("--min", default="", help="越小越好的目标列")
    ap.add_argument("--max", default="", help="越大越好的目标列")
    ap.add_argument("--benefit", default="", help="评价题的效益型指标")
    ap.add_argument("--cost", default="", help="评价题的成本型指标")
    ap.add_argument("--delta", type=float, default=0.1)
    ap.add_argument("--reproduced", action="store_true",
                    help="声明已跨环境重跑（e3 才能到 2）")
    ap.add_argument("--out-csv", default="",
                    help="干净 CSV 的输出路径，默认 out/clean.csv")
    ap.add_argument("--names-out", default="",
                    help="列名映射 CSV 的输出路径（可选）")
    ap.add_argument("--out-gif", default="",
                    help="视频输出路径，默认 out/fig/flow.gif")
    ap.add_argument("--frame-ms", type=int, default=900,
                    help="每帧停留毫秒数")
    ap.add_argument("--steps", default="",
                    help="流程图节点，用 | 隔开（flow 图用）")
    ap.add_argument("--tex", default="",
                    help="同时生成英文 LaTeX 论文，例如 paper.tex")
    ap.add_argument("--no-figs", action="store_true",
                    help="不要自动出图（默认会生成 12 张）")
    ap.add_argument("--compile", action="store_true",
                    help="生成后就地 pdflatex 编译两遍")
    ap.add_argument("--mechanism", default="auto",
                        choices=["auto", "full", "brief", "none"],
                        help="机理段：auto 按题型选，full 完整，"
                             "brief 只留方向，none 跳过")
    ap.add_argument("--no-gate", action="store_true",
                    help="跳过全量质量门（探索阶段用）")
    ap.add_argument("--strict", action="store_true",
                    help="出稿前强制过竞赛规则，不过就拒绝")
    ap.add_argument("--lang", default="en",
                    choices=_i18n.available(),
                    help="论文语言（en/zh/ja/ko/fr/de/es/ru）")
    ap.add_argument("--team", default="000000",
                    help="队号，写进论文页眉，不写姓名学校")
    ap.add_argument("--problem", default="",
                    help="题目的一句话描述，写进摘要")
    ap.add_argument("--out", default="", help="把报告写成 markdown 文件")
    ap.add_argument("--json", action="store_true")
    # ── 试错循环（experiment）──
    ap.add_argument("--rounds", type=int, default=5,
                    help="experiment 的最大轮数，默认 5")
    ap.add_argument("--routes", type=int, default=3,
                    help="每轮提几条路线，默认 3（契约要求 >=3）")
    ap.add_argument("--propose-json", default="",
                    help="外部提案文件（LLM 写）；留空用规则版 propose")
    ap.add_argument("--no-contract", action="store_true",
                    help="experiment 跳过提案契约校验（默认会先过契约）")
    ap.add_argument("--budget", type=float, default=45.0,
                    help="experiment 的总预算分钟数")
    ap.add_argument("--from-tex", default="",
                    help="skeleton 从这个已生成的 tex 提取段落（key 必然对得上）")
    ap.add_argument("--overrides", default="",
                    help="LLM 写的正文段落（JSON: 原文前40字 -> 新文本）")
    ap.add_argument("--proposal", default="",
                    help="contract 要校验的提案文件")
    # 名字用 --types 而不是 --kind：--kind 已经被 plot --kind 占了，
    # argparse 会直接报 conflicting option string（第 108 轮实测）。
    ap.add_argument("--types", default="",
                    help="advise：显式声明题型（逗号分隔）。"
                         "LLM 读完题面后最清楚，插件是能力层不是预言机")
    a = ap.parse_args()

    # --json 时：提示全部改走 stderr，stdout 只留 JSON。
    # 原来两者混在 stdout 里，LLM 解析前得先剥皮；剥皮逻辑一脆，
    # 就会退回「直接 run 一条龙」，插件那 19 个命令全被绕过。
    # JSON 本身在下面显式写 sys.__stdout__（不受这次重定向影响）。
    if bool(getattr(a, "json", False)):
        sys.stdout = sys.stderr

    if a.cmd == "selftest":
        return selftest()

    # ── 试错循环：propose → exec → judge → 下一轮 ──
    # 这是「LLM 主导建模」的执行器：LLM 给提案（或规则出提案），
    # 它负责跑、判、记死路。原来只在 orchestrate.py 里能跑，
    # 没接进主入口，等于插件的能力层对 LLM 不可见。
    # ── 骨架：列出可被 LLM 替换的正文段落 ──
    # 不依赖 run() 的内部流程（那条路上有多个提前 return，实测卡住），
    # 直接调 paper.build 收集。代价是只能拿到不依赖完整 ctx 的段落，
    # 但那些正好是最该由 LLM 重写的：摘要与结论。
    if a.cmd == "skeleton":
        import paper as _pp
        # 从已生成的 tex 提取：key 一定和 run 的产物对得上。
        # 用 paper.build 的简化 ctx 会因措辞不同而错位（实测过）。
        if a.from_tex:
            _t = open(a.from_tex, encoding="utf-8").read()
            _paras = [p.strip() for p in _t.split("\n\n")
                      if p.strip()
                      and not p.strip().startswith(("\\", "%"))
                      and "\\begin{" not in p and "\\end{" not in p
                      and len(p.strip()) > 120]
            _sk = [(_pp.para_key(p), " ".join(p.split()))
                   for p in _paras]
        else:
            _pp.set_overrides(None)
            _ctx = dict(ds=None, n=0, y=a.y,
                        xs=[x.strip() for x in (a.x or "").split(",") if x.strip()],
                        min_cols=a.min, problem=a.problem, lang=a.lang)
            try:
                _pp.build(_ctx)
            except Exception as e:              # noqa: BLE001
                _say(f"  build 失败：{type(e).__name__}: {e}")
            _sk = [(k, t) for k, t in _pp.dump_skeleton()
                   if k and not k.startswith("__")]
        if a.json:
            _emit([dict(key=k, text=t) for k, t in _sk])
        else:
            _say(f"  可替换的正文段落：{len(_sk)} 段")
            _say("  用法：写一个 {\"原文前40字\": \"新文本\"} 的 JSON，")
            _say("        然后 run --overrides 那个文件（或用 MMKIT_OVERRIDES）")
            for k, t in _sk:
                _say("")
                _say(f"  [{k}]")
                _say(f"    {t[:150]}")
        return 0

    if a.cmd == "experiment":
        import orchestrate as _och
        data = a.data or mm.find_xlsx()
        if not data or not os.path.exists(data):
            _say(f"找不到数据：{data!r}")
            return 2
        propose = _och.rule_propose
        if a.propose_json:
            _pj = json.load(open(a.propose_json, encoding="utf-8"))
            # 形状处理与 `contract` 子命令保持一致（第 104 轮）。
            # 原来这里直接 `_pj.get("proposals") if isinstance(_pj, dict)`：
            # 递单个路线对象会得到 None → [] → 被当成「空提案」静默停住。
            if isinstance(_pj, dict):
                if "proposals" in _pj:
                    _routes = _pj.get("proposals") or []
                elif any(k in _pj for k in ("route_id", "method", "title")):
                    _say("  提案必须是**列表**（或 {\"proposals\": [...]}），"
                         "现在收到的是单个路线对象。")
                    return 2
                else:
                    _routes = []
            else:
                _routes = _pj
            # 契约必须先过（第 104 轮）。
            # 原来 `experiment --propose-json` 完全不校验：实测同一份提案
            # `contract` 判 ok=False（三条都是 run 只换 --x，属同构变体），
            # `experiment` 却照跑不误 —— 契约成了摆设。
            # 注意：这里写成 `a.no_contract` 而不是 getattr(a, ...) ——
            # schema.py 靠扫 `a.<名字>` 提取参数，用 getattr 会让这个开关
            # 从能力清单里消失（实测：重建 schema 后 --no-contract 不在里面）。
            if not a.no_contract:
                import contract as _ct
                _cmds, _argn = _ct.reflect_cmds()
                _res = _ct.validate_batch(list(_routes or []), _cmds, _argn)
                if not _res.get("ok"):
                    _say("  提案没过契约，先修它（或用 --no-contract 显式绕过）：")
                    for _k, _v in (_res.get("per_route_errors") or {}).items():
                        _say(f"    {_k}: {'；'.join(_v)[:110]}")
                    for _v in (_res.get("batch_errors") or []):
                        _say(f"    整体: {_v[:110]}")
                    return 2

            def propose(ctx, _r=_routes):
                return list(_r or [])
            _say(f"  用外部提案：{len(_routes or [])} 条 <- {a.propose_json}")
        st = _och.run_loop(data, propose, max_rounds=a.rounds,
                           routes_per_round=a.routes, budget_min=a.budget)
        rep = _och.report(st)
        if a.json:
            _emit(dict(rounds=st.rounds_used, attempts=len(st.attempts),
                       reason=st.stop_reason,
                       best=st.best.get("brief", ""),
                       dead_ends=st.dead_summary()[:20],
                       report=rep))
        else:
            _say(rep)
        return 0

    # ── 提案契约：LLM 的空话在这里被挡住 ──
    if a.cmd == "contract":
        import contract as _ct
        if not a.proposal:
            _say("contract 需要 --proposal <提案.json>")
            return 2
        try:
            pj = json.load(open(a.proposal, encoding="utf-8"))
        except Exception as e:                      # noqa: BLE001
            _say(f"  读不出提案：{e}")
            return 2
        # 提案的顶层可以是列表，也可以是 {"proposals": [...]}。
        # 但如果是**单个路线对象**被直接递进来，原来会走到 `pj.get("proposals")`
        # → None → [] → 报「只提了 0 条」。那句话会让人以为自己写空了文件，
        # 实际上文件里是有内容的，只是形状不对（第 99 轮）。
        if isinstance(pj, dict):
            if "proposals" in pj:
                batch = pj.get("proposals") or []
            elif any(k in pj for k in ("route_id", "method", "title")):
                _say("  提案必须是**列表**（或 {\"proposals\": [...]}），"
                     "现在收到的是单个路线对象。")
                _say("  示例：[{...}, {...}, {...}] —— 至少 3 条。")
                return 2
            else:
                batch = []
        else:
            batch = pj
        cmds, argn = _ct.reflect_cmds()
        res = _ct.validate_batch(batch or [], cmds, argn)
        if a.json:
            _emit(res)
        else:
            _say(f"  提案 {len(batch or [])} 条；结果：{res}")
        return 0 if res.get("ok") else 1

    if a.cmd == "solve":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        if not a.x or not (a.obj or a.y):
            print("solve 需要 --x 和 --obj（或 --y）")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        xs = ds.pick(a.x.split(","))
        obj = ds.pick([a.obj or a.y])[0]
        print(BAR)
        print(f"约束优化 · 数据 {os.path.basename(path)}（{ds.n_rows} 行）")
        print(BAR)
        print(f"  自变量 {xs}")
        print(f"  目标   {obj}（{'最小化' if not a.maximize else '最大化'}）")
        if a.constraint:
            print(f"  约束   {a.constraint}")
        r = solve_opt(ds, xs, obj, a.constraint, minimize=not a.maximize)
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        elif r.get("mode") == "discrete":
            print_solve_discrete(r, xs, obj)
        else:
            print_solve(r, xs, obj, ds)
        return 0

    if a.cmd == "race":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        if not a.y or not a.x:
            print("race 需要 --y 和 --x")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        yc = ds.pick([a.y])[0]
        xs = ds.pick(a.x.split(","))
        # race 也在比较「哪个结构更好」，自变量混进响应组成部分时
        # 比出来的名次没有意义。与 run 用同一套判定（mm.suspect_leak）。
        _lb = [c for c, _cc, _k in mm.suspect_leak(ds, yc, xs) if _k == "leak"]
        if _lb:
            _msg = ("自变量里有响应的组成部分：%s。删掉这些列再比结构。"
                    % "、".join(_lb))
            if getattr(a, "strict", False):
                print("\n[拒绝] " + _msg)
                return 2
            print("\n[警告] " + _msg)
        r = race_seeds(ds, yc, xs)
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        else:
            print(BAR)
            print(f"数据 {os.path.basename(path)}（{ds.n_rows} 行）")
            print(BAR)
            print_race(r, yc)
        return 0

    if a.cmd == "ode":
        if not a.rhs:
            print("ode 需要 --rhs，例如 --rhs \"-0.7*y\"")
            return 2
        try:
            r = ode_solve(a.rhs, [a.y0], a.t0, a.t1, a.method)
        except ValueError as e:
            print(f"表达式有问题：{e}")
            return 2
        if a.json:
            r2 = dict(r)
            r2["ts"] = r["ts"].tolist()
            r2["ys"] = r["ys"].tolist()
            _emit(json.dumps(r2, ensure_ascii=False, indent=2))
        else:
            print_ode(r)
        return 0

    if a.cmd == "dim":
        if not a.var:
            print("dim 需要至少一个 --var，例如 --var 周期=T --var 重力=L*T^-2")
            return 2
        pairs, bad = [], []
        for raw in a.var:
            if "=" not in raw:
                bad.append(f"{raw!r}（要写成 名字=量纲）")
                continue
            nm, spec = raw.split("=", 1)
            try:
                parse_dims(spec)
            except ValueError as e:
                bad.append(f"{raw!r}（{e}）")
                continue
            pairs.append((nm.strip(), spec.strip()))
        if bad:
            print("解析不了：")
            for b in bad:
                print(f"  · {b}")
            return 2
        r = dimension_analysis(pairs)
        if a.json:
            _emit(json.dumps(dict(dims=r["dims"], rank=r["rank"], n=r["n"],
                                  n_pi=r["n_pi"],
                                  pis=[p.tolist() for p in r["pis"]],
                                  names=r["names"]),
                             ensure_ascii=False, indent=2))
        else:
            print_dim(r)
        return 0

    if a.cmd == "forecast":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        if not a.y:
            print("forecast 需要 --y")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        yc = ds.pick([a.y])[0]
        tc = ds.pick([a.t])[0] if a.t else None
        r = forecast(ds, yc, a.horizon, tc)
        if not r.get("ok"):
            print(f"做不了：{r.get('why')}")
            return 2
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        else:
            print(BAR)
            print(f"数据 {os.path.basename(path)}（{ds.n_rows} 行）")
            print(BAR)
            print_forecast(r)
        return 0

    if a.cmd == "cluster":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        if not a.x:
            print("cluster 需要 --x（要聚类的特征列）")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        xs = ds.pick(a.x.split(","))
        r = cluster(ds, xs, a.k or None)
        if not r.get("ok"):
            print(f"做不了：{r.get('why')}")
            return 2
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        else:
            print(BAR)
            print(f"数据 {os.path.basename(path)}（{ds.n_rows} 行）")
            print(BAR)
            print_cluster(r)
        return 0

    if a.cmd == "plot":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        out = a.out_png or f"plot_{a.kind}.png"
        # matplotlib 优先：矢量 + 字体嵌入 + LaTeX 渲染
        _m = _plot_via_mpl(a, ds, out)
        if _m is not None and _m.get("path"):
            print(f"  图已保存 {_m['path']}"
                  f"（{os.path.getsize(_m['path'])} 字节，matplotlib）")
            if _m.get("pdf"):
                print(f"  矢量版 {_m['pdf']}"
                      f"（{os.path.getsize(_m['pdf'])} 字节，进 LaTeX 用这个）")
            for _w in (_m.get("warn") or []):
                print(f"  ⚠ {_w}")
            return 0
        if _m is not None and _m.get("why"):
            print(f"  {_m['why']}")
        r = None
        if a.kind == "scatter":
            if not a.x or not a.y:
                print("scatter 需要 --x 与 --y")
                return 2
            xs = ds.pick(a.x.split(","))
            r = plot_scatter(ds, xs[0], ds.pick([a.y])[0],
                             color_by=a.k, out=out)
        elif a.kind == "forecast":
            if not a.y:
                print("forecast 图需要 --y")
                return 2
            r = plot_forecast(ds, ds.pick([a.y])[0], a.horizon, out)
        elif a.kind == "box":
            cols = ds.pick(a.cost.split(",")) if a.cost else ds.num_names
            r = plot_box(ds, cols, out)
        elif a.kind == "hist":
            if not a.y:
                print("hist 需要 --y")
                return 2
            r = plot_hist(ds, ds.pick([a.y])[0], out)
        elif a.kind == "resid":
            if not a.y or not a.x:
                print("resid 需要 --y 与 --x")
                return 2
            r = plot_resid(ds, ds.pick(a.x.split(",")),
                           ds.pick([a.y])[0], out)
        elif a.kind == "qq":
            if not a.y or not a.x:
                print("qq 需要 --y 与 --x")
                return 2
            r = plot_qq(ds, ds.pick([a.y])[0],
                        ds.pick(a.x.split(",")), out)
        elif a.kind == "corr":
            cols = ds.pick(a.cost.split(",")) if a.cost else ds.num_names
            r = plot_corr(ds, cols, out)
        elif a.kind == "pred":
            if not a.y or not a.x:
                print("pred 需要 --y 与 --x")
                return 2
            r = plot_pred(ds, ds.pick(a.x.split(",")),
                          ds.pick([a.y])[0], out)
        elif a.kind == "flow":
            r = plot_flow(a.steps.split("|") if a.steps else None, out)
        elif a.kind == "bar":
            cols = ds.pick(a.cost.split(",")) if a.cost else []
            if not cols:
                print("bar 需要 --cost（要画权重的指标列）")
                return 2
            sc = mm.score(ds, [], cols)
            r = plot_bar([_paper.describe(c)[0] for c in sc["cols"]],
                         sc["weights"],
                         title="Entropy weights", ylabel="Weight",
                         out=out)
        elif a.kind == "sens":
            # 敏感性：把每个因子扰动 ±1 个标准差，看目标变多少
            if not a.y:
                print("sens 需要 --y（要观察的目标列）")
                return 2
            ycol = ds.pick([a.y])[0]
            pcols = (ds.pick(a.cost.split(",")) if a.cost
                     else ds.num_names[:3])
            pcols = [c for c in pcols if c != ycol]
            if not pcols:
                print("sens 需要 --cost（要扰动的因子列）")
                return 2
            X = ds.cols(pcols)
            yv = ds.col(ycol)
            A = mm.design(X, "linear")
            beta = np.linalg.lstsq(A, yv, rcond=None)[0]
            items = []
            for k, nm in enumerate(pcols):
                sd = float(np.std(X[:, k], ddof=1))
                if sd <= 0:
                    continue

                def _eval(delta, k=k):
                    Xp = X.copy()
                    Xp[:, k] = Xp[:, k] + delta * sd
                    return float(np.mean(mm.design(Xp, "linear") @ beta))
                items.append(dict(label=nm, base=_eval(0.0),
                                  plus=_eval(+1.0), minus=_eval(-1.0)))
            r = plot_sens(items, out)
        elif a.kind == "pareto":
            cols = ds.pick(a.min.split(",")) if a.min else []
            if len(cols) < 2:
                print("pareto 需要至少两个 --min 目标列")
                return 2
            r = plot_pareto(ds, cols[:3], True, out)
        else:
            print(f"未知图类型 {a.kind!r}")
            return 2
        if r is None or not r.get("path"):
            print(f"没画出来：{(r or {}).get('why', '未知原因')}")
            return 2
        print(f"  图已保存 {r['path']}"
              f"（{os.path.getsize(r['path'])} 字节）")
        if r.get("warn"):
            for w in r["warn"]:
                print(f"  ⚠ {w}")
        if r.get("questionable"):
            print("  ⚠ 这张图对应的预测不可用（见 forecast 的警告）")
        return 0

    if a.cmd == "profile":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        import dataprof as _dp
        _ds = mm.DS(path, a.sheet)
        _p = _dp.profile(_ds)
        if a.json:
            _emit(json.dumps(_p, ensure_ascii=False, indent=2, default=str))
        else:
            _data_note(_ds)
            print(_dp.report(_p))
        return 0

    if a.cmd == "ahp":
        if not a.ahp:
            print("ahp 需要 --ahp，行用 | 分隔、元素用 , 分隔")
            print('  例：--ahp "1,3,5|1/3,1,2|1/5,1/2,1"')
            return 2
        try:
            rows = []
            for seg in a.ahp.split("|"):
                row = []
                for cell in seg.split(","):
                    cell = cell.strip()
                    if not cell:
                        continue
                    row.append(float(safe_expr(cell)(0.0, [0.0])))
                if row:
                    rows.append(row)
        except (ValueError, SyntaxError) as e:
            print(f"矩阵解析失败：{e}")
            return 2
        if len({len(r) for r in rows}) != 1:
            print(f"矩阵不是方阵：各行长度 {[len(r) for r in rows]}")
            return 2
        names = [s.strip() for s in a.names.split(",") if s.strip()] \
            if a.names else None
        try:
            r = mm.ahp(rows, names)
        except ValueError as e:
            print(f"AHP 算不了：{e}")
            return 2
        if a.json:
            _emit(json.dumps(dict(weights=r["weights"].tolist(),
                                  lambda_max=r["lambda_max"], CI=r["CI"],
                                  CR=r["CR"], RI=r["RI"],
                                  consistent=r["consistent"],
                                  names=r["names"], warn=r["warn"]),
                             ensure_ascii=False, indent=2))
        else:
            mm.print_ahp(r)
        return 0

    if a.cmd == "grey":
        vals = []
        if a.series:
            try:
                vals = [float(safe_expr(x.strip())(0.0, [0.0]))
                        for x in a.series.split(",") if x.strip()]
            except (ValueError, SyntaxError) as e:
                print(f"序列解析失败：{e}")
                return 2
        else:
            path = a.data or mm.find_xlsx()
            if not path or not os.path.exists(path):
                print("grey 需要 --series 或可用的数据文件")
                return 2
            if not a.y:
                print("用数据文件时 grey 需要 --y")
                return 2
            ds = mm.DS(path, a.sheet)
            _data_note(ds)
            vals = [float(v) for v in ds.col(ds.pick([a.y])[0])]
        r = gm11(vals, a.horizon)
        if not r.get("ok"):
            print(f"做不了：{r.get('why')}")
            return 2
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print_gm11(r)
        return 0

    if a.cmd == "graph":
        import graph as _g
        op = a.op or "dijkstra"
        try:
            if op in ("dijkstra", "mst", "flow"):
                eds = parse_edges(a.edges)
                n = max(max(u, v) for u, v, _w in eds) + 1
                if a.nodes and a.nodes > n:
                    n = a.nodes
            else:  # tsp
                if not a.matrix:
                    print("tsp 需要 --matrix，行用 | 或 ; 隔开")
                    return 2
                # 行分隔符同时支持 | 和 ; —— PowerShell 会把 | 当管道符，
                # 命令行里根本没法直接写 |，所以 ; 必须能用。
                raw = a.matrix.replace("|", ";")
                mat = [[float(safe_expr(c.strip())(0.0, [0.0]))
                        for c in row.split(",") if c.strip()]
                       for row in raw.split(";") if row.strip()]
                n = len(mat)
        except (ValueError, SyntaxError) as e:
            print(f"输入解析失败：{e}")
            return 2

        try:
            if op == "dijkstra":
                if a.src is None:
                    print("dijkstra 需要 --from")
                    return 2
                r = _g.dijkstra(n, eds, a.src, a.dst)
                r.update(src=a.src)
                if a.dst is not None:
                    r["dst"] = a.dst
            elif op == "mst":
                r = _g.kruskal(n, eds)
                r["n"] = n
            elif op == "flow":
                if a.src is None or a.dst is None:
                    print("flow 需要 --from 与 --to")
                    return 2
                r = _g.max_flow(n, eds, a.src, a.dst)
                r.update(s=a.src, t=a.dst)
            else:
                r = _g.tsp(n, mat, a.src or 0)
                r["n"] = n
        except ValueError as e:
            print(f"算不了：{e}")
            return 2

        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        else:
            print_graph(r, op)
        return 0

    if a.cmd in ("greyrel", "fuzzy"):
        # 共用的矩阵解析：行用 | 或 ; 隔开，元素可以用 1/3
        def _mat(spec):
            raw = (spec or "").replace("|", ";")
            return [[float(safe_expr(c.strip())(0.0, [0.0]))
                     for c in row.split(",") if c.strip()]
                    for row in raw.split(";") if row.strip()]

        def _nums(spec):
            return [float(safe_expr(c.strip())(0.0, [0.0]))
                    for c in (spec or "").split(",") if c.strip()]

        if a.cmd == "greyrel":
            if not a.matrix:
                print("greyrel 需要 --matrix（行用 ; 或 | 隔开）")
                return 2
            try:
                M = _mat(a.matrix)
                dirs = _nums(a.directions) if a.directions else None
                ref = _nums(a.ref) if a.ref else None
            except (ValueError, SyntaxError) as e:
                print(f"输入解析失败：{e}")
                return 2
            try:
                r = mm.grey_relational(M, directions=dirs, rho=a.rho,
                                       normalize=a.normalize, ref=ref)
            except ValueError as e:
                print(f"算不了：{e}")
                return 2
            if a.json:
                _emit(json.dumps(dict(grades=r["grades"].tolist(),
                                      order=r["order"].tolist(),
                                      ref=r["ref"].tolist(),
                                      ref_src=r["ref_src"],
                                      rho=r["rho"], dmin=r["dmin"],
                                      dmax=r["dmax"], warn=r["warn"]),
                                 ensure_ascii=False, indent=2))
            else:
                names = ([s.strip() for s in a.names.split(",") if s.strip()]
                         if a.names else None)
                mm.print_grey_relational(r, names)
            return 0

        # fuzzy
        if not a.membership:
            print("fuzzy 需要 --membership（行用 ; 或 | 隔开）")
            return 2
        try:
            R = _mat(a.membership)
        except (ValueError, SyntaxError) as e:
            print(f"隶属度矩阵解析失败：{e}")
            return 2
        # 权重来源：--weights 直接给，或 --ahp 用 AHP 算
        try:
            if a.weights:
                W = _nums(a.weights)
            elif a.ahp:
                ahp_r = mm.ahp(_mat(a.ahp))
                if not ahp_r["consistent"]:
                    print("AHP 矩阵没通过一致性检验（CR≥0.1），"
                          "先修矩阵再来定权重")
                    return 2
                W = ahp_r["weights"].tolist()
                print(f"  权重来自 AHP（CR={ahp_r['CR']:.4f} 通过）")
            else:
                print("fuzzy 需要 --weights 或 --ahp")
                return 2
            grades = _nums(a.grades) if a.grades else None
        except (ValueError, SyntaxError) as e:
            print(f"输入解析失败：{e}")
            return 2
        try:
            r = mm.fuzzy_eval(W, R, operator=a.operator, grades=grades)
        except ValueError as e:
            print(f"算不了：{e}")
            return 2
        if a.json:
            _emit(json.dumps(dict(B=r["B"].tolist(), Bn=r["Bn"].tolist(),
                                  score=r["score"], peak=r["peak"],
                                  operator=r["operator"], warn=r["warn"]),
                             ensure_ascii=False, indent=2))
        else:
            gn = ([s.strip() for s in a.names.split(",") if s.strip()]
                  if a.names else None)
            mm.print_fuzzy(r, grade_names=gn)
        return 0

    if a.cmd == "video":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        if not a.y or not a.x:
            print("video 需要 --y 与 --x")
            return 2
        ycol = ds.pick([a.y])[0]
        xs = ds.pick(a.x.split(","))
        gif_out = a.out_gif or "out/fig/flow.gif"
        outdir = os.path.dirname(os.path.abspath(gif_out))
        # 图就在 gif 同目录，或它的 fig/ 子目录 —— 两处都找。
        # 第一版只找 outdir/fig，而实际图在 outdir，于是 9 张图全部
        # 找不到、每帧安静地留白，程序还返回 0。静默失败最危险。
        # 第三个目录原本是仓库默认题的 out/fig —— 和 _collect_figures
        # 第 44 轮删掉的那个兜底一模一样：换目录跑就从别处借图，
        # 而 GIF 里是别人题的图，不报错。
        fig_dirs = [outdir, os.path.join(outdir, "fig")]
        missing = []

        def _fig(name):
            for d in fig_dirs:
                p = os.path.join(d, name)
                if os.path.exists(p):
                    return p
            missing.append(name)
            return None

        # 收集真实数字，视频里每一帧都要挂一个，不做装饰性轮播
        eda = mm.eda(ds)
        fitr = mm.fit(ds, ycol, xs)
        best = fitr.get("best") or {}
        robs = mm.robustness(ds, ycol, xs)
        rb = robs["base"]
        steps = [
            dict(title="Data loaded", image=None, text_only=True,
                 big=f"{os.path.basename(ds.path)}\n"
                     f"{ds.n_rows} rows x {len(ds.num_names)} numeric columns",
                 note=(ds.drop_note() or "没有丢弃行") + "；"
                      + (ds.non_numeric_note() or "")),
            dict(title="Exploratory analysis", image=_fig("box.png"),
                 note=f"{len(eda['per_col'])} 个数值变量的分布；"
                      f"箱线图看中位数与离群点，不被极端值带偏"),
            dict(title="Response distribution", image=_fig("hist.png"),
                 note=f"目标 {mm.__dict__.get('_', '')} 均值 "
                      f"{float(ds.col(ycol).mean()):.4g}，"
                      f"标准差 {float(ds.col(ycol).std(ddof=1)):.4g}"),
            dict(title="Correlation structure", image=_fig("corr.png"),
                 note="相关系数接近 ±1 的变量对，其各自效应加性模型分不开"),
            dict(title="Model selection", image=None, text_only=True,
                 big=f"best: {best.get('label')}\n"
                     f"CV RMSE = {best.get('rmse'):.5f}"
                 if best.get("rmse") is not None else "no candidate",
                 note=f"{len(fitr.get('cands') or [])} 个候选结构，"
                      f"多折交叉验证比 RMSE"),
            dict(title="Fitted vs observed", image=_fig("pred.png"),
                 # 图里画的是**样本内** RMSE，摘要里报的是**交叉验证** RMSE，
                 # 两个数不一样。并排放而不标名字，观众会以为是同一个数 —— 必须写清楚。
                 note=(f"in-sample R^2 = {rb['r2']:.4f}；"
                       f"CV RMSE = {best.get('rmse'):.5f}"
                       f"（图内标注的是 in-sample RMSE，与 CV 值不同）")
                 if best.get("rmse") is not None else
                 f"in-sample R^2 = {rb['r2']:.4f}"),
            dict(title="Residual diagnostics", image=_fig("resid.png"),
                 note=f"Breusch-Pagan = {rb['bp']:.2f}"
                      f"（5% 临界 {rb['bp_crit']:.2f}）"
                      + ("，有异方差" if rb["bp"] > rb["bp_crit"]
                         else "，同方差")),
            dict(title="Normality check", image=_fig("qq.png"),
                 note="Q-Q 图看残差是否近似正态 —— t 检验成立的前提"),
            dict(title="Transformation robustness", image=None,
                 text_only=True,
                 big=f"{robs['n_stable']}/{robs['n_total']} stable",
                 note=("结论随尺度改变的是："
                       + "、".join(map(str, robs.get("flips") or []))
                       + "，这些不能单独当结论")
                      if robs.get("flips") else
                      "全部变量在 log/sqrt 尺度下符号与显著性一致"),
            dict(title="Sensitivity", image=_fig("sens.png"),
                 note="每个因子 ±1 标准差扰动，看目标响应变化幅度"),
            dict(title="Workflow", image=_fig("flow.png"),
                 note="从原始数据到结论的完整链路；每一步都留机器可读记录"),
        ]
        if missing:
            print(f"  ⚠ 缺 {len(missing)} 张图，对应帧将只有文字："
                  f"{'、'.join(missing[:6])}")
            print(f"    先用 mmkit plot --kind <类型> 生成到 {outdir}")
        frames = _video.build_frames([s for s in steps if s], hold=1)
        gif_path = a.out_gif or os.path.join(outdir, "flow.gif")
        r = _video.save_gif(frames, gif_path, ms=a.frame_ms)
        if not r.get("path"):
            print(f"  做不了：{r.get('why')}")
            return 2
        print(f"  GIF 已保存 {r['path']}"
              f"（{r['frames']} 帧，{r['bytes']} 字节）")
        mp4 = _video.save_mp4(frames, os.path.splitext(gif_path)[0] + ".mp4",
                              fps=2)
        if mp4.get("path"):
            print(f"  MP4 已保存 {mp4['path']}"
                  f"（{mp4['frames']} 帧，{mp4['bytes']} 字节）")
        else:
            print(f"  MP4 跳过：{mp4.get('why')}")
        return 0

    if a.cmd == "clean":
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        # 日期列可信性：A 题 Apr 文件把日期写成 2025-01-04（月份钉死 01），
        # 直接解析会让整年错位。必须在导出前就告诉用户。
        try:
            import openpyxl as _oxl
            _ext = os.path.splitext(str(path))[1].lower()
            if _ext in (".xlsx", ".xlsm"):
                _wb = _oxl.load_workbook(path, data_only=True)
                _ws = _wb[a.sheet] if a.sheet else _wb.active
                _col0 = [r[0] for r in _ws.iter_rows(
                    min_row=ds.header_row + 2, max_row=ds.header_row + 60,
                    values_only=True)]
                _h = mm.date_col_health(_col0, os.path.basename(path))
                if not _h["ok"]:
                    print("  ⚠ 日期列不可信：")
                    for _r in _h["reasons"]:
                        print(f"      · {_r}")
        except Exception:                               # noqa: BLE001
            pass
        out_csv = a.out_csv or "out/clean.csv"
        d = os.path.dirname(os.path.abspath(out_csv))
        if d:
            os.makedirs(d, exist_ok=True)
        # 只导出**数值列**且**行已对齐**的那部分 —— 这正是后面建模真正用的数据。
        # 导出原始表会让人以为被丢掉的行也参与了建模。
        with open(out_csv, "w", encoding="utf-8", newline="") as fh:
            fh.write(",".join('"' + n.replace('"', '""') + '"'
                              for n in ds.num_names) + "\n")
            for row in ds.M:
                fh.write(",".join(f"{v:.10g}" for v in row) + "\n")
        if ds.n_rows == 0 or not ds.num_names:
            print(f"  ✗ 导出失败：解析出 0 行可用数据 / 0 个数值列。")
            print(f"    写出的 {out_csv} 是空的，不要拿它继续分析。")
            print(f"    常见原因：所有列都被判成非数值（文本列 / 日期列），")
            print(f"    或数值列缺失率都超过 60%。")
            try:
                os.remove(out_csv)
                print(f"    已删除空文件 {out_csv}")
            except OSError:
                pass
            return 2
        print(f"  干净 CSV 已写入 {out_csv}"
              f"（{ds.n_rows} 行 × {len(ds.num_names)} 列）")
        if ds.dropped:
            print(f"  ⚠ 有 {ds.dropped} 行因为缺值没有进入这份 CSV —— "
                  f"建模用的就是这里的 {ds.n_rows} 行")
        # 同时导出一份列名映射，论文里的符号要对得上
        if a.names_out:
            with open(a.names_out, "w", encoding="utf-8",
                      newline="\n") as fh:
                fh.write("symbol,source_column,english\n")
                for i, n in enumerate(ds.num_names, 1):
                    en = _paper.describe(n)[0]
                    fh.write(f"x{i},{n},{en}\n")
            print(f"  列名映射已写入 {a.names_out}")
        return 0

    if a.cmd == "merge":
        # 数模题大量是「一月一个文件」「一天一个 sheet」。
        # 不支持合并，这类题根本进不去 —— 这是"任意一道题"的门槛。
        root = a.data or "."
        srcs = _ms.find_sources(root)
        if not srcs:
            print(f"{root!r} 下没找到可读的数据文件")
            print(f"  支持: {', '.join(_ms.SUPPORTED)}")
            return 2
        print(f"  找到 {len(srcs)} 个源:")
        for s in srcs[:12]:
            print(f"    {os.path.basename(s)}")
        if len(srcs) > 12:
            print(f"    … 另有 {len(srcs) - 12} 个")
        m = _ms.merge_paths(srcs, per_sheet=(a.sheet in ("all", "*")))
        print()
        print(_ms.report(m))
        print()
        # 列不一致必须点出来 —— 这是"两种表头"陷阱的铁证
        if m["n_cols"] > 0:
            print(f"  列并集 {m['n_cols']} 列（若各文件列名不一致，"
                  f"并集会大于单个文件的列数）")
        out_csv = a.out_csv or "out/merged.csv"
        d = os.path.dirname(os.path.abspath(out_csv))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(out_csv, "w", encoding="utf-8", newline="") as fh:
            fh.write(",".join('"' + str(c).replace('"', '""') + '"'
                              for c in m["header"]) + "\n")
            for row in m["rows"]:
                fh.write(",".join(_cell(v) for v in row) + "\n")
        print(f"  已写入 {out_csv}"
              f"（{m['n_rows']} 行 × {m['n_cols']} 列）")
        print(f"  下一步：mmkit.py run --data {out_csv} --y <目标> --x <因子>")
        return 0

    if a.cmd == "advise":
        # 模块一第一条是「定题」。在这之前插件只会"你让它算什么就算什么"，
        # 没人问一句"这道题到底该做回归吗"。
        path = a.data or mm.find_xlsx()
        if not path or not os.path.exists(path):
            print(f"找不到数据：{path!r}")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        ycol = ds.pick([a.y])[0] if a.y else None
        xs = ds.pick(a.x.split(",")) if a.x else []
        # 目标列要喂给 advise（第 106 轮）：不带它的话，
        # diagnose 看不见「这是一道要寻优的题」，永远只会说 explain。
        #
        # 注意别写成 `for _s in (a.min or "") + "," + (a.max or "")` ——
        # 那是**逐字符迭代**，一个目标名会被拆成等/待/时/间四个（第 106 轮实测）。
        _objs = []
        for _s in (a.min or "", a.max or ""):
            _objs += [x.strip() for x in str(_s).split(",") if x.strip()]
        _seen = set()
        _objs = [x for x in _objs if not (x in _seen or _seen.add(x))]
        r = _advise.diagnose(ds, ycol, xs, objectives=_objs,
                             statement=(a.problem or ""),
                             declared_kinds=[k for k in (a.types or "").split(",")
                                            if k.strip()])
        if a.json:
            _emit(json.dumps(r, ensure_ascii=False, indent=2, default=str))
            return 0
        KIND_CN = {"forecast": "时间序列预测", "explain": "关系与解释",
                   "evaluate": "综合评价", "optimize": "优化与决策",
                   "unclear": "信息不足，定不了题",
                   # 第 108 轮补：多标签与显式声明会带出这些名字，
                   # 之前没有中文映射，屏幕上直接显示英文。
                   "network": "网络与流", "simulation": "仿真与随机模拟",
                   "mechanism": "机理建模", "multiobjective": "多目标寻优",
                   "regression": "回归与解释", "optimization": "优化与决策",
                   "prediction": "预测与外推", "evaluation": "综合评价"}
        print()
        print("=" * 84)
        _ks = r.get("kinds") or [r["kind"]]
        print("定题结果：**%s**" % "、".join(KIND_CN.get(k, k) for k in _ks))
        if len(_ks) > 1:
            print("（主标签「%s」；题里还带目标列，所以优化那条路也要走）"
                  % KIND_CN.get(r["kind"], r["kind"]))
        print("=" * 84)
        print("  判断依据（每条都可复核）：")
        for e in r["evidence"]:
            print(f"    · {e}")
        print()
        print("  推荐方法链：")
        for i, c in enumerate(r["chains"], 1):
            print(f"    {i}. {c}")
        if r["risks"]:
            print()
            print("  ⚠ 风险：")
            for w in r["risks"]:
                print(f"    · {w}")
        print()
        print("  边界：这是**依据数据结构的建议**，不是对题意的理解。")
        print("        题意（要做几问、每问要什么）只有你能给。")
        return 0

    if a.cmd == "hints":
        path = a.data or mm.find_xlsx()
        if not path:
            print("找不到数据")
            return 2
        ds = mm.DS(path, a.sheet)
        _data_note(ds)
        if not a.y or not a.x:
            print("hints 需要 --y 和 --x")
            return 2
        ycol = ds.pick([a.y])[0]
        xs = ds.pick(a.x.split(","))
        hs = all_partial(ds, ycol, xs)
        if hs:
            print(f"n = {hs[0]['n']}   "
                  f"α=0.05 显著临界 |r| ≈ {hs[0]['r_crit']:.4f}   "
                  f"（样本越大临界越低，但显著 ≠ 重要）")
            print()
        for h in hs:
            pcs = "—" if h["pc"] is None else f"{h['pc']:+.4f}"
            d = {1: "正", -1: "负", 0: "—"}[h["sign"]]
            print(f"{h['name']:<24} 偏相关 {pcs:>8}  {d:<2}  {h['note']}")
        return 0

    return run(a.data, a.y,
               a.x.split(",") if a.x else [],
               a.claim,
               a.min.split(",") if a.min else [],
               a.max.split(",") if a.max else [],
               a.delta, a.reproduced, a.json, a.out,
               a.benefit.split(",") if a.benefit else [],
               a.cost.split(",") if a.cost else [],
               a.tex, a.team, a.problem,
                min_cols=a.min, lang=a.lang, strict=a.strict,
                   compile_pdf=a.compile, no_gate=a.no_gate,
               no_figs=getattr(a, "no_figs", False))


if __name__ == "__main__":
    raise SystemExit(main())
