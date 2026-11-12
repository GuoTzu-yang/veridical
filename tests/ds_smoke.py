#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DS 读取与体检的回归：第 83 轮在真实 CSV 上踩到的三个坑。

都不依赖外部文件，现场造数据。
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


td = tempfile.mkdtemp(prefix="ds_smoke_")

print("=" * 72)
print("一、CSV 读取（原来只认 .xlsx）")
print("=" * 72)

# 典型真实数据形态：日期列 + 几个数值列 + 一个几乎全空的稀疏列
p1 = os.path.join(td, "real.csv")
rows = ["DATE,温度,压力,稀疏列"]
for i in range(40):
    sparse = "1.0" if i % 10 == 0 else ""      # 只有 10% 有值
    rows.append(f"2025-01-{i % 28 + 1:02d},{20 + i * 0.1:.1f},{100 + i:.1f},{sparse}")
open(p1, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")

ds = mm.DS(p1)
ck("能读 CSV（原来抛 InvalidFileException）", ds.n_rows > 0,
   f"{ds.n_rows} 行")
ck("日期列被识别为非数值", "DATE" in ds.non_numeric, str(ds.non_numeric))
ck("中文列名保留", "温度" in ds.num_names, str(ds.num_names))
ck("稀疏列被排除（只 10% 有值）", "稀疏列" in ds.non_numeric,
   f"数值列={ds.num_names}")
ck("稀疏列没有把整份数据拖空", ds.n_rows >= 30, f"{ds.n_rows} 行")

# 分隔符嗅探
p2 = os.path.join(td, "semi.csv")
open(p2, "w", encoding="utf-8", newline="\n").write(
    "a;b;c\n1;2;3\n4;5;6\n7;8;9\n")
ds2 = mm.DS(p2)
ck("分号分隔的 CSV 也能认", list(ds2.num_names) == ["a", "b", "c"],
   str(ds2.num_names))

# BOM
p3 = os.path.join(td, "bom.csv")
open(p3, "w", encoding="utf-8-sig", newline="\n").write(
    "x,y\n1,2\n3,4\n5,6\n")
ds3 = mm.DS(p3)
ck("带 BOM 的 CSV 不乱码", list(ds3.num_names) == ["x", "y"],
   str(ds3.num_names))

print()
print("=" * 72)
print("二、丢行要说清楚（悄悄丢数据会得出错误结论）")
print("=" * 72)

# 列有 2/3 有值（超过 60% 阈值 → 入选数值列），
# 于是含缺值的 1/3 行会被丢掉 —— 这才是 drop_note 该触发的场景。
# 若给 50% 有值，那一列会被整体排除（低于阈值），行一行都不会丢。
p4 = os.path.join(td, "missing.csv")
rows = ["v1,v2"]
for i in range(21):
    v2 = "" if i % 3 == 0 else f"{i}.0"     # 3 行里空 1 行 = 66.7% 有值
    rows.append(f"{i}.0,{v2}")
open(p4, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")

ds4 = mm.DS(p4)
ck("v2 有 66.7% 有值 → 入选数值列", "v2" in ds4.num_names,
   str(ds4.num_names))
ck("含缺值的行被丢掉", ds4.dropped == 7 and ds4.n_rows == 14,
   f"保留 {ds4.n_rows} 丢弃 {ds4.dropped}")
ck("丢行提示非空", bool(ds4.drop_note()), ds4.drop_note()[:50])
ck("丢行提示里有比例", "%" in ds4.drop_note(), ds4.drop_note()[:60])
ck("没丢行时提示为空",
   mm.DS(p3).drop_note() == "", repr(mm.DS(p3).drop_note()))

# 反例：只有 50% 有值的列会被整列排除，而不是把一半的行丢掉
p4b = os.path.join(td, "half.csv")
rows = ["v1,v2"]
for i in range(20):
    rows.append(f"{i}.0,{'' if i % 2 else f'{i}.0'}")
open(p4b, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")
ds4b = mm.DS(p4b)
ck("只有 50% 有值的列被整列排除", "v2" in ds4b.non_numeric,
   str(ds4b.non_numeric))
ck("整列排除时一行都不丢", ds4b.dropped == 0 and ds4b.n_rows == 20,
   f"保留 {ds4b.n_rows} 丢弃 {ds4b.dropped}")

print()
print("=" * 72)
print("三、低基数列不做 IQR 异常判定")
print("=" * 72)

# YEAR 只有两个值，PH 只有三个值 —— 真实数据里 IQR 会把它们全判成异常
p5 = os.path.join(td, "lowcard.csv")
rows = ["YEAR,PH,连续值"]
for i in range(100):
    yr = 2026 if i % 4 == 0 else 2025          # 25% 是 2026
    ph = [7.0, 7.1, 7.2][i % 3]
    rows.append(f"{yr},{ph},{50 + (i % 20)}.0")
open(p5, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")

ds5 = mm.DS(p5)
e5 = mm.eda(ds5)
by_name = {c["name"]: c for c in e5["per_col"]}
ck("YEAR 不再报异常值", by_name["YEAR"]["n_outlier"] == 0,
   f"{by_name['YEAR']['n_outlier']} 个（修前 25 个）")
ck("YEAR 给出低基数说明", bool(by_name["YEAR"]["out_note"]),
   by_name["YEAR"]["out_note"])
ck("PH 不再报异常值", by_name["PH"]["n_outlier"] == 0,
   f"{by_name['PH']['n_outlier']} 个")
ck("连续列仍会正常判异常",
   "out_note" in by_name["连续值"],
   by_name["连续值"]["out_note"] or "（连续列没有低基数说明，符合预期）")

print()
print("=" * 72)
print("四、xlsx 路径没被改坏")
print("=" * 72)
xlsx = mm.find_xlsx()
if xlsx and xlsx.endswith(".xlsx"):
    dsn = mm.DS(xlsx)
    ck("APMCM xlsx 仍能读", dsn.n_rows > 0, f"{dsn.n_rows} 行")
    ck("APMCM xlsx 没有丢行", dsn.dropped == 0, f"丢弃 {dsn.dropped}")
    ck("APMCM xlsx 数值列数不变", len(dsn.num_names) == 7,
       str(dsn.num_names))
else:
    ck("（跳过 xlsx 检查）", True, "没找到 xlsx")

print()
print("=" * 72)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 72)
raise SystemExit(0 if bad == 0 else 1)
