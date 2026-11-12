#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变换稳健性检验：第 84 轮补。

要证明的核心：
  1. R² 会被报出来（原来只报 RMSE，用户无法判断模型有没有用）
  2. 结论对 y 尺度敏感时会被抓出来（实测水厂数据 6 个变量里翻了 2 个）
  3. 它的判定与手工 OLS 一致
"""
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import mm  # noqa: E402

bad = 0
n = 0


def ck(name, cond, detail=""):
    global bad, n
    n += 1
    if cond:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        bad += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))


def 造(y, xs):
    """把数组写成 CSV 并读回来成 DS。"""
    p = os.path.join(tempfile.mkdtemp(prefix="rob_"), "d.csv")
    cols = list(xs.keys()) + ["y"]
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(",".join(cols) + "\n")
        for i in range(len(y)):
            f.write(",".join(f"{xs[c][i]:.8f}" for c in xs)
                    + f",{y[i]:.8f}\n")
    return mm.DS(p)


print("=" * 74)
print("一、ols_summary 与手算一致")
print("=" * 74)

rng = np.random.default_rng(3)
N = 200
x1 = rng.normal(0, 1, N)
x2 = rng.normal(0, 1, N)
y = 2.0 + 1.5 * x1 - 0.7 * x2 + rng.normal(0, 1, N)
ds = 造(y, {"x1": x1, "x2": x2})
X = ds.cols(["x1", "x2"])
Y = ds.col("y")
st = mm.ols_summary(X, Y, ["x1", "x2"])

ck("截距与系数贴近真值",
   abs(st["beta"][0] - 2.0) < 0.2 and abs(st["beta"][1] - 1.5) < 0.2
   and abs(st["beta"][2] + 0.7) < 0.2,
   "  ".join(f"{b:+.3f}" for b in st["beta"]))

# 手算 R²
A = np.hstack([np.ones((N, 1)), X])
b_hat = np.linalg.lstsq(A, Y, rcond=None)[0]
res = Y - A @ b_hat
r2_manual = 1 - np.sum(res ** 2) / np.sum((Y - Y.mean()) ** 2)
ck("R² 与手算一致", abs(st["r2"] - r2_manual) < 1e-10,
   f"{st['r2']:.6f} vs {r2_manual:.6f}")
ck("R² 接近真模型（约 0.7）", st["r2"] > 0.6, f"{st['r2']:.4f}")
ck("BP 临界值按 k 查表（k=2 → 5.99）",
   abs(st["bp_crit"] - 5.99) < 1e-9, str(st["bp_crit"]))
ck("同方差数据 BP 低于临界", st["bp"] < st["bp_crit"],
   f"BP={st['bp']:.2f} < {st['bp_crit']:.2f}")

print()
print("=" * 74)
print("二、构造一个结论会翻转的数据")
print("=" * 74)

# x_small 的效应在原尺度是正的，取对数后变负 —— 造一个能触发的场景
rng = np.random.default_rng(11)
N2 = 400
xa = rng.uniform(0.1, 3.0, N2)
xb = rng.normal(0, 1, N2)
# y 由 exp 结构生成：log(y) 与 xa 正相关，但 y 本身与 xa 的关系被曲率掩盖
y2 = np.exp(0.8 * xa - 0.5 * xb + rng.normal(0, 0.3, N2)) * 0.5
ds2 = 造(y2, {"xa": xa, "xb": xb})
r = mm.robustness(ds2, "y", ["xa", "xb"])

ck("稳健性函数能跑", r.get("base") is not None,
   f"{r['n_stable']}/{r['n_total']} 稳")
ck("同时给出了原尺度和 log 尺度",
   len(r["variants"]) >= 2 and r["variants"][0]["name"] == "原尺度",
   str([v["name"] for v in r["variants"]]))
ck("每行都有 cells", all(len(row["cells"]) == len(r["variants"])
                          for row in r["rows"]))
# exp 结构下，xa 在 log 尺度应当更显著
xa_row = next(row for row in r["rows"] if row["name"] == "xa")
t_raw = abs(xa_row["cells"][0]["t"])
t_log = abs(xa_row["cells"][1]["t"])
ck("log 尺度下 xa 的 t 值更大（exp 结构被拉直）", t_log > t_raw,
   f"原 {t_raw:.2f} vs log {t_log:.2f}")

print()
print("=" * 74)
print("三、警告会如实给出")
print("=" * 74)

# 全部同值的 y：R² 无意义、必然报警告
p = os.path.join(tempfile.mkdtemp(prefix="rob_"), "flat.csv")
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("x,y\n")
    for i in range(50):
        f.write(f"{i % 7}.0,3.0\n")
ds_flat = mm.DS(p)
r_flat = mm.robustness(ds_flat, "y", ["x"])
ck("y 全同值时给警告", len(r_flat["warn"]) > 0,
   r_flat["warn"][0][:50] if r_flat["warn"] else "无警告")

# R² 很低时必须有警告
rng = np.random.default_rng(5)
N3 = 300
xn = rng.normal(0, 1, N3)
yn = rng.normal(0, 1, N3)          # 与 x 完全无关
ds_n = 造(yn, {"xn": xn})
r_n = mm.robustness(ds_n, "y", ["xn"])
ck("无关变量的 R² 很低", r_n["base"]["r2"] < 0.1,
   f"{r_n['base']['r2']:.2%}")
ck("R² 低时明确警告「不该单独当结论」",
   any("R²" in w and "不该单独" in w for w in r_n["warn"]),
   [w[:40] for w in r_n["warn"]])

print()
print("=" * 74)
print("四、真实数据上的事实（水厂 3145 行）")
print("=" * 74)
WATER = os.path.abspath(os.path.join(HERE, "..", "apmcm2026", "data",
                                     "water_clean.csv"))
if os.path.exists(WATER):
    dsw = mm.DS(WATER)
    rw = mm.robustness(dsw, "FILT. NTU",
                       ["R/W NTU", "R/W CLR", "R/W FLOW", "RIVER LEVEL",
                        "ALUM", "CL2"])
    ck("水厂数据 R² 很低（<10%）", rw["base"]["r2"] < 0.10,
       f"{rw['base']['r2']:.2%}")
    ck("水厂数据 BP 判出异方差", rw["base"]["bp"] > rw["base"]["bp_crit"],
       f"{rw['base']['bp']:.1f} > {rw['base']['bp_crit']:.1f}")
    翻转 = [row["name"] for row in rw["rows"] if not row["stable"]]
    ck("抓到有变量结论翻转", len(翻转) > 0, f"{len(翻转)} 个：{翻转}")
    ck("ALUM 在翻转名单里", "ALUM" in 翻转, str(翻转))
    ck("翻转变量被写进警告",
       any("尺度改变" in w for w in rw["warn"]),
       [w[:46] for w in rw["warn"] if "尺度" in w])
else:
    ck("（跳过真实数据）", True, "没有 water_clean.csv")

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
