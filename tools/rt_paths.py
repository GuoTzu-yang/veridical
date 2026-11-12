#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_paths.py —— 只读：列出某篇冻结表里命中指定关键词的条目（path=value）。"""
from __future__ import annotations
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

name = sys.argv[1]
pats = sys.argv[2:] or ["cond", "falsify", "tradeoff", "seg"]
p = os.path.join(ROOT, "out", "runs", name, "冻结数字.json")
fz = json.load(io.open(p, encoding="utf-8"))
print("%s: n=%d  generated_from=%r" % (name, fz.get("n"), fz.get("generated_from")))
hit = [it for it in fz.get("items", [])
       if any(k in it["path"] for k in pats)]
print("命中 %d 条 / patterns=%s" % (len(hit), pats))
for it in hit:
    print("  %-46s %r" % (it["path"], it["value"]))
if not hit:
    print("  （本次没找到）")
