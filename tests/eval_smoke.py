#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灰色关联度 / 模糊综合评价：拿能手算的数字对。

不手算就不算验证过。
"""
import os
import sys

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


print("=" * 76)
print("灰色关联度分析")
print("=" * 76)

# 手算用例：X 与参考完全相同 → 关联度 1
M = np.array([[1.0, 2.0, 3.0],
              [1.0, 2.0, 3.0]])
r = mm.grey_relational(M, ref=[1.0, 2.0, 3.0])
ck("与参考完全相同 → 关联度 = 1",
   np.allclose(r["grades"], 1.0), str(np.round(r["grades"], 6)))
ck("全相同会给「无区分力」警告", len(r["warn"]) > 0, r["warn"][0][:40])

# 手算用例：x0=[1,2,3]，x=[3,2,1]
# 均值化后 x0=[0.5,1,1.5] x=[1.5,1,0.5]
# Δ=[1,0,1]，Δmin=0 Δmax=1
# ξ=(0+0.5*1)/(Δ+0.5*1) = 0.5/(Δ+0.5) = [1/3, 1, 1/3]
# r = (1/3+1+1/3)/3 = 5/9 ≈ 0.55556
M2 = np.array([[3.0, 2.0, 1.0]])
r2 = mm.grey_relational(M2, ref=[1.0, 2.0, 3.0])
ck("反向序列关联度 = 5/9 ≈ 0.5556",
   abs(float(r2["grades"][0]) - 5 / 9) < 1e-9,
   f"{r2['grades'][0]:.6f} vs {5 / 9:.6f}")
ck("Δmin=0 Δmax=1", abs(r2["dmin"]) < 1e-9 and abs(r2["dmax"] - 1) < 1e-9,
   f"dmin={r2['dmin']:.4f} dmax={r2['dmax']:.4f}")
ck("关联系数是 [1/3, 1, 1/3]",
   np.allclose(r2["xi"][0], [1 / 3, 1.0, 1 / 3]),
   str(np.round(r2["xi"][0], 6)))

# 排序：三个方案，中间那个最像参考
M3 = np.array([[1.0, 2.0, 3.0],      # 完全相同 → 1.0
               [1.2, 2.2, 3.2],      # 接近
               [9.0, 9.0, 9.0]])     # 完全不像
r3 = mm.grey_relational(M3, ref=[1.0, 2.0, 3.0])
ck("排序：完全相同的排第一", int(r3["order"][0]) == 0,
   str(r3["order"]))
ck("排序：完全不像的排最后", int(r3["order"][-1]) == 2, str(r3["order"]))
ck("关联度随相似度单调下降",
   r3["grades"][0] > r3["grades"][1] > r3["grades"][2],
   str(np.round(r3["grades"], 4)))

# 方向：越小越好的指标
M4 = np.array([[1.0, 9.0],      # 指标1小(差)、指标2大(差)
               [9.0, 1.0]])     # 指标1大(好)、指标2小(好) → 正好是理想解
r4 = mm.grey_relational(M4, directions=[1, -1])
ck("方向 -1 时参考取「指标1最大、指标2最小」",
   r4["ref"][0] == 9.0 and r4["ref"][1] == 1.0, str(r4["ref"]))
# 方案 1 就是理想解本身 [9,1]，关联度必然是 1，排第一
ck("等于理想解的方案排第一且关联度为 1",
   int(r4["order"][0]) == 1 and abs(float(r4["grades"][1]) - 1.0) < 1e-9,
   f"order={r4['order']} grades={np.round(r4['grades'], 4)}")

# 归一化方式
for how in ("init", "mean", "range"):
    rr = mm.grey_relational(M3, ref=[1.0, 2.0, 3.0], normalize=how)
    ck(f"归一化 {how} 可运行且排序合理",
       int(rr["order"][0]) == 0 and int(rr["order"][-1]) == 2,
       str(rr["order"]))


def _raise(label, fn):
    try:
        fn()
        ck(label, False, "没抛异常")
    except Exception as e:
        ck(label, True, type(e).__name__)


_raise("未知归一化方式报错",
       lambda: mm.grey_relational(M3, normalize="nosuch"))
_raise("directions 长度不符报错",
       lambda: mm.grey_relational(M3, directions=[1, 1]))
_raise("ref 长度不符报错",
       lambda: mm.grey_relational(M3, ref=[1.0]))
_raise("一维输入报错", lambda: mm.grey_relational([1, 2, 3]))

print()
print("=" * 76)
print("模糊综合评价")
print("=" * 76)

# 手算用例
# W=[0.3,0.3,0.4]
# R=[[0.5,0.3,0.2],[0.4,0.4,0.2],[0.2,0.5,0.3]]
# 加权平均 B = W·R = [0.35, 0.41, 0.24]
W = [0.3, 0.3, 0.4]
R = [[0.5, 0.3, 0.2],
     [0.4, 0.4, 0.2],
     [0.2, 0.5, 0.3]]
r = mm.fuzzy_eval(W, R, operator="weighted")
ck("加权平均 B = [0.35, 0.41, 0.24]",
   np.allclose(r["B"], [0.35, 0.41, 0.24]), str(np.round(r["B"], 6)))
ck("B 已归一化（和为 1）", abs(r["Bn"].sum() - 1) < 1e-12,
   f"{r['Bn'].sum():.12f}")
ck("最大隶属落在第 2 等级", r["peak"] == 1, str(r["peak"]))

# 主因素决定 M(∧,∨): B_j = max_i min(W_i, R_ij)
# j=0: max(min(.3,.5), min(.3,.4), min(.4,.2)) = max(.3,.3,.2)=.3
# j=1: max(.3,.3,.4)=.4
# j=2: max(.2,.2,.3)=.3
rm = mm.fuzzy_eval(W, R, operator="maxmin")
ck("主因素决定 B = [0.3, 0.4, 0.3]",
   np.allclose(rm["B"], [0.3, 0.4, 0.3]), str(np.round(rm["B"], 6)))
ck("主因素算子会警告信息丢失",
   any("主导" in w for w in rm["warn"]), rm["warn"][-1][:44])

# 分值折算
r2 = mm.fuzzy_eval(W, R, grades=[95, 85, 75])
expect_score = 0.35 * 95 + 0.41 * 85 + 0.24 * 75
ck("综合得分按等级分值加权",
   abs(r2["score"] - expect_score) < 1e-9,
   f"{r2['score']:.4f} vs {expect_score:.4f}")

# 结论不明确
Rflat = [[0.34, 0.33, 0.33],
         [0.34, 0.33, 0.33],
         [0.32, 0.34, 0.34]]
rf = mm.fuzzy_eval([0.34, 0.33, 0.33], Rflat)
ck("最大隶属度 <0.4 时警告结论不明确",
   any("不明确" in w or "分不开" in w for w in rf["warn"]),
   str(np.round(rf["Bn"], 3)))

_raise("权重长度为 0 报错", lambda: mm.fuzzy_eval([], [[0.5]]))
_raise("权重长度不符报错", lambda: mm.fuzzy_eval([1.0], R))
_raise("隶属度越界报错",
       lambda: mm.fuzzy_eval([1.0], [[1.5]]))
_raise("负权重报错", lambda: mm.fuzzy_eval([-0.5, 1.5], [[0.5], [0.5]]))
_raise("未知算子报错", lambda: mm.fuzzy_eval(W, R, operator="nosuch"))
_raise("grades 长度不符报错",
       lambda: mm.fuzzy_eval(W, R, grades=[1, 2]))

print()
print("=" * 76)
print("CLI 入口（greyrel / fuzzy）")
print("=" * 76)

import subprocess  # noqa: E402

ENV = dict(os.environ)
ENV["PYTHONIOENCODING"] = "utf-8"
ENV["PYTHONUTF8"] = "1"


def run_cli(args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "mmkit.py")] + args,
                       capture_output=True, env=ENV, timeout=600)
    return r.returncode, (r.stdout or b"").decode("utf-8", "replace")


code, out = run_cli(["greyrel", "--matrix", "1,2,3;1.2,2.2,3.2;9,9,9",
                     "--ref", "1,2,3"])
ck("CLI greyrel 退出码 0", code == 0, f"exit={code}")
ck("CLI greyrel 第 1 名关联度为 1", "1.0000" in out)
ck("CLI greyrel 给出区分力判断", "有区分力" in out)

code, out = run_cli(["greyrel", "--matrix", "1,9;9,1",
                     "--directions", "1,-1"])
ck("CLI greyrel 支持方向（默认参考取理想解）",
   code == 0 and "理想解" in out, f"exit={code}")

code, out = run_cli(["fuzzy", "--weights", "0.3,0.3,0.4",
                     "--membership", "0.5,0.3,0.2;0.4,0.4,0.2;0.2,0.5,0.3",
                     "--grades", "95,85,75", "--names", "优,良,中"])
ck("CLI fuzzy 退出码 0", code == 0, f"exit={code}")
ck("CLI fuzzy 判定为良", "良" in out and "0.4100" in out)
ck("CLI fuzzy 综合得分 86.1", "86.1000" in out)
ck("CLI fuzzy 不泄漏 numpy 类型", "np.float64" not in out,
   "报告里不该出现 np.float64(...)")

code, out = run_cli(["fuzzy", "--ahp", "1,3,5|1/3,1,2|1/5,1/2,1",
                     "--membership", "0.5,0.3,0.2;0.4,0.4,0.2;0.2,0.5,0.3"])
ck("CLI fuzzy 可用 AHP 定权重", code == 0 and "权重来自 AHP" in out,
   f"exit={code}")

code, out = run_cli(["fuzzy", "--ahp", "1,3,1/3|1/3,1,3|3,1/3,1",
                     "--membership", "0.5,0.3,0.2;0.4,0.4,0.2;0.2,0.5,0.3"])
ck("CLI 矛盾 AHP 被拒绝定权重",
   code == 2 and "没通过一致性检验" in out, f"exit={code}")

print()
print("=" * 76)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 76)
raise SystemExit(0 if bad == 0 else 1)
