#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_find.py —— 只读：在冻结表里按 |值| 找条目。

用法: python tools/rt_find.py <题名> <目标值> [容差=0.05]
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

name = sys.argv[1]
want = float(sys.argv[2])
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
p = os.path.join(ROOT, "out", "runs", name, "冻结数字.json")
fz = json.load(io.open(p, encoding="utf-8"))
hits = [it for it in fz.get("items", []) if abs(abs(it["value"]) - want) <= tol]
print("%s: 找 |值|≈%g（容差 %g）→ %d 条" % (name, want, tol, len(hits)))
for it in hits:
    print("   %-42s %r" % (it["path"], it["value"]))
if not hits:
    print("   （本次没找到）")
