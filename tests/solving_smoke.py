#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解题质量回归：用 A 题真实附件验证三个新检测。

这三个检测是第 88 轮实测出来的真缺陷：
  · TIME 被当数值列，还能被选成 --y（每步计算都对，模型毫无意义）
  · CLR 355 行里 354 个是 5.0，却被当成正常自变量
  · Apr 文件日期写成 2025-01-04（月份钉死 01），插件默默丢弃、不警告
"""
import os
import sys

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


A = os.path.abspath(os.path.join(
    HERE, "..", "apmcm2026", "题库", "2026中文-A_B_C三题",
    "A题 自来水厂水质预测与评估", "附件", "附件1  2025数据集"))

print("=" * 74)
print("一、时间列识别（TIME 不能当被解释变量）")
print("=" * 74)

apr = os.path.join(A, "JBALB_Apr2025.xlsx")
if os.path.exists(apr):
    ds = mm.DS(apr)
    tc = mm.time_cols(ds)
    ck("能识别出 TIME 是时间轴", "TIME" in tc, str(tc))
    ck("TIME 确实在数值列里（所以原来才会被误用）",
       "TIME" in ds.num_names, "这正是危险的来源")
    ck("CLR 不被误判成时间列", "CLR" not in tc, str(tc))
    ck("普通测量列不被误判",
       not any(k in tc for k in ("RIVER LEVEL", "R/W FLOW", "R/W NTU")),
       str(tc))

    print()
    print("=" * 74)
    print("二、准常数列（CLR 355 行里 354 个是 5.0）")
    print("=" * 74)
    dg = ds.degenerate_cols()
    ck("CLR 被判为准常数列", "CLR" in dg, str(dg))
    ck("正常变化列不被误判",
       "R/W NTU" not in dg and "RIVER LEVEL" not in dg, str(dg))
    # 验证 CLR 的真实分布
    import collections
    import numpy as np
    c = collections.Counter(np.round(ds.col("CLR"), 6).tolist())
    top = c.most_common(1)[0]
    ck("CLR 的最频值占比确实 > 90%",
       top[1] / ds.n_rows > 0.90, f"{top[0]} 占 {top[1]}/{ds.n_rows}")

    print()
    print("=" * 74)
    print("三、日期列可信性（Apr 写成 2025-01-04）")
    print("=" * 74)
    import openpyxl
    wb = openpyxl.load_workbook(apr, data_only=True)
    ws = wb.active
    col0 = [r[0] for r in ws.iter_rows(min_row=2, max_row=40,
                                       values_only=True)]
    h = mm.date_col_health(col0, os.path.basename(apr))
    ck("判出日期列不可信", h["ok"] is False, str(h["ok"]))
    ck("说清楚是月份/日号写反",
       any("写反" in r or "错位" in r for r in h["reasons"]),
       (h["reasons"] or [""])[0][:60])
    ck("提到文件名月份不符",
       any("4 月" in r for r in h["reasons"]),
       (h["reasons"] or [""])[0][:60])

    # 反例：正常的日期列应当判为可信
    good = [f"2025-04-{d:02d} 00:00:00" for d in range(1, 31)]
    hg = mm.date_col_health(good, "JBALB_Apr2025.xlsx")
    ck("正常日期列判为可信", hg["ok"] is True, str(hg["reasons"]))

    # 反例：整列同一天
    same = ["2025-01-04 00:00:00"] * 30
    hs = mm.date_col_health(same, "unknown.xlsx")
    ck("整列同一天判为不可信", hs["ok"] is False, str(hs["reasons"][:1]))

print()
print("=" * 74)
print("四、两种表头都能认（完整版 21 列 / 精简版 16 列）")
print("=" * 74)
for fn, want in (("JBALB_Jan2025.xlsx", 21), ("JBALB_May2025.xlsx", 16)):
    p = os.path.join(A, fn)
    if not os.path.exists(p):
        continue
    d = mm.DS(p)
    ck(f"{fn} 列数 {want}", len(d.names) == want, f"{len(d.names)} 列")
    ck(f"{fn} 表头在第 0 行", d.header_row == 0, str(d.header_row))

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
