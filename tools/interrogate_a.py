#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拿陌生的 A 题原始附件拷问插件 —— 我有标准答案，看它选得对不对。

已知正确答案（来自 02-A题实战记录，实跑核过）：
  1. 附件1 有两种表头：完整版 21 列 / 精简版 16 列（5~8 月是精简版）
  2. 文件内日期列三种格式混用；Apr 把日期写成 2025-01-04（月份钉死 01）
     → 直接用日期列，4 月数据会被塞进 1 月 4 日，整年错位
  3. 附件2 是 90 个 sheet，sheet_name=0 只读到 1 天
  4. 2026-02 整月 NTU 全空（336 个时点）

判据：插件有没有识别/警示这些。
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import mm  # noqa: E402

BASE = os.path.abspath(os.path.join(HERE, "..", "apmcm2026", "题库",
                                    "2026中文-A_B_C三题",
                                    "A题 自来水厂水质预测与评估", "附件"))

CASE = [
    ("附件1 完整版（Jan，21 列）",
     os.path.join(BASE, "附件1  2025数据集", "JBALB_Jan2025.xlsx"), 21),
    ("附件1 精简版（May，16 列）",
     os.path.join(BASE, "附件1  2025数据集", "JBALB_May2025.xlsx"), 16),
    ("附件1 Apr（日期陷阱）",
     os.path.join(BASE, "附件1  2025数据集", "JBALB_Apr2025.xlsx"), None),
]

print("=" * 78)
print("拷问 1：能否读、表头认对没、列数对不对")
print("=" * 78)
for label, path, expect_cols in CASE:
    if not os.path.exists(path):
        print(f"  {label}: 文件不存在")
        continue
    try:
        ds = mm.DS(path)
    except Exception as e:                              # noqa: BLE001
        print(f"  {label}: **读失败** {type(e).__name__}: {str(e)[:70]}")
        continue
    print(f"\n  {label}")
    print(f"    header_row={ds.header_row}  "
          f"总列={len(ds.names)}  数值列={len(ds.num_names)}  "
          f"行={ds.n_rows}/{ds.n_rows_raw}")
    print(f"    列名: {ds.names[:8]}")
    if expect_cols:
        ok = len(ds.names) == expect_cols
        print(f"    期望 {expect_cols} 列 → {'✓ 对' if ok else '✗ 错'}")
    if ds.dropped:
        print(f"    丢弃: {ds.drop_note()[:70]}")
    if ds.non_numeric:
        print(f"    非数值: {ds.non_numeric[:6]}")

print()
print("=" * 78)
print("拷问 2：日期陷阱 —— 它会把 Apr 的数据当成 1 月 4 日吗？")
print("=" * 78)
apr = os.path.join(BASE, "附件1  2025数据集", "JBALB_Apr2025.xlsx")
if os.path.exists(apr):
    ds = mm.DS(apr)
    cols_lower = [c.lower() for c in ds.names]
    date_cols = [c for c in ds.names
                 if any(k in str(c).lower() for k in
                        ("date", "time", "日期", "时间"))]
    print(f"  列名里长得像日期的: {date_cols}")
    print(f"  它们是数值列吗: "
          f"{[c in ds.num_names for c in date_cols]}")
    # 直接看原始第一列的值
    import openpyxl
    wb = openpyxl.load_workbook(apr, data_only=True)
    ws = wb.active
    vals = [str(r[0]) for r in ws.iter_rows(min_row=2, max_row=5,
                                            values_only=True)]
    print(f"  原始日期列前 4 个值: {vals}")
    print("  正确日期应是 2025-04-01 起 —— "
          "若插件把这一列当普通数据，就会把 4 月当成 1 月")
    print(f"  插件是否把它识别为非数值（因而不参与建模）: "
          f"{[c not in ds.num_names for c in date_cols]}")

print()
print("=" * 78)
print("拷问 3：用插件给的数值列跑一遍，看它自己会说什么")
print("=" * 78)
if os.path.exists(apr):
    ds = mm.DS(apr)
    nums = ds.num_names
    if len(nums) >= 3:
        y = nums[0]
        xs = [c for c in nums[1:5] if c != y]
        if xs:
            print(f"  y={y}  x={xs}")
            for h in __import__("mmkit").all_partial(ds, y, xs):
                pcs = "—" if h["pc"] is None else f"{h['pc']:+.4f}"
                print(f"    {h['name']:<14}{pcs:>9}  {h['note'][:52]}")
