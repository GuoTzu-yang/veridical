#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_dclass_path.py —— 只读：给 D_computed 里「gate 口径能溯源」的 token 找出**精确来源**。

输出：token / 命中的分支（direct 同号 / direct 反号 / x100 / div100）/ f / f 的 path
用来区分「同一个量的另一种写法」与「跨量巧合」。
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

# 上一趟 rt_dclass.py 判出的 gate_ok 集合（题, token）
TARGETS = [
    ("evaluation", "37.9"), ("prediction", "0.074"), ("prediction", "87.8"),
    ("network", "-5.0"), ("population", "-0.8"), ("simulation", "-46.0"),
    ("chemical", "4.1"), ("real_c2024", "-12.5"), ("pop_panel", "539.2"),
    ("age_struct", "-7.2"), ("birth_rate", "-4.3"), ("fertility", "-2.7"),
    ("nflis", "0.644"), ("nflis", "-67.3"), ("review_pacifier", "0.004"),
]

for task, tok in TARGETS:
    d = os.path.join(ROOT, "out", "runs", task)
    fz = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    items = fz.get("items", [])
    v = float(tok)
    dec = F._decimals(tok)
    tol = 0.5 * (10 ** -dec) + 1e-12
    a = abs(v)
    hit = None
    for it in items:
        f = it["value"]
        if abs(a - abs(f)) <= tol:
            hit = ("direct_same" if v * f >= 0 else "direct_flip",
                   it["path"], f)
            break
    if hit is None:
        for it in items:
            f = it["value"]
            if abs(a - abs(f) * 100.0) <= tol:
                hit = ("x100", it["path"], f)
                break
    if hit is None:
        for it in items:
            f = it["value"]
            if abs(a - abs(f) / 100.0) <= tol:
                hit = ("div100", it["path"], f)
                break
    if hit is None:
        print("%-18s %-14s 无命中" % (task, tok))
        continue
    branch, path, f = hit
    print("%-18s %-14s %-12s f=%-22r path=%s" % (task, tok, branch, f, path))
