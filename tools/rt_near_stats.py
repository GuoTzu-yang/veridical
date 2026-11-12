#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_near_stats.py —— 只读：统计 out/_rt_E_near.txt 里「值在冻结表」的比例。

判据（与报告 §2.3 一致）：
  · token 总数              = 未溯源 token 数
  · 最近邻 rel < 1e-3 的     = 值就在冻结表里（强证据）
  · 「有效容差判=True」的行数 = 宽口径（含偶然匹配，不作强证据）
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "out", "_rt_E_near.txt")

lines = io.open(path, encoding="utf-8").read().splitlines()
cur = None
rel_ok = 0
tot = 0
for ln in lines:
    m = re.match(r"\s+token=(\S+)", ln)
    if m:
        cur = m.group(1)
        tot += 1
        got = False
        continue
    m = re.search(r"frozen\s+\S+\s+f=\S+\s+rel=([0-9.eE+-]+)", ln)
    if m and cur and not got:
        got = True
        if float(m.group(1)) < 1e-3:
            rel_ok += 1
wide = sum(1 for ln in lines if "有效容差判=True" in ln)
print("token 总数=%d   最近邻 rel<1e-3 的=%d   有效容差判=True 的行数=%d"
      % (tot, rel_ok, wide))
