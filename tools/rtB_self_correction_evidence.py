# -*- coding: utf-8 -*-
"""Read-only probe 4: pre-flight the literal markers used as `evidence`.

gate greps each finding's `evidence` string inside its `where` file, so every
marker must exist byte-for-byte. This probe checks candidates and also prints
the surrounding line so the auditor can see the context. Writes nothing.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [
    ("out/final/paper.tex", ["log contains 29", "30 rounds of a 129",
                             "30 repair", "The log contains 29",
                             "128 recorded rounds of repair"]),
    ("out/final/redteam-report.md", ["29 recorded rounds", "**30**"]),
    ("交接-第122轮.md", ["1053 → 28", "1482 → 263"]),
]

for rel, marks in CASES:
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    print("=" * 78)
    print("FILE:", rel, "exists:", os.path.exists(p))
    if not os.path.exists(p):
        continue
    with open(p, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    for m in marks:
        n = text.count(m)
        print("  [%s]  occurrences=%d" % (m, n))
        if n:
            for i, ln in enumerate(lines, 1):
                if m in ln:
                    print("      L%d: %s" % (i, ln.strip()[:150]))
                    break
