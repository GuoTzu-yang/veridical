#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_twogates.py —— 只读：同一份产物，gate 口径 vs verify 口径的判决差集。

gate 口径：freeze.check_paper（只判带小数，_match_written 用 abs(v)/abs(f)）
verify 口径：verify.trace（判所有 token，_near 不带 abs）

只比较**带小数**的 token，整数不参与（gate 本来就不判）。
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import freeze as F      # noqa: E402
import untraced as U    # noqa: E402
import gate as G        # noqa: E402

names = sys.argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]
for name in names:
    d = os.path.join(ROOT, "out", "runs", name)
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    frozen = json.load(io.open(os.path.join(d, "冻结数字.json"),
                              encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(d)) or None
    deliv = G._is_deliverable(d)
    rc = F.check_paper(tex, frozen, single_point=deliv, data_values=dv,
                       strict_source=deliv)
    rv = V.trace(tex, V.load_outputs(d))
    A = {round(float(x), 6) for x in (rc.get("untraced") or [])}
    B = {round(float(u["token"]), 6) for u in (rv.get("untraced") or [])
         if "." in u["token"]}
    both = A & B
    only_gate = A - B
    only_verify = B - A
    print("=" * 78)
    print("%-16s gate: %d/%d 未溯源 %d (%.1f%%) | verify: %d/%d 未溯源 %d  "
          "| 交集 %d  只 gate %d  只 verify %d"
          % (name, rc["n_traced"], rc["n_numbers"], len(A),
             100 * rc["untraced_ratio"], rv["n_numbers"] - rv["n_untraced"],
             rv["n_numbers"], rv["n_untraced"], len(both), len(only_gate),
             len(only_verify)))
    if only_gate:
        print("   只 gate 判红（verify 认为有源）: %s" % sorted(only_gate)[:10])
    if only_verify:
        toks = [u["token"] for u in rv["untraced"]
                if round(float(u["token"]), 6) in only_verify and "." in u["token"]]
        print("   只 verify 判红（gate 认为有源）: %s" % toks[:10])
