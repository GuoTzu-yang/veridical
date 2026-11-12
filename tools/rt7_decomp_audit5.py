# -*- coding: utf-8 -*-
"""rt7_decomp_audit5.py —— 「every numeric token」到底是不是每一个。

verify.py:133 在分类之前按 PLAUSIBLE_META 静默丢弃 token。
这里量出被丢的比例，并确认丢弃集合恰好是那 16 个值。只读。
"""
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import verify as V


def papers():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    out = []
    for nm, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if os.path.exists(os.path.join(d, "paper.tex")):
            out.append((nm, d))
    return out


tot_with = tot_wo = 0
dropped = Counter()
print("%-16s %8s %8s %8s" % ("题", "skip=T", "skip=F", "被丢"))
for nm, d in papers():
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    a = V.extract_numbers(tex, skip_meta=True)
    b = V.extract_numbers(tex, skip_meta=False)
    tot_with += len(a)
    tot_wo += len(b)
    print("%-16s %8d %8d %8d" % (nm, len(a), len(b), len(b) - len(a)))
    # 被丢的是哪些值
    ca = Counter(t for t, _ in a)
    cb = Counter(t for t, _ in b)
    for k in cb:
        n = cb[k] - ca.get(k, 0)
        if n > 0:
            dropped[k] += n

print()
print("合计 skip_meta=True  %d" % tot_with)
print("合计 skip_meta=False %d" % tot_wo)
print("被 PLAUSIBLE_META 丢掉 %d（占 skip_meta=False 的 %.1f%%）"
      % (tot_wo - tot_with, 100.0 * (tot_wo - tot_with) / max(1, tot_wo)))
print()
print("被丢的 distinct 值 = %d 个：" % len(dropped))
for k, n in dropped.most_common():
    mark = "∈PLAUSIBLE_META" if float(k) in V.PLAUSIBLE_META else "!! 不在 META 里"
    print("   %-8s x %-5d %s" % (k, n, mark))
