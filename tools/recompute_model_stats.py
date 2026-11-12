"""重算 DWTS 论文的模型统计量（替代 build_evidence.py 里的 6 行硬编码）。

原 build_evidence.py 第 42-47 行把 cv_rmse_quad / cv_rmse_lin / cv_gap /
eps_floor / strong_assumption_* 直接写成字面量，导致「以计算结果形态记录的
手写数字」。本脚本按论文第 455-464 行描述的做法真正计算：

  - 重复交叉验证（10 折 × 10 种子），linear vs quadratic
  - Breusch-Pagan（n * R²，残差平方对 X 辅助回归）
  - HC3 稳健标准误
  - 表 tab:pi 的三档 profile 预测值与 95% 区间

输出 out/d2026c/model_stats.json，供 build_evidence.py 与 paper.tex 取用。
"""
import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")
OUT = os.path.join(HERE, "out", "d2026c")

COLS = ["judge_avg", "age", "n_weeks"]


def design(X, quad):
    cols = [np.ones(len(X))]
    cols += [X[:, i] for i in range(X.shape[1])]
    if quad:
        cols += [X[:, i] ** 2 for i in range(X.shape[1])]
    return np.column_stack(cols)


def cv_rmse(Xd, y, k=10, seeds=range(10)):
    vals = []
    for s in seeds:
        idx = np.random.RandomState(s).permutation(len(y))
        errs = []
        for f in np.array_split(idx, k):
            tr = np.setdiff1d(idx, f)
            beta, *_ = np.linalg.lstsq(Xd[tr], y[tr], rcond=None)
            errs.append(y[f] - Xd[f] @ beta)
        e = np.concatenate(errs)
        vals.append(float(np.sqrt((e ** 2).mean())))
    return float(np.mean(vals)), float(np.std(vals))


def bp_stat(Xd, y):
    """Breusch-Pagan LM 统计量：n * R²，残差平方对 X 的辅助回归。"""
    beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    e = y - Xd @ beta
    e2 = e ** 2
    b2, *_ = np.linalg.lstsq(Xd, e2, rcond=None)
    r = e2 - Xd @ b2
    r2 = 1 - (r ** 2).sum() / ((e2 - e2.mean()) ** 2).sum()
    return float(len(y) * r2)


def chi2_df3_sf(x):
    """χ²(3) 生存函数闭式：2(1-Φ(√x)) + √(2x/π)·e^{-x/2}。"""
    tail = 2 * (1 - 0.5 * (1 + math.erf(math.sqrt(x / 2))))
    tail += math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    return float(tail)


def hc3(Xd, y):
    """HC3 稳健协方差，返回 (se, t_ratio)。"""
    n, k = Xd.shape
    XtX_inv = np.linalg.inv(Xd.T @ Xd)
    beta = XtX_inv @ Xd.T @ y
    e = y - Xd @ beta
    h = np.einsum("ij,jk,ik->i", Xd, XtX_inv, Xd)
    u = (e / (1 - h)) ** 2
    V = XtX_inv @ (Xd.T @ (Xd * u[:, None])) @ XtX_inv
    se = np.sqrt(np.diag(V))
    return beta, se, beta / se


def ridge_cv(Xd, y, lam, k=10, seeds=range(10)):
    """岭回归的重复 CV（不惩罚截距那一列）。"""
    vals = []
    pen = np.eye(Xd.shape[1]) * lam
    pen[0, 0] = 0.0
    for s in seeds:
        idx = np.random.RandomState(s).permutation(len(y))
        errs = []
        for f in np.array_split(idx, k):
            tr = np.setdiff1d(idx, f)
            A = Xd[tr].T @ Xd[tr] + pen
            beta = np.linalg.solve(A, Xd[tr].T @ y[tr])
            errs.append(y[f] - Xd[f] @ beta)
        e = np.concatenate(errs)
        vals.append(float(np.sqrt((e ** 2).mean())))
    return float(np.mean(vals)), float(np.std(vals))


def spearman(a, b):
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def sensitivity(df):
    """响应做 log / sqrt 变换后，各预测子的符号与秩是否保持。"""
    rows = []
    y = df["placement"].to_numpy(float)
    for c in COLS:
        x = df[c].to_numpy(float)
        base = spearman(x, y)
        rho_log = spearman(x, np.log(y))
        rho_sqrt = spearman(x, np.sqrt(y))
        keep = (np.sign(base) == np.sign(rho_log) == np.sign(rho_sqrt))
        rows.append(dict(col=c, rho=round(base, 3),
                         rho_log=round(rho_log, 3),
                         rho_sqrt=round(rho_sqrt, 3),
                         sign_kept=bool(keep)))
    return rows


def main():
    df = pd.read_excel(os.path.join(D, "dwts2026c.xlsx"))
    y = df["placement"].to_numpy(float)
    X0 = df[COLS].to_numpy(float)

    lin, lin_sd = cv_rmse(design(X0, False), y)
    quad, quad_sd = cv_rmse(design(X0, True), y)

    Xl = design(X0, False)
    bp = bp_stat(Xl, y)
    p_bp = chi2_df3_sf(bp)

    beta, se, t = hc3(Xl, y)

    # 三档 profile：age 取 25/50/75 分位，n_weeks 取中位数
    q_age = df["age"].quantile([0.25, 0.5, 0.75]).to_numpy(float)
    med_weeks = float(df["n_weeks"].median())
    profiles = [
        ("High-scoring, young", 8.5, q_age[0]),
        ("Mid-range, mid-age", 7.2, q_age[1]),
        ("Low-scoring, older", 6.0, q_age[2]),
    ]
    half = 1.96 * lin
    pi = []
    for name, judge, age in profiles:
        x0 = np.array([1.0, judge, age, med_weeks])
        hat = float(x0 @ beta)
        pi.append(dict(name=name, judge=judge, age=round(float(age), 1),
                       n_weeks=med_weeks, pred=round(hat, 1),
                       lo=round(hat - half, 1), hi=round(hat + half, 1)))

    r1, r1sd = ridge_cv(Xl, y, 1.0)
    r10, r10sd = ridge_cv(Xl, y, 10.0)
    sens = sensitivity(df)
    kept = sum(1 for r in sens if r["sign_kept"])

    out = dict(
        cols=COLS,
        n=int(len(y)),
        cv_rmse_ridge1=round(r1, 4), cv_rmse_ridge1_sd=round(r1sd, 4),
        cv_rmse_ridge10=round(r10, 4), cv_rmse_ridge10_sd=round(r10sd, 4),
        sensitivity=sens, sensitivity_sign_kept=kept,
        cv_rmse_lin=round(lin, 4), cv_rmse_lin_sd=round(lin_sd, 4),
        cv_rmse_quad=round(quad, 4), cv_rmse_quad_sd=round(quad_sd, 4),
        cv_gap=round(abs(quad - lin), 4),
        bp=round(bp, 2), bp_df=3, bp_p=round(p_bp, 4),
        bp_reject_at_05=bool(p_bp < 0.05),
        hc3_se={c: round(float(s), 4) for c, s in zip(["const"] + COLS, se)},
        hc3_t={c: round(float(v), 3) for c, v in zip(["const"] + COLS, t)},
        pi_half_width=round(half, 3),
        pi=pi,
        note=("由 tools/recompute_model_stats.py 实算；"
              "替换 build_evidence.py 原第 42-44 行的硬编码"),
    )

    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "model_stats.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\nwritten:", p)


if __name__ == "__main__":
    main()
