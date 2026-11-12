#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 dsh-plugin-writing-guard 的规则提取成 JSON。

来源：external/npm/dsh-plugin-writing-guard/package/lib/rules.js（235 KB）

提取字段：id / category / severity / regex / maxHits / label / profiles
过滤：有 5 条规则是「统计型」（平均句长、段落节奏），它们的 pattern 会
匹配整段文本（上轮实测匹配 44096 次）；这些不在正则层面判，跳过。
"""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(HERE, "external", "npm", "dsh-plugin-writing-guard",
                  "package", "lib", "rules.js")
OUT = os.path.join(HERE, "kb", "ai_rules.json")

if not os.path.exists(JS):
    raise SystemExit("规则源不存在: " + JS)

js = open(JS, encoding="utf-8", errors="replace").read()
parts = re.split(r"(?=id:\s*['\"])", js)

rules = []
for p in parts[1:]:
    m_id = re.match(r"id:\s*['\"]([^'\"]+)", p)
    if not m_id:
        continue
    rid = m_id.group(1)

    def grab(pat, default=None):
        mm = re.search(pat, p)
        return mm.group(1) if mm else default

    m_rx = re.search(r"pattern:\s*/(.+?)/[gimsuy]*,", p, re.S)
    if not m_rx:
        continue
    rx = m_rx.group(1)
    rules.append(dict(
        id=rid,
        category=grab(r"category:\s*['\"]([^'\"]+)") or "?",
        severity=grab(r"severity:\s*['\"]([^'\"]+)") or "low",
        label=grab(r"label:\s*['\"]([^'\"]+)") or rid,
        regex=rx,
        maxHits=int(grab(r"maxHits:\s*(\d+)") or 99),
        profiles=(grab(r"profiles:\s*\[([^\]]*)\]") or "").replace("'", ""),
        languages=(grab(r"languages:\s*\[([^\]]*)\]") or "").replace("'", ""),
    ))

# 兼容性筛选：Python re 能否编译 + 是否会匹配整段
kept, dropped = [], []
_sample = ("The model is fitted to the data rather than assumed. " * 60)
for r in rules:
    try:
        cre = re.compile(r["regex"])
    except re.error as e:
        dropped.append((r["id"], f"正则不兼容: {str(e)[:40]}"))
        continue
    n = len(cre.findall(_sample))
    if n > 200:
        dropped.append((r["id"], f"匹配过宽（{n} 次/60句）"))
        continue
    kept.append(r)

json.dump(dict(version=1,
               source="dsh-plugin-writing-guard 2.0.1 lib/rules.js",
               note="按 category 分组；maxHits 是原作者设的上报上限。",
               rules=kept),
          open(OUT, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)

from collections import Counter
c = Counter(r["category"] for r in kept)
print(f"  保留 {len(kept)} 条 / 丢弃 {len(dropped)} 条")
print(f"  写入 {OUT}")
print()
print("  按类别：")
for k, v in c.most_common():
    print(f"    {k:<22}{v}")
if dropped:
    print()
    print("  丢弃原因：")
    for i, why in dropped:
        print(f"    {i:<28}{why}")
