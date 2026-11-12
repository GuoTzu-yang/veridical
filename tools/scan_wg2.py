#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 writing-guard 的规则扫论文（第二版：按 id 分块提取，不假设字段顺序）。"""
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(os.environ.get("TEMP", "/tmp"),
                     "wg_inspect", "package", "lib", "rules.js")
TEX = os.path.join(HERE, "out", "fig", "paper.tex")

js = open(RULES, encoding="utf-8", errors="replace").read()

# 按 id:'xxx' 切开，每块到下一个 id: 之前
parts = re.split(r"(?=id:\s*['\"])", js)
rules = []
for p in parts[1:]:
    m_id = re.match(r"id:\s*['\"]([^'\"]+)", p)
    if not m_id:
        continue
    rid = m_id.group(1)
    m_cat = re.search(r"category:\s*['\"]([^'\"]+)", p)
    m_sev = re.search(r"severity:\s*['\"]([^'\"]+)", p)
    m_max = re.search(r"maxHits:\s*(\d+)", p)
    # pattern 有两种写法：/.../g  或 new RegExp('...')
    m_rx = re.search(r"pattern:\s*/(.+?)/[gimsuy]*,", p, re.S)
    if not m_rx:
        m_rx = re.search(r"pattern:\s*new RegExp\(\s*['\"](.+?)['\"]", p, re.S)
    if not m_rx:
        continue
    rules.append(dict(
        id=rid,
        category=(m_cat.group(1) if m_cat else "?"),
        severity=(m_sev.group(1) if m_sev else "?"),
        maxHits=int(m_max.group(1)) if m_max else 99,
        rx=m_rx.group(1),
    ))

print(f"  提取 {len(rules)} 条规则")

tex = open(TEX, encoding="utf-8").read()
body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", tex)
body = re.sub(r"\s+", " ", body)

hits = []
for r in rules:
    try:
        cre = re.compile(r["rx"])
    except re.error as e:
        continue
    ms = [m.group(0) for m in cre.finditer(body)]
    if ms:
        hits.append((r["id"], r["category"], r["severity"],
                     min(len(ms), r["maxHits"]), len(ms), ms[:4]))

hits.sort(key=lambda x: -x[4])
print(f"  论文命中 {len(hits)} 条规则\n")
print(f"  {'规则':<28}{'类别':<20}{'严重':<7}{'实/报':<8}样例")
for rid, cat, sev, rep, real, ex in hits:
    e = " | ".join(str(x)[:26] for x in ex[:3])
    print(f"  {rid:<28}{cat:<20}{sev:<7}{real}/{rep:<5}{e}")

print()
c = Counter(h[1] for h in hits)
for k, v in c.most_common():
    print(f"    {k:<24}{v} 条命中")
