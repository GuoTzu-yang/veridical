#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查：这套东西有多少是这道题专用的。

要回答「只针对这道题还是覆盖全部」，得数清楚：
  · 有多少处把「热阻/压降/温度」「heat sink」「manifold」写死了
  · 换一道题，哪些模块会自动适配，哪些会输出错误的东西
"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 这道题的专有词
DOMAIN = ["heat sink", "thermal resistance", "pressure drop",
          "manifold", "pin-fin", "pin fin", "non-uniformity",
          "热阻", "压降", "针肋", "歧管", "深高比", "排数", "温度非均匀"]

print("  === 各模块里的专有词出现次数 ===")
files = ["mmkit.py", "paper.py", "q4.py", "q5.py", "multimodel.py",
         "cards.py", "innovation.py", "abstract.py", "gate.py",
         "plot_mpl.py", "mm.py", "cite.py", "schema.py", "freeze.py"]
for fn in files:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        print(f"    {fn:<18} 不存在")
        continue
    src = open(p, encoding="utf-8").read()
    low = src.lower()
    hits = {}
    for w in DOMAIN:
        n = low.count(w.lower())
        if n:
            hits[w] = n
    total = sum(hits.values())
    print(f"    {fn:<18}{total:>4} 处   {hits if hits else ''}")

print()
print("  === 关键：有没有参数化的入口 ===")
mk = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
for flag in ("--y", "--x", "--min", "--problem", "--sheet", "--data"):
    print(f"    {flag:<12}{flag in mk}")

print()
print("  === 假设卡片是不是这道题专用 ===")
cd = os.path.join(HERE, "kb", "cards")
if os.path.isdir(cd):
    for f in sorted(os.listdir(cd)):
        if not f.endswith(".json"):
            continue
        txt = open(os.path.join(cd, f), encoding="utf-8").read()
        low = txt.lower()
        n = sum(low.count(w) for w in DOMAIN)
        print(f"    {f:<12}{n:>3} 处专有词 / {len(txt)} 字节")
else:
    print("    没有 kb/cards")

print()
print("  === 论文的机理节是不是这道题专用 ===")
pp = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
m = re.search(r"_PHYS_STRENGTH\s*=\s*\{(.*?)\}", pp, re.S)
if m:
    print(f"    _PHYS_STRENGTH 有 {m.group(1).count(':')} 条预测")
else:
    print("    没有 _PHYS_STRENGTH")
# 机理段的位置
for kw in ("Mechanistic basis", "conservation", "governing equation"):
    print(f"    {kw:<22}{pp.count(kw)} 次")
