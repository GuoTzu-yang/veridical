#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多源读取回归：A 题是「任意一道题」的门槛。

判据不是我拍脑袋定的，是 apmcm2026/02-A题实战记录里逐文件核过的：
  附件1 = 12 个 xlsx = 4380 行
  附件2 = 3 个 xls / 90 个 sheet = 1080 行
  每月行数 = 该月天数 × 12
数字对不上就说明合并逻辑错了。
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

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


BASE = os.path.abspath(os.path.join(
    HERE, "..", "apmcm2026", "题库", "2026中文-A_B_C三题",
    "A题 自来水厂水质预测与评估", "附件"))
D1 = os.path.join(BASE, "附件1  2025数据集")
D2 = os.path.join(BASE, "附件2  2026数据集")

print("=" * 74)
print("一、附件1：12 个 xlsx 合并 = 4380 行（实战记录事实）")
print("=" * 74)
if os.path.isdir(D1):
    srcs = ms.find_sources(D1)
    ck("找到 12 个源", len(srcs) == 12, f"{len(srcs)} 个")
    m = ms.merge_paths(srcs)
    ck("全部读取成功", m["n_ok"] == 12, f"{m['n_ok']}/12")
    ck("总行数 = 4380", m["n_rows"] == 4380, f"{m['n_rows']} 行")
    # 列并集 > 21 说明两种表头确实不同（陷阱 1 的直接证据）
    ck("列并集 > 21（两种表头并存）", m["n_cols"] > 21,
       f"{m['n_cols']} 列 vs 单文件最多 21 列")
    # 每月行数 = 天数 × 12
    for fn, want in (("JBALB_Jan2025.xlsx", 372), ("JBALB_Feb2025.xlsx", 336),
                     ("JBALB_Apr2025.xlsx", 360),
                     ("JBALB_May2025.xlsx", 372)):
        f = next((x for x in m["files"]
                  if x["path"] == fn), None)
        if f:
            ck(f"{fn} = {want} 行（天数×12）", f["rows"] == want,
               f"{f['rows']} 行")
    # 精简版文件确实是 16 列
    may = next((x for x in m["files"] if x["path"] == "JBALB_May2025.xlsx"),
               None)
    ck("May 是精简版（16 列）", may and may["cols"] == 16,
       f"{may['cols'] if may else '?'} 列")
else:
    ck("（附件1 目录不存在，跳过）", True, "")

print()
print("=" * 74)
print("二、附件2：3 个 .xls / 90 个 sheet = 1080 行")
print("=" * 74)
if os.path.isdir(D2):
    srcs2 = ms.find_sources(D2)
    ck("找到 3 个 .xls", len(srcs2) == 3, str(len(srcs2)))
    ck("后缀确实是 .xls（openpyxl 读不了）",
       all(s.lower().endswith(".xls") for s in srcs2),
       os.path.basename(srcs2[0]) if srcs2 else "")
    # sheet 数
    names = ms.sheet_names(srcs2[0])
    ck("单文件 31 个 sheet（1 月 31 天）", len(names) == 31, str(len(names)))
    m2 = ms.merge_paths(srcs2, per_sheet=True)
    ck("总行数 = 1080（90 天 × 12）", m2["n_rows"] == 1080,
       f"{m2['n_rows']} 行")
    ck("三个文件都读成功", m2["n_ok"] == 3, f"{m2['n_ok']}/3")
    ck("表头里带 __sheet 来源标记", "__sheet" in m2["header"],
       str(m2["header"][:3]))
    # 2 月只有 28 个 sheet
    feb = next((x for x in m2["files"] if "2月" in x["path"]), None)
    ck("2 月 = 336 行（28×12）", feb and feb["rows"] == 336,
       f"{feb['rows'] if feb else '?'} 行")
else:
    ck("（附件2 目录不存在，跳过）", True, "")

print()
print("=" * 74)
print("三、损坏/空输入的健壮性")
print("=" * 74)
import tempfile
td = tempfile.mkdtemp(prefix="ms_")
empty = os.path.join(td, "empty.csv")
open(empty, "w", encoding="utf-8").close()
h, r = ms.read_rows(empty)
ck("空 CSV 返回空表头空行，不抛异常", h == [] and r == [], f"{h} {len(r)}")

# 列名不一致时必须取并集而不是猜
a = os.path.join(td, "a.csv")
b = os.path.join(td, "b.csv")
open(a, "w", encoding="utf-8", newline="\n").write("x,y\n1,2\n")
open(b, "w", encoding="utf-8", newline="\n").write("x,z\n3,4\n")
mm_ = ms.merge_paths([a, b])
ck("列名不同取并集", set(mm_["header"]) == {"x", "y", "z"},
   str(mm_["header"]))
ck("合并行数 = 2", mm_["n_rows"] == 2, str(mm_["n_rows"]))
ck("不猜同名列（y 和 z 各自独立）",
   mm_["header"].count("x") == 1 and "y" in mm_["header"]
   and "z" in mm_["header"], str(mm_["header"]))

# 读不了的文件要报出来而不是静默跳过
bad_f = os.path.join(td, "broken.xlsx")
open(bad_f, "wb").write(b"not an excel file")
m3 = ms.merge_paths([bad_f, a])
ck("坏文件被标记为失败", m3["n_ok"] == 1 and m3["n_files"] == 2,
   f"{m3['n_ok']}/{m3['n_files']}")
ck("坏文件给出原因", any(not f.get("ok") and f.get("why")
                         for f in m3["files"]), "有 why 字段")

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
