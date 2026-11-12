#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_dclass.py —— 只读：把当前 28 个 D_computed 按「用 gate 口径能不能溯源」拆开。

三个桶：
  gate_ok       _match_written 命中（说明是 verify 的符号/缩放口径差，不是缺源）
  gate_data     round(v,6) 在输入表里（E 类）
  gate_missing  两样都不命中 —— 真·未登记
另标 integer=True 的（gate 根本不判）。
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

cfg = json.load(io.open(os.path.join(ROOT, "runs.json"), encoding="utf-8"))
rows = []
for nm, it in cfg.items():
    d = os.path.join(ROOT, it["out"])
    texp = os.path.join(d, "paper.tex")
    fzp = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(texp) and os.path.exists(fzp)):
        continue
    tex = io.open(texp, encoding="utf-8").read()
    fz = json.load(io.open(fzp, encoding="utf-8"))
    fvals = [x["value"] for x in fz.get("items", [])]
    dv = U.data_values_of(U.find_data_file(d))
    r = V.trace(tex, V.load_outputs(d))
    for u in (r.get("untraced") or []):
        tok = u["token"]
        if U.classify_token(tok, dv) != "D_computed":
            continue
        integer = "." not in tok
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = F._decimals(tok) if not integer else 0
        ok = F._match_written(v, dec, fvals) if not integer else None
        in_data = bool(dv) and round(v, 6) in dv
        rows.append(dict(task=nm, token=tok, integer=integer,
                         gate=("n/a" if integer else ok),
                         data=in_data, line=u["line"][:60]))

print("D_computed 总数 = %d" % len(rows))
buckets = {}
for r in rows:
    if r["integer"]:
        k = "integer(未判)"
    elif r["gate"]:
        k = "gate_ok(口径差)"
    elif r["data"]:
        k = "gate_data(输入表)"
    else:
        k = "gate_missing(真缺源)"
    buckets.setdefault(k, []).append(r)
for k in sorted(buckets):
    print("  %-22s %d" % (k, len(buckets[k])))
print()
for k in sorted(buckets):
    print("### %s" % k)
    for r in buckets[k]:
        print("   %-18s %-16s %s" % (r["task"], r["token"], r["line"][:56]))
