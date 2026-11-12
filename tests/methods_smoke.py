#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 AHP 与 GM(1,1) 的实现对不对 —— 用有已知答案的教科书的例子。

不拿已知答案对过，就不算实现完。
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import mm  # noqa: E402
import mmkit  # noqa: E402

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
print("AHP 层次分析法")
print("=" * 76)

# 经典 3 阶例子：几何平均法解析解
A = np.array([[1, 3, 5],
              [1 / 3, 1, 2],
              [1 / 5, 1 / 2, 1]], float)
r = mm.ahp(A, names=["安全性", "成本", "效率"])
print("  权重:", np.round(r["weights"], 4), " λmax=", round(r["lambda_max"], 4),
      " CR=", round(r["CR"], 4))
ck("权重和为 1", abs(r["weights"].sum() - 1) < 1e-12,
   f"{r['weights'].sum():.12f}")
# 手算：gm = [15^(1/3), (2/3)^(1/3), (1/10)^(1/3)] 归一化
gm = np.array([15 ** (1 / 3), (2 / 3) ** (1 / 3), 0.1 ** (1 / 3)])
expect = gm / gm.sum()
ck("权重与手算几何平均一致", np.allclose(r["weights"], expect),
   f"差 {np.abs(r['weights'] - expect).max():.2e}")
ck("第一个指标最重要", r["weights"][0] > r["weights"][1] > r["weights"][2],
   str(np.round(r["weights"], 3)))
# λmax 手算约 3.0039
ck("λmax ≈ 3.0039", abs(r["lambda_max"] - 3.0039) < 0.002,
   f"{r['lambda_max']:.4f}")
ck("CI ≈ 0.00195", abs(r["CI"] - 0.00195) < 0.001, f"{r['CI']:.5f}")
ck("CR < 0.1 判为一致", r["consistent"] is True, f"CR={r['CR']:.4f}")

# 故意造一个矛盾的矩阵：A>B, B>C, C>A
bad_A = np.array([[1, 3, 1 / 3],
                  [1 / 3, 1, 3],
                  [3, 1 / 3, 1]], float)
rb = mm.ahp(bad_A)
print("  矛盾矩阵: CR=", round(rb["CR"], 4), " consistent=", rb["consistent"])
ck("矛盾矩阵 CR ≥ 0.1", rb["CR"] >= 0.1, f"{rb['CR']:.4f}")
ck("矛盾矩阵判为不一致", rb["consistent"] is False)
ck("矛盾矩阵给出警告", len(rb["warn"]) > 0, rb["warn"][0][:40] if rb["warn"] else "")

# 正互反性检查
not_recip = np.array([[1, 2], [3, 1]], float)
rn = mm.ahp(not_recip)
ck("非正互反矩阵被指出", any("正互反" in w for w in rn["warn"]),
   rn["warn"][0][:50] if rn["warn"] else "")


def _ck_raise(label, fn):
    try:
        fn()
        ck(label, False, "没抛异常")
    except Exception as e:
        ck(label, True, type(e).__name__)


_ck_raise("含负数的矩阵报错",
          lambda: mm.ahp(np.array([[1, -2], [-0.5, 1]], float)))
_ck_raise("非方阵报错", lambda: mm.ahp(np.array([[1, 2, 3], [1, 1, 1]], float)))

print()
print("=" * 76)
print("GM(1,1) 灰色预测")
print("=" * 76)

# 刘思峰《灰色系统理论及其应用》经典例子
X = [2.874, 3.278, 3.337, 3.390, 3.679]
g = mmkit.gm11(X, horizon=3)
print(f"  a={g['a']:+.6f}  b={g['b']:.6f}  C={g['C']:.4f}  "
      f"P={g['P']:.3f}  等级={g['grade']}")
ck("GM 能跑通", g.get("ok") is True, str(g.get("why")))
# 教科书值：a = -0.0372, b = 3.0653
ck("发展系数 a ≈ -0.0372", abs(g["a"] - (-0.0372)) < 0.002,
   f"{g['a']:+.6f}")
ck("灰作用量 b ≈ 3.0653", abs(g["b"] - 3.0653) < 0.01, f"{g['b']:.6f}")
ck("拟合值贴近实测", np.max(np.abs(np.array(g["resid"]))) < 0.1,
   f"最大残差 {np.max(np.abs(np.array(g['resid']))):.4f}")
ck("后验差 C 在合格范围", g["C"] < 0.5, f"{g['C']:.4f}")
ck("精度等级不是不合格", g["grade"] != "不合格", g["grade"])
ck("外推是递增的（原序列递增）",
   all(g["fut"][i] < g["fut"][i + 1] for i in range(len(g["fut"]) - 1)),
   str([round(v, 4) for v in g["fut"]]))
ck("拟合首点等于实测首点", abs(g["fitted"][0] - X[0]) < 1e-9,
   f"{g['fitted'][0]:.6f} vs {X[0]}")

# 退化情况
ck("点数不足要拒绝", mmkit.gm11([1, 2, 3])["ok"] is False,
   mmkit.gm11([1, 2, 3]).get("why", ""))
ck("含 0 要拒绝", mmkit.gm11([1, 0, 2, 3, 4])["ok"] is False,
   mmkit.gm11([1, 0, 2, 3, 4]).get("why", ""))
ck("常数序列要拒绝", mmkit.gm11([2, 2, 2, 2, 2])["ok"] is False,
   mmkit.gm11([2, 2, 2, 2, 2]).get("why", ""))

# 常数递增序列（纯指数）应当拟合得极好
exp_seq = [np.exp(0.2 * k) for k in range(6)]
ge = mmkit.gm11(exp_seq, horizon=2)
ck("纯指数序列拟合精度为「好」", ge["grade"] == "好",
   f"C={ge['C']:.4f} P={ge['P']:.3f} 等级={ge['grade']}")
ck("纯指数外推接近真值",
   abs(ge["fut"][0] - np.exp(0.2 * 6)) / np.exp(1.2) < 0.02,
   f"预测 {ge['fut'][0]:.4f} vs 真值 {np.exp(1.2):.4f}")

# 震荡序列应当被判不合格或给出警告
osc = [1.0, 5.0, 1.2, 4.8, 1.4, 4.6]
go = mmkit.gm11(osc, horizon=2)
ck("震荡序列不给「好」",
   go.get("ok") and go["grade"] != "好",
   f"等级={go.get('grade')} C={go.get('C', 0):.3f}")

print()
print("=" * 76)
print("CLI 入口（ahp / grey / graph）")
print("=" * 76)

import subprocess  # noqa: E402

ENV = dict(os.environ)
ENV["PYTHONIOENCODING"] = "utf-8"
ENV["PYTHONUTF8"] = "1"


def run_cli(args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "mmkit.py")] + args,
                       capture_output=True, env=ENV, timeout=600)
    return r.returncode, (r.stdout or b"").decode("utf-8", "replace")


code, out = run_cli(["ahp", "--ahp", "1,3,5|1/3,1,2|1/5,1/2,1",
                     "--names", "安全性,成本,效率"])
ck("CLI ahp 退出码 0", code == 0, f"exit={code}")
ck("CLI ahp 给出权重", "0.6483" in out, "安全性 0.6483")
ck("CLI ahp 给出一致性结论", "通过一致性检验" in out)

code, out = run_cli(["ahp", "--ahp", "1,3,1/3|1/3,1,3|3,1/3,1"])
ck("CLI 矛盾矩阵退出码 0", code == 0, f"exit={code}")
ck("CLI 矛盾矩阵明确拒绝", "自相矛盾" in out, "CR ≥ 0.1")

code, out = run_cli(["grey", "--series", "2.874,3.278,3.337,3.390,3.679",
                     "--horizon", "3"])
ck("CLI grey 退出码 0", code == 0, f"exit={code}")
ck("CLI grey 给出 a 与 b", "发展系数" in out and "灰作用量" in out)
ck("CLI grey 给出后验差检验", "后验差比" in out and "小误差概率" in out)

code, out = run_cli(["graph", "--op", "dijkstra", "--edges",
                     "0-1:4,0-2:1,2-1:2,1-3:1,2-3:5", "--from", "0",
                     "--to", "3"])
ck("CLI dijkstra 退出码 0", code == 0, f"exit={code}")
ck("CLI dijkstra 距离 = 4", "4.000000" in out, "0-2-1-3")

code, out = run_cli(["graph", "--op", "mst", "--edges",
                     "0-1:1,1-2:3,0-2:2,2-3:4,0-3:5"])
ck("CLI mst 退出码 0", code == 0, f"exit={code}")
ck("CLI mst 权重 = 7", "7.000000" in out)

code, out = run_cli(["graph", "--op", "flow", "--edges",
                     "0-1:16,0-2:13,1-2:10,2-1:4,1-3:12,3-2:9,2-4:14,"
                     "4-3:7,3-5:20,4-5:4", "--from", "0", "--to", "5"])
ck("CLI flow 退出码 0", code == 0, f"exit={code}")
ck("CLI flow 最大流 = 23", "23.000000" in out, "CLRS 经典例")

code, out = run_cli(["graph", "--op", "tsp", "--matrix",
                     "0,1,1.41421356,1;1,0,1,1.41421356;"
                     "1.41421356,1,0,1;1,1.41421356,1,0"])
ck("CLI tsp 退出码 0（; 作行分隔符）", code == 0, f"exit={code}")
ck("CLI tsp 正方形周长 = 4", "4.000000" in out)

code, out = run_cli(["graph", "--op", "dijkstra", "--edges", "0-1:-1",
                     "--from", "0", "--to", "1"])
ck("CLI 负权被拒绝", code != 0 or "负权" in out, f"exit={code}")

print()
print("=" * 76)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 76)
raise SystemExit(0 if bad == 0 else 1)
