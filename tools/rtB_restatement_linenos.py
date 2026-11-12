# -*- coding: utf-8 -*-
"""restatement 板 · 只读探针 6：把 md 里引用的每一处行号核一遍。

只读 out/final/paper.tex；只打印（marker -> 实际行号）。
"""
from __future__ import annotations

import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

MARKERS = [
    "Type detection, which could not emit",
    "has survived an attempt to break it",
    "found our own code full of them",
    "0.94",
    "What we take as the task",
    "every number must be traceable",
    "Not supported:",
    "Problem types can be recognised",
    "Every number in this paper comes from one script",
    "a number with no artifact is visible to the verifier",
    "Problem-type coverage",
    "It is not a report generator",
    "the rule we kept returning to",
    "we introduce a mechanism that places it",
    "Threat models not addressed",
    "Relation to prior work",
    "Does the mechanism work at scale",
    "Is the checker itself trustworthy",
    "What should be verified, and where",
]


def main():
    with io.open(PAPER, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    print("被审文件：out/final/paper.tex  总行 %d" % len(lines))
    print("=" * 72)
    for m in MARKERS:
        hits = [i for i, l in enumerate(lines, start=1) if m in l]
        tag = "OK " if hits else "MISS"
        print("%s %-56s -> %s" % (tag, m[:56], hits[:6]))
    print("=" * 72)
    print("L100-L106 原文：")
    for i in range(99, 107):
        print("  L%-4d %s" % (i, lines[i - 1]))
    print("\nL1170-L1196（§11.1 声明表头与两行）:")
    for i in list(range(1172, 1178)) + list(range(1182, 1192)):
        print("  L%-4d %s" % (i, lines[i - 1]))


if __name__ == "__main__":
    main()
