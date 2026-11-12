#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_list_un23.py —— 只读：23 篇里所有 gate 口径的未溯源 token（含 why）。"""
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
import verify as V      # noqa: E402

cfg = json.load(io.open(os.path.join(ROOT, "runs.json"), encoding="utf-8"))
for nm, it in cfg.items():
    d = os.path.join(ROOT, it["out"])
    texp = os.path.join(d, "paper.tex")
    fzp = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(texp) and os.path.exists(fzp)):
        continue
    frozen = json.load(io.open(fzp, encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(d)) or None
    deliv = G._is_deliverable(d)
    r = F.check_paper(io.open(texp, encoding="utf-8").read(), frozen,
                      single_point=deliv, data_values=dv,
                      strict_source=deliv)
    if not (r.get("untraced") or []):
        continue
    print("=" * 70)
    print("%s  %d/%d  未溯源 %s  reasons=%s"
          % (nm, r["n_traced"], r["n_numbers"], r["untraced"], r["reasons"]))
    # 找每个未溯源 token 的原文与精度
    tex = io.open(texp, encoding="utf-8").read()
    for tok in r["untraced"]:
        dec = F._decimals("%.17g" % tok)
        # 用原文在 tex 里定位（按值匹配所有写法）
        hits = []
        for i, ln in enumerate(tex.splitlines(), 1):
            for m in V.extract_numbers(ln, skip_meta=False):
                try:
                    if abs(float(m[0]) - tok) < 1e-18:
                        hits.append((i, ln.strip()[:100]))
                        break
                except ValueError:
                    pass
        print("   token=%r  dec(按 %.17g)=%r" % (tok, tok, dec))
        for h in hits[:2]:
            print("      L%d  %s" % h)
