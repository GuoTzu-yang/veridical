# -*- coding: utf-8 -*-
"""交付前校验（只读，只打印）：确认四条 finding 的 evidence 标记在 where 文件里逐字存在，
并复核 timing 表求和。gate 会去该文件 grep 这个标记，这里先自查一遍。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
checks = [
    ("out/final/paper.tex", "0 times in 138 cases"),
    ("out/final/paper.tex", r"23\,$\times$\,23"),
    ("out/final/paper.tex", r"Agreement is 97.5\% (195/200)"),
    ("out/final/paper.tex", "changes no content at all"),
]
ok = 0
for rel, mark in checks:
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    txt = open(p, encoding="utf-8").read()
    hit = mark in txt
    ok += hit
    idx = txt.find(mark)
    line = txt[:idx].count("\n") + 1 if hit else None
    print(f"  {'OK ' if hit else 'MISS'}  {rel}  L{line}  len={len(mark)}  {mark!r}")
print(f"markers found: {ok}/{len(checks)}")

print("-" * 60)
print("timing 表求和复核")
secs = [0.41, 0.42, 0.40, 0.20, 1.72, 0.15, 0.35, 0.46, 2.57]
print("  sum = %.2f  | 表内 total = 6.68  | 一致: %s" % (sum(secs), abs(sum(secs) - 6.68) < 0.005))
print("  slowest step = %.2f (gate)  | 正文说 2.57: %s" % (max(secs), max(secs) == 2.57))
