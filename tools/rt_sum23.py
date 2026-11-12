#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_sum23.py —— 只读：独立复核 23 篇的 numbers 判决（不经过 e_verify 的展示层）。"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import freeze as F      # noqa: E402
import untraced as U    # noqa: E402
import gate as G        # noqa: E402

cfg = json.load(io.open(os.path.join(ROOT, "runs.json"), encoding="utf-8"))
bad = 0
tot_n = 0
tot_un = 0
print("%-20s %-5s %6s %6s %7s %5s %s"
      % ("题", "ok", "traced", "n", "ratio", "hp", "整数未判"))
print("-" * 74)
for nm, it in cfg.items():
    d = os.path.join(ROOT, it["out"])
    texp = os.path.join(d, "paper.tex")
    fzp = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(texp) and os.path.exists(fzp)):
        print("%-20s 缺产物" % nm)
        continue
    frozen = json.load(io.open(fzp, encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(d)) or None
    deliv = G._is_deliverable(d)
    r = F.check_paper(io.open(texp, encoding="utf-8").read(), frozen,
                      single_point=deliv, data_values=dv,
                      strict_source=deliv)
    tot_n += r["n_numbers"]
    tot_un += len(r.get("untraced") or [])
    if not r["ok"]:
        bad += 1
    print("%-20s %-5s %6d %6d %7.3f %5s %6d  %s"
          % (nm, "OK" if r["ok"] else "FAIL", r["n_traced"], r["n_numbers"],
             r["untraced_ratio"], r["high_precision_bad"],
             r["n_int_not_judged"],
             "" if r["ok"] else str(r["untraced"][:5])))
print("-" * 74)
print("合计 候选 %d，未溯源 %d；红题 %d" % (tot_n, tot_un, bad))
