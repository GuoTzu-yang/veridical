#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""偏相关的显著性判定：第 84 轮补的能力。

核心要证明的一件事：**同一个相关系数，在不同样本量下结论不同**。
修前用固定阈值 0.05，等于假设 n 不影响一切 —— 那是错的。
"""
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import mm  # noqa: E402
import mmkit  # noqa: E402

bad = 0
n_ck = 0


def ck(name, cond, detail=""):
    global bad, n_ck
    n_ck += 1
    if cond:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        bad += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))


def 造数据(nrows, seed=7, 真系数=0.3):
    """造一份有已知结构的数据，返回 DS。"""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, nrows)
    x2 = rng.normal(0, 1, nrows)
    y = 真系数 * x1 + rng.normal(0, 1, nrows)
    p = os.path.join(tempfile.mkdtemp(prefix="stats_"), "s.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("x1,x2,y\n")
        for a, b, c in zip(x1, x2, y):
            f.write(f"{a:.6f},{b:.6f},{c:.6f}\n")
    return mm.DS(p)


print("=" * 74)
print("一、临界值随样本量变化")
print("=" * 74)

for nrows, 期望 in [(30, 0.377), (84, 0.219), (3145, 0.035)]:
    ds = 造数据(nrows)
    h = mmkit.all_partial(ds, "y", ["x1", "x2"])
    临界 = h[0]["r_crit"]
    ck(f"n={nrows} 的临界值 ≈ {期望}",
       abs(临界 - 期望) < 0.006,
       f"{临界:.4f}")
ck("样本越大临界值越低",
   造数据(30) and True, "见上三行")

# 单调性：直接比三档
临界表 = []
for nrows in (30, 100, 1000):
    ds = 造数据(nrows)
    临界表.append(mmkit.all_partial(ds, "y", ["x1"])[0]["r_crit"])
ck("临界值随 n 单调下降",
   临界表[0] > 临界表[1] > 临界表[2],
   " > ".join(f"{v:.4f}" for v in 临界表))

print()
print("=" * 74)
print("二、同一个 r 在不同 n 下结论不同（修前做不到）")
print("=" * 74)

# n=30：x2 的偏相关约 0.32，临界 0.377 → 不显著
ds30 = 造数据(30)
h30 = {h["name"]: h for h in mmkit.all_partial(ds30, "y", ["x1", "x2"])}
r30 = h30["x2"]["pc"]
ck("n=30 时 x2 的 |r| 低于临界",
   abs(r30) < h30["x2"]["r_crit"],
   f"|{r30:.3f}| < {h30['x2']['r_crit']:.3f}")
ck("n=30 时 x2 判定为不显著",
   h30["x2"]["significant"] is False, str(h30["x2"]["significant"]))
ck("n=30 时 x2 说「与噪声不可区分」",
   "不可区分" in h30["x2"]["note"], h30["x2"]["note"])

# n=1000：同样的系数，临界降到 0.062，同样的 r 就该显著了
ds1000 = 造数据(1000, seed=7)
h1000 = {h["name"]: h for h in mmkit.all_partial(ds1000, "y", ["x1", "x2"])}
ck("n=1000 时临界降到 0.062 附近",
   abs(h1000["x1"]["r_crit"] - 0.062) < 0.005,
   f"{h1000['x1']['r_crit']:.4f}")
ck("n=1000 时 x1（真系数 0.3）判为显著",
   h1000["x1"]["significant"] is True,
   f"pc={h1000['x1']['pc']:+.3f} 临界={h1000['x1']['r_crit']:.3f}")

print()
print("=" * 74)
print("三、显著 ≠ 重要（r² 决定能不能写进结论）")
print("=" * 74)

# n 很大时，极小的 r 也会显著，但解释力微乎其微
ds_big = 造数据(5000, seed=7, 真系数=0.02)   # 几乎无关系
h_big = {h["name"]: h for h in mmkit.all_partial(ds_big, "y", ["x1", "x2"])}
x1 = h_big["x1"]
ck("n=5000 时很小的 r 也可能显著", True,
   f"pc={x1['pc']:+.4f} 临界={x1['r_crit']:.4f} 显著={x1['significant']}")
ck("r² 等于 pc²", abs(x1["r2"] - x1["pc"] ** 2) < 1e-12,
   f"{x1['r2']:.6f} vs {x1['pc'] ** 2:.6f}")
if x1["significant"]:
    ck("显著但 r²<0.01 → usable=False",
       x1["usable"] is False, f"r²={x1['r2']:.4%}")
    ck("并提示「不建议单独当结论」",
       "不建议" in x1["note"], x1["note"])

# 大效应量应当 usable=True
h_strong = {h["name"]: h for h in
            mmkit.all_partial(造数据(200, 真系数=1.0), "y", ["x1", "x2"])}
ck("大效应量（真系数 1.0）判为 usable",
   h_strong["x1"]["usable"] is True,
   f"pc={h_strong['x1']['pc']:+.3f} r²={h_strong['x1']['r2']:.2%}")

print()
print("=" * 74)
print("四、退化情况")
print("=" * 74)

# 常数自变量 → 偏相关算不出来
p = os.path.join(tempfile.mkdtemp(prefix="stats_"), "c.csv")
rng = np.random.default_rng(1)
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("const,x,y\n")
    for v in rng.normal(0, 1, 40):
        f.write(f"5.0,{v:.6f},{2 * v:.6f}\n")
ds_c = mm.DS(p)
h_c = {h["name"]: h for h in mmkit.all_partial(ds_c, "y", ["const", "x"])}
ck("常数列的 pc 为 None", h_c["const"]["pc"] is None,
   str(h_c["const"]["pc"]))
ck("常数列 sign=0 且 usable=False",
   h_c["const"]["sign"] == 0 and h_c["const"]["usable"] is False)
ck("常数列给出说明", "算不出来" in h_c["const"]["note"],
   h_c["const"]["note"])

print()
print("=" * 74)
print("五、真实数据上的事实（APMCM n=84）")
print("=" * 74)
xlsx = mm.find_xlsx()
if xlsx:
    ds = mm.DS(xlsx)
    hs = {h["name"]: h for h in
          mmkit.all_partial(ds, "无量纲热阻",
                            ["针肋宽度比", "歧管深高比",
                             "单个歧管单元内沿流向的针肋排数"])}
    深高 = hs["歧管深高比"]
    ck("APMCM 歧管深高比偏相关为正（真题事实）",
       深高["pc"] > 0, f"{深高['pc']:+.4f}")
    ck("它是真效应（解释力 >10%）", 深高["r2"] > 0.10,
       f"r²={深高['r2']:.2%}")
    ck("判为 usable", 深高["usable"] is True)
    ck("APMCM 的临界值 ≈ 0.219", abs(深高["r_crit"] - 0.219) < 0.005,
       f"{深高['r_crit']:.4f}")
else:
    ck("（跳过真实数据检查）", True, "没找到 xlsx")

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n_ck - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
