# -*- coding: utf-8 -*-
"""rtB_notation_verify_evidence.py -- self-check before shipping.

Every evidence marker I intend to put in the JSON is grepped here, verbatim,
against the file named in `where`. A marker that does not appear makes the
finding invalid, so this runs before the report is written.
Exit code 0 only if every marker is found.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = [
    # (probe, where_relative_to_ROOT, evidence, why)
    ("P1", "out/final/paper.tex", "enlarging the window",
     "W's object (counterexample sub-range) vs LLM context window"),
    ("P1", "out/final/paper.tex", "context window is short of",
     "same word, second object"),
    ("P1", "out/final/paper.tex", "an instruction channel",
     "C's word reused for prompt-injection channel"),
    ("P1", "out/final/paper.tex", "channel set",
     "C declared"),
    ("P2", "out/final/paper.tex", "$R^2=0.94$",
     "R used WITH a value at L81, never declared"),
    ("P2", "out/final/paper.tex", "$n=84$",
     "n used WITH a value at L792, never declared"),
    ("P2", "out/final/paper.tex",
     "Every symbol used with a value in this paper is defined here.",
     "the caption claim that the two above falsify"),
    ("P3", "out/final/paper.tex",
     "token classes & structural, configuration, temporal, computed",
     "T's declared member list: four items"),
    ("P3", "out/final/tab_anatomy.tex", "Tabulated data",
     "fifth class present in the authoritative table"),
    ("P3", "out/final/paper.tex", "tabulated input data",
     "fifth class present in the body text too"),
    ("P3", "out/final/paper.tex", "four classes with different legitimate sources",
     "body calls the five-item list four"),
    ("P3", "out/final/paper.tex", "class B",
     "alpha's annotation cites an undefined lettered class scheme"),
    ("P3", "out/final/tab_anatomy.tex", "1483",
     "untraced total in the anatomy table"),
    ("P3", "out/final/paper.tex", "1053",
     "computed count in body = 1053 vs table 1054"),
    ("P4", "out/final/paper.tex", "rows per sub-range",
     "W's unit, written"),
    ("P4", "out/final/paper.tex", "traced tokens / $N$",
     "tau written as a ratio of token counts (dimensionless)"),
    ("IMPL", "falsify.py", "min_seg: int = 8",
     "window is a row count, default 8"),
    ("IMPL", "falsify.py", "min_seg = max(3, min(min_seg, len(pairs) // 2))",
     "window silently changes under heavy ties"),
]

print("=" * 78)
print("EVIDENCE SELF-CHECK (verbatim grep, as gate will do)")
print("=" * 78)
bad = 0
cache = {}
for probe, where, ev, why in CHECKS:
    p = os.path.join(ROOT, where.replace("/", os.sep))
    if p not in cache:
        cache[p] = io.open(p, encoding="utf-8").read() if os.path.exists(p) else None
    txt = cache[p]
    if txt is None:
        print("  MISSING FILE  %-28s %s" % (where, ev))
        bad += 1
        continue
    ok = ev in txt
    n = txt.count(ev)
    print("  %-5s %-6s x%-2d  %-30s | %s"
          % (probe, "FOUND" if ok else "ABSENT", n, where, ev[:46]))
    print("        why: %s" % why)
    if not ok:
        bad += 1

print("\n" + "=" * 78)
print("RESULT: %d checked, %d absent" % (len(CHECKS), bad))
print("=" * 78)
sys.exit(0 if bad == 0 else 1)
