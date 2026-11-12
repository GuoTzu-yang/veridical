#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性加入：残差诊断 + 前沿计算过程。写完再统一编译。

② 残差诊断正式化
   题目要求「评估模型的拟合与预测效果」。原来只有 R² 和 CV 误差，
   残差层面没有结论。这一节给出：
       异方差   Breusch–Pagan 统计量 vs 卡方临界值（不用 p 值，
                避免为一句结论去实现分布函数）
       正态性   偏度、峰度、Jarque–Bera
       漏设曲率 残差与拟合值的相关（线性规格若真，该相关应接近 0）
       遗漏因子 残差与各自变量的相关

③ 前沿计算过程
   原来只给「前沿有 12 点」这个结论，读者无法核对。现在给出：
       算法（逐点判断是否被支配）
       前沿点坐标表
       一个具体的被支配例子：某设计被哪个设计支配、差多少
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① mm.diag_report / mm.front_detail ══
P1 = os.path.join(HERE, "mm.py")
s1 = open(P1, encoding="utf-8").read()
if "def diag_report(" not in s1:
    FUNC = '''

def diag_report(ds: DS, yname: str, xnames: list[str]) -> dict:
    """残差诊断：异方差、正态性、是否漏设曲率、是否遗漏因子。

    Breusch–Pagan 用「残差平方对自变量辅助回归的 R² × n」，
    临界值取卡方(df=k) 的 0.05 分位（k=3 → 7.81）。
    报统计量与临界值的比较而不是 p 值：一句话的结论不值得为它
    去实现一个卡方分布函数，而临界值本身是可核对的常数。
    """
    y = np.asarray(ds.col(yname), dtype=float)
    X = np.column_stack([np.asarray(ds.col(c), dtype=float)
                         for c in xnames])
    r = fit(ds, yname, xnames)
    kind = (r.get("best") or {}).get("kind") or "linear"
    A = design(X, kind)
    if A is None:
        return {}
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    e = y - A @ beta
    n = len(e)
    m = float(e.mean())
    s = float(e.std(ddof=1)) or 1e-12
    # 异方差：残差平方的辅助回归
    aux = np.column_stack([np.ones(n), X])
    ab, *_ = np.linalg.lstsq(aux, e ** 2, rcond=None)
    er = e ** 2 - aux @ ab
    bp = float(n * (1.0 - er.var() / (e ** 2).var())) if (e ** 2).var() > 0 else 0.0
    # 正态性
    skew = float(((e - m) ** 3).mean() / s ** 3)
    kurt = float(((e - m) ** 4).mean() / s ** 4)
    jb = float(n / 6.0 * (skew ** 2 + (kurt - 3.0) ** 2 / 4.0))
    # 漏设曲率：残差与拟合值的相关
    c_trend = (float(np.corrcoef(e, A @ beta)[0, 1])
               if (A @ beta).std() > 0 else 0.0)
    # 遗漏因子：残差与各自变量的相关
    c_each = []
    for i in range(X.shape[1]):
        v = X[:, i]
        c_each.append(float(np.corrcoef(e, v)[0, 1]) if v.std() > 0 else 0.0)
    return dict(y=yname, kind=kind, n=n,
                rmse=float(np.sqrt((e ** 2).mean())),
                r2=float(1.0 - e.var() / y.var()) if y.var() > 0 else 0.0,
                bp=bp, bp_crit=7.81,
                skew=skew, kurt=kurt, jb=jb,
                c_trend=c_trend, c_each=c_each, xnames=list(xnames))


def front_detail(M, minimize=None) -> dict:
    """前沿是怎么算出来的：前沿点、被支配的一个具体例子。

    给出例子是为了让读者能核对「非支配」这个判定：光说「12 点」
    无法核对，光说「第 37 号被第 45 号支配，压降差 0.004」可以。
    """
    A = np.asarray(M, dtype=float)
    if minimize is None:
        minimize = [True] * A.shape[1]
    idx = pareto_idx(A, minimize)
    S = A.copy()
    for j, mn in enumerate(minimize):
        if not mn:
            S[:, j] = -S[:, j]
    example = None
    for i in range(len(A)):
        if i in idx:
            continue
        dom = [k for k in idx
               if np.all(S[k] <= S[i] + 1e-12) and np.any(S[k] < S[i] - 1e-12)]
        if dom:
            k = dom[0]
            example = dict(i=i, dominated_by=k,
                           worse=[float(A[i, j] - A[k, j])
                                  for j in range(A.shape[1])],
                           coords_i=[float(v) for v in A[i]],
                           coords_k=[float(v) for v in A[k]])
            break
    return dict(front=[int(x) for x in idx], n_front=len(idx),
                n_total=len(A),
                coords=[[float(v) for v in A[i]] for i in idx],
                example=example)


'''
    k = s1.find("def print_fit(")
    s1 = s1[:k] + FUNC + s1[k:]
    ast.parse(s1)
    compile(s1, P1, "exec")
    open(P1, "w", encoding="utf-8", newline="\n").write(s1)
    print("① mm 加了 diag_report / front_detail")

# ══ ② mmkit ctx ══
P2 = os.path.join(HERE, "mmkit.py")
s2 = open(P2, encoding="utf-8").read()
if "_diag_ctx" not in s2:
    H = '''

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
            r = mm.diag_report(ds, yc, _xs)
            if r:
                d = _paper.describe(yc)
                r["y_en"] = d[0] if d else yc
                r["x_en"] = [_paper.describe(c)[0] if _paper.describe(c) else c
                             for c in _xs]
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
        return d
    except Exception:                               # noqa: BLE001
        return {}

'''
    k = s2.find("def _cond_scaled(")
    s2 = s2[:k] + H + s2[k:]
    s2 = s2.replace("            pred_int=_pi_ctx(ds, min_cols, xs),",
                    "            pred_int=_pi_ctx(ds, min_cols, xs),\n"
                    "            diag=_diag_ctx(ds, min_cols, xs),\n"
                    "            front_detail=_front_ctx(ds, min_cols),", 1)
    ast.parse(s2)
    compile(s2, P2, "exec")
    open(P2, "w", encoding="utf-8", newline="\n").write(s2)
    print("② mmkit 加了 diag / front_detail 的 ctx")
