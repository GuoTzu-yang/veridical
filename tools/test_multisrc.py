#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 A 题真实数据验证 multisrc：这是「任意一道题」的门槛。"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import multisrc  # noqa: E402

BASE = os.path.abspath(os.path.join(
    HERE, "..", "apmcm2026", "题库", "2026中文-A_B_C三题",
    "A题 自来水厂水质预测与评估", "附件"))

print("=" * 76)
print("一、单文件多 sheet（附件2 的 .xls，90 个 sheet）")
print("=" * 76)
f2 = os.path.join(BASE, "附件2  2026数据集", "2026年1月.xls")
if os.path.exists(f2):
    names = multisrc.sheet_names(f2)
    print(f"  {os.path.basename(f2)}: {len(names)} 个 sheet")
    print(f"  前 5 个: {names[:5]}")
    h, r, meta = multisrc.read_all_sheets(f2)
    print(f"  合并后: {len(r)} 行 × {len(h)} 列, 用了 {meta['sheets']} 个 sheet")
    print(f"  表头: {h[:6]}")
    print(f"  第一行: {[str(v)[:12] for v in r[0][:6]]}")
    print(f"  ← 每行带 __sheet 标记来源，否则合并后无法追溯日期")

print()
print("=" * 76)
print("二、多文件合并（附件1 的 12 个 xlsx）")
print("=" * 76)
d1 = os.path.join(BASE, "附件1  2025数据集")
if os.path.isdir(d1):
    srcs = multisrc.find_sources(d1)
    print(f"  找到 {len(srcs)} 个源")
    m = multisrc.merge_paths(srcs)
    print()
    print(multisrc.report(m))
    print()
    # 关键：两种表头的差异必须暴露出来
    print(f"  列并集 {m['n_cols']} 列 —— 若 > 21 说明确实存在列名不一致")

print()
print("=" * 76)
print("三、三个月的附件2 全合并（含 .xls 路径）")
print("=" * 76)
d2 = os.path.join(BASE, "附件2  2026数据集")
if os.path.isdir(d2):
    srcs2 = multisrc.find_sources(d2)
    print(f"  找到 {len(srcs2)} 个源: {[os.path.basename(x) for x in srcs2]}")
    m2 = multisrc.merge_paths(srcs2, per_sheet=True)
    print(multisrc.report(m2))
    print(f"  合计 {m2['n_rows']} 行 × {m2['n_cols']} 列")
    print(f"  期望约 90 天 × 12 时点 = 1080 行（题面事实）")
