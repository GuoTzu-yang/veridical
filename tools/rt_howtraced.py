#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_howtraced.py —— 只读：每个带小数 token 是靠哪条分支通过的？

_match_written 的三条分支：
  direct   |abs(v) - abs(f)|      <= tol   （含「符号相反」的情形，单列 sign_flip）
  x100     |abs(v) - abs(f)*100|  <= tol   （百分比写法）
  /100     |abs(v) - abs(f)/100|  <= tol

输出每篇的分布 + 反号通过的明细。整数 token 不参与（gate 不判）。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import freeze as F      # noqa: E402
import untraced as U    # noqa: E402

TASKS = sys.argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]


def how(v, dec, fvals):
    tol = 0.5 * (10 ** -dec) + 1e-12
    a = abs(v)
    for f in fvals:
        if abs(a - abs(f)) <= tol:
            return ("direct_same" if (v * f >= 0 or v == 0 or f == 0)
                    else "direct_flip", f)
    for f in fvals:
        if abs(a - abs(f) * 100.0) <= tol:
            return ("x100", f)
    for f in fvals:
        if abs(a - abs(f) / 100.0) <= tol:
            return ("div100", f)
    return ("NONE", None)


for name in TASKS:
    d = os.path.join(ROOT, "out", "runs", name)
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    frozen = json.load(io.open(os.path.join(d, "冻结数字.json"),
                              encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ",
               tex, flags=re.S)
    toks = [tt for tt, _l in V.extract_numbers(t, skip_meta=False)
            if "." in tt]
    seen = set()
    cnt = {}
    flips = []
    for tok in toks:
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = F._decimals(tok)
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        kind, f = how(v, dec, fvals)
        cnt[kind] = cnt.get(kind, 0) + 1
        if kind == "direct_flip":
            flips.append((tok, f))
    print("=" * 78)
    print("%-16s 候选 %d  %s" % (name, len(seen),
                                 "  ".join("%s=%d" % (k, cnt[k])
                                           for k in sorted(cnt))))
    for tok, f in flips[:12]:
        print("    反号通过: %-12s ← f=%r" % (tok, f))
