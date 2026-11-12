#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_x100.py —— 只读：×100 / ÷100 分支的命中明细 + dec>12 的 token 现在靠什么通过。

第 122 轮复核版：本地 tol 必须与 freeze._match_written 同步（它已去掉 +1e-12）。
脚本启动时用 _sync_check() 断言两边一致；不一致就打印警告，避免「探针自己算旧公式」
这种假结论（上一版踩过：探针里复制了旧 tol，于是地板看起来没修）。
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import freeze as F      # noqa: E402

TASKS = sys.argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]


def _tol(dec: int) -> float:
    """与 freeze.py:165 `tol = 0.5 * (10.0 ** -dec)` 同步。"""
    return 0.5 * (10.0 ** -dec)


def _sync_check() -> int:
    random.seed(7)
    bad = 0
    for _ in range(300):
        dec = random.choice([-3, -1, 0, 1, 3, 6, 10, 13, 17])
        f = random.uniform(-1e4, 1e4)
        v = round(f, dec)
        local = abs(abs(v) - abs(f)) <= _tol(dec)
        prod = F._match_written(v, dec, [f])
        if local != prod:
            bad += 1
    return bad


_n = _sync_check()
print("_sync_check：本地 tol vs freeze._match_written 不一致 %d/300" % _n)
if _n:
    print("  ⚠ 本地 tol 已与生产判据漂移 —— 下面的明细不可信")

for name in TASKS:
    d = os.path.join(ROOT, "out", "runs", name)
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    fz = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    fvals = [it["value"] for it in fz.get("items", [])]
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ",
               tex, flags=re.S)
    seen = set()
    x100, hi = [], []
    for tok, _line in V.extract_numbers(t, skip_meta=False):
        if "." not in tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = F._decimals(tok)
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        tol = _tol(dec)
        a = abs(v)
        direct = [f for f in fvals if abs(a - abs(f)) <= tol]
        if direct:
            if dec > 12:
                hi.append((tok, dec, direct[0], abs(a - abs(direct[0]))))
            continue
        x = [f for f in fvals if abs(a - abs(f) * 100.0) <= tol]
        if x:
            x100.append((tok, x[0]))
    print("=" * 78)
    print("%-16s 候选 %d   x100 命中 %d   dec>12 的 direct 命中 %d"
          % (name, len(seen), len(x100), len(hi)))
    for tok, f in x100:
        print("    x100: %-14s ← f=%r" % (tok, f))
    for tok, dec, f, delta in hi:
        print("    dec>12: %-14s dec=%-3d ← f=%-24r |差|=%.3g  半格=%.3g"
              % (tok, dec, f, delta, _tol(dec)))
