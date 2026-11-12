#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_dbg.py —— 只读：查某题某 token 的 dec/tol/最近冻结值。"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import freeze as F      # noqa: E402
import verify as V      # noqa: E402

name, tok = sys.argv[1], sys.argv[2]
d = os.path.join(ROOT, "out", "runs", name)
fz = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
vals = [it["value"] for it in fz.get("items", [])]
v = float(tok)
dec = F._decimals(tok)
tol = 0.5 * (10 ** -dec) + 1e-12
print("token=%r  v=%r  dec=%r  tol=%r  _written_decimals=%r"
      % (tok, v, dec, tol, V._written_decimals(tok)))
order = sorted(vals, key=lambda f: abs(abs(v) - abs(f)))
for f in order[:5]:
    print("   f=%r  |abs(v)-abs(f)|=%r  同号=%s"
          % (f, abs(abs(v) - abs(f)), (v * f >= 0)))
print("  _match_written =", F._match_written(v, dec, vals))
