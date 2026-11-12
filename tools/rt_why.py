#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_why.py —— 只读：给一篇的每个未溯源 token 找「池里最近的值」，判定为什么不匹配。

用法: python tools/rt_why.py prediction [更多题名...]
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

names = sys.argv[1:]
for name in names:
    d = os.path.join(ROOT, "out", "runs", name)
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    outs = V.load_outputs(d)
    pool = V.collect_output_numbers(outs)
    fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                          encoding="utf-8"))
    fvals = [it["value"] for it in fz.get("items", [])]
    r = V.trace(tex, outs)
    print("=" * 78)
    print("%s  池 %d 个值（含冻结表 %d 条）  未溯源 %d/%d"
          % (name, len(pool), len(fvals), r["n_untraced"], r["n_numbers"]))
    for u in r["untraced"]:
        tok = u["token"]
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = V._written_decimals(tok)
        cands = sorted(pool, key=lambda f: abs(V._decimals(0) if False
                                               else abs(round(f, dec) - v)))
        best = cands[0] if cands else None
        in_fz = any(abs(round(f, dec) - v) <= 1e-12 for f in fvals)
        print("\n  token=%s  dec=%s  v=%r" % (tok, dec, v))
        if best is not None:
            print("     池最近 f=%r  round(f,dec)=%r  差=%r"
                  % (best, round(best, dec), round(best, dec) - v))
        print("     冻结表里有 round(f,dec)==v 的吗: %s" % in_fz)
        print("     ctx: %s" % u["line"][:110])
