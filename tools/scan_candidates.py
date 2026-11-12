#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫 external/ 里所有真实数据文件，挑出结构不同的候选题。

为什么要多跑题
------------
「机理节把热沉的守恒律搬进预测题」这类缺陷，只跑一道题时看不见；
换一道结构完全不同的题，它就露出来了。所以先把候选题挑出来。
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")

rows = []
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if not f.lower().endswith((".xlsx", ".xls", ".csv", ".tsv")):
            continue
        p = os.path.join(root, f)
        rel = os.path.relpath(p, HERE)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 20 * 1024 * 1024:
            rows.append((rel, sz, -1, -1, "too big"))
            continue
        try:
            if f.lower().endswith((".csv", ".tsv")):
                sep = "\t" if f.lower().endswith(".tsv") else None
                d = pd.read_csv(p, nrows=500, sep=sep, low_memory=False,
                               encoding_errors="replace")
            else:
                xl = pd.ExcelFile(p)
                best = (None, -1, -1)
                for sh in xl.sheet_names:
                    try:
                        d2 = xl.parse(sh)
                    except Exception:
                        continue
                    nnum = sum(1 for c in d2.columns
                               if pd.api.types.is_numeric_dtype(d2[c]))
                    if nnum > best[1]:
                        best = (sh, nnum, len(d2))
                sh, nnum, nrow = best
                if sh is None:
                    continue
                d = xl.parse(sh)
        except Exception as e:
            rows.append((rel, sz, -1, -1, type(e).__name__))
            continue
        nnum = sum(1 for c in d.columns
                   if pd.api.types.is_numeric_dtype(d[c]))
        rows.append((rel, sz, len(d), nnum, ""))

rows.sort(key=lambda r: (-r[3], -r[2]))
print("  文件  行  数值列  大小  路径")
print("  " + "-" * 72)
n = 0
for rel, sz, nrow, nnum, err in rows:
    if nnum >= 3 and nrow >= 20 and not err:
        n += 1
        if n <= 22:
            print("  %5d %3d  %8.0fK  %s" % (nrow, nnum, sz / 1024,
                                              rel[:56]))
print()
print("  可用候选（数值列>=3 且行数>=20）：%d 个 / 共 %d 个文件"
      % (n, len(rows)))