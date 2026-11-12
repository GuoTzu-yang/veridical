#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 dsh-plugin-writing-guard 的规则扫我们的论文。

来源：dsh-plugin-writing-guard 2.0.1 的 lib/rules.js（202,273 字符，35 条规则）。

它比我们的 aitaste.py 多三样东西：
  · profiles   —— 规则按文档类型作用域（manuscript / rebuttal / ...）
  · maxHits    —— 每条规则最多报几次，防刷屏
  · category   —— 区分 process_residue / claim_calibration /
                  rhetorical_pattern / llm_associated / academic_style

这里提取 JS 里的正则，转成 Python 扫我们的 paper.tex。
"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(os.environ.get("TEMP", "/tmp"),
                     "wg_inspect", "package", "lib", "rules.js")
TEX = os.path.join(HERE, "out", "fig", "paper.tex")

js = open(RULES, encoding="utf-8", errors="replace").read()

# 抽 id / category / severity / pattern / maxHits
pat = re.compile(
    r"\{\s*id:\s*'([^']+)',\s*\n\s*category:\s*'([^']+)',\s*\n"
    r"\s*severity:\s*'([^']+)',.*?pattern:\s*/(.+?)/g,", re.S)
found = pat.findall(js)
print(f"  从 rules.js 提取到 {len(found)} 条规则")

tex = open(TEX, encoding="utf-8").read()
# 剥 LaTeX 命令留文字
body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", tex)
body = re.sub(r"\s+", " ", body)

hits = []
for rid, cat, sev, rx in found:
    try:
        py_rx = re.compile(rx)
    except re.error:
        continue
    ms = py_rx.findall(body)
    if ms:
        hits.append((rid, cat, sev, len(ms), ms[:4]))

hits.sort(key=lambda x: -x[3])
print(f"  论文命中 {len(hits)} 条规则\n")
print(f"  {'规则':<26}{'类别':<22}{'严重':<8}次数  样例")
for rid, cat, sev, n, ex in hits:
    e = ", ".join(str(x)[:22] for x in ex[:3])
    print(f"  {rid:<26}{cat:<22}{sev:<8}{n:<5} {e}")

print()
from collections import Counter
c = Counter(h[1] for h in hits)
print("  按类别汇总:")
for k, v in c.most_common():
    print(f"    {k:<24}{v} 条规则命中")
