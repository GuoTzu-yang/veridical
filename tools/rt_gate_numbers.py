#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_gate_numbers.py —— 只读：直接调 gate.chk_numbers（不跑 gate 主流程、不写盘）。"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import gate  # noqa: E402

TASKS = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]

for name in (sys.argv[1:] or TASKS):
    d = os.path.join(ROOT, "out", "runs", name)
    r = gate.chk_numbers(d)
    print("%-16s %-5s %s" % (name, r.get("status"), r.get("detail")))
