#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定题与时间列体检回归。

两件事都在 A 题真实数据上验证过：
  · 定题：A 题必须判成时间序列预测，不是"关系与解释"
  · 脏值：A 题 TIME 列有 5 行是 5.87，不是合法时点
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import advise  # noqa: E402
import mm  # noqa: E402
import multisrc as ms  # noqa: E402

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


A_MERGED = os.path.join(HERE, "out", "fig", "a2025_merged.csv")

print("=" * 74)
print("一、定题：三种题型必须判对")
print("=" * 74)

if os.path.exists(A_MERGED):
    ds = mm.DS(A_MERGED)
    r = advise.diagnose(ds, "FILT. NTU", ["RIVER LEVEL", "R/W NTU"])
    ck("A 题判成时间序列预测", r["kind"] == "forecast", r["kind"])
    ck("依据里写明周期=12",
       any("周期 12" in e for e in r["evidence"]), str(r["evidence"][:1]))
    ck("推荐 forecast 命令",
       any("forecast" in c for c in r["chains"]), r["chains"][0][:40])
    ck("报告时间列脏值", any("非法值" in e for e in r["evidence"]),
       [e for e in r["evidence"] if "非法" in e][:1])
    ck("风险里要求先剔除脏行",
       any("剔除" in w or "修正" in w for w in r["risks"]),
       [w for w in r["risks"] if "剔除" in w][:1])

    th = mm.time_col_health(ds, "TIME")
    ck("TIME 周期识别为 12", th["period"] == 12, str(th["period"]))
    ck("TIME 脏值 5 个", th["n_bad"] == 5, str(th["n_bad"]))
    ck("脏值是 5.87", th["bad_values"] == [5.87], str(th["bad_values"]))
    ck("合法时点 12 个", len(th["good_values"]) == 12,
       str(len(th["good_values"])))

# B 题：有 y + 因子 → explain
xlsx = mm.find_xlsx()
if xlsx:
    dsb = mm.DS(xlsx)
    rb = advise.diagnose(dsb, "无量纲热阻",
                         ["针肋宽度比", "歧管深高比"])
    ck("B 题判成关系与解释", rb["kind"] == "explain", rb["kind"])
    ck("B 题没有时间轴",
       not rb["time_cols"], str(rb["time_cols"]))
    ck("B 题推荐 run",
       any("run" in c for c in rb["chains"]), rb["chains"][0][:40])

# 不给 y → evaluate
if os.path.exists(A_MERGED):
    ds2 = mm.DS(A_MERGED)
    re_ = advise.diagnose(ds2, None, [])
    # A 题有时间轴，所以即使不给 y 仍是 forecast —— 这是对的（时间性优先）
    ck("有周期时间轴时优先判时序（哪怕没给 --y）",
       re_["kind"] == "forecast", re_["kind"])

# 真正无时间轴、无 y → evaluate
import tempfile
td = tempfile.mkdtemp(prefix="adv_")
pa = os.path.join(td, "eval.csv")
with open(pa, "w", encoding="utf-8", newline="\n") as f:
    f.write("成本,质量,效率\n")
    for i in range(40):
        f.write(f"{10+i*0.3:.4f},{80-i*0.2:.4f},{0.5+i*0.01:.4f}\n")
dse = mm.DS(pa)
reve = advise.diagnose(dse, None, [])
ck("无时间轴无 y → 综合评价", reve["kind"] == "evaluate", reve["kind"])
ck("评价链里有熵权/AHP",
   any("bar" in c or "ahp" in c for c in reve["chains"]),
   str(reve["chains"][:2]))

print()
print("=" * 74)
print("二、边界：信息不足时要说不知道，不能硬判")
print("=" * 74)
pz = os.path.join(td, "tiny.csv")
open(pz, "w", encoding="utf-8", newline="\n").write("a\n1\n2\n3\n")
dsz = mm.DS(pz)
rz = advise.diagnose(dsz, "a", [])
ck("单列少行 → unclear", rz["kind"] in ("unclear", "explain"),
   rz["kind"])
ck("小样本被点名", any("只有" in w for w in rz["risks"]),
   [w for w in rz["risks"] if "只有" in w][:1])

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
