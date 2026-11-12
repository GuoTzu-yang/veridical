# -*- coding: utf-8 -*-
"""rtB_notation_poly.py -- polysemy hunt for the eight declared symbols.

For each declared symbol, searches the whole paper for OTHER objects that the
same glyph/letter stands for: error-class labels (class A/B/C/D), the literal
N/A token, the word forms, and any competing mathematical role. Reports every
hit with line + section so each claim is checkable by grep.

Reads paper.tex and the \\input-ed .tex tables. Prints only.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(FINAL, "paper.tex")
RAW = io.open(PAPER, encoding="utf-8").read()
LINES = RAW.split("\n")

SEC_RE = re.compile(r"^\\(section|subsection)\{([^}]*)\}")
sections = [(i, m.group(2)) for i, ln in enumerate(LINES, 1)
            for m in [SEC_RE.match(ln.strip())] if m]


def lineno(i):
    return RAW.count("\n", 0, i) + 1


def section_of(line):
    cur = "<preamble>"
    for start, title in sections:
        if start <= line:
            cur = title
    return cur


def hits(pat, flags=0, limit=40):
    out = []
    for m in re.finditer(pat, RAW, flags):
        ln = lineno(m.start())
        out.append((ln, section_of(ln),
                    RAW[max(0, m.start() - 70):m.start() + 80].replace("\n", " ")))
    return out[:limit]


print("=" * 78)
print("A. ERROR-CLASS LABELS  (would collide with C = channel set, D = digest)")
print("=" * 78)
for pat, label in [
    (r"\bclass\s+[A-D]\b", "class A-D"),
    (r"\bClass\s+[A-D]\b", "Class A-D"),
    (r"\bfour classes\b", "four classes"),
    (r"\bsix defect classes\b", "six defect classes"),
    (r"class~[A-D]", "class~A-D"),
]:
    h = hits(pat)
    print("\n  %-22s n=%d" % (label, len(h)))
    for ln, sec, ctx in h:
        print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("B. LITERAL 'N/A' TOKEN  (collides with N = numeric tokens)")
print("=" * 78)
h = hits(r"N/A")
print("  n=%d" % len(h))
for ln, sec, ctx in h:
    print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("C. THE WORD 'class' / 'classes' EVERYWHERE (what T is declared to be)")
print("=" * 78)
h = hits(r"\bclasses?\b")
print("  n=%d" % len(h))
for ln, sec, ctx in h:
    print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("D. 'time axis' / T-as-time  (Case 6 claims two definitions)")
print("=" * 78)
for pat in [r"time axis", r"time-axis", r"axis"]:
    h = hits(pat)
    print("\n  %-14s n=%d" % (pat, len(h)))
    for ln, sec, ctx in h[:12]:
        print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("E. CONTEXT OF L626 (where bare 'c' was flagged)")
print("=" * 78)
for i in range(620, 634):
    print("  L%-5d %s" % (i, LINES[i - 1]))

print("\n" + "=" * 78)
print("F. 'channel' WORD vs C=channel set ; 'scope' word")
print("=" * 78)
for pat in [r"\bchannels?\b", r"\bscope\b"]:
    h = hits(pat)
    print("\n  %-14s n=%d" % (pat, len(h)))
    for ln, sec, ctx in h[:14]:
        print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("G. THE WORD 'window' (W = window length) - all mentions")
print("=" * 78)
h = hits(r"\bwindow\w*", limit=60)
print("  n=%d" % len(h))
for ln, sec, ctx in h:
    print("     L%-5d [%s] ...%s..." % (ln, sec[:44], ctx))

print("\n" + "=" * 78)
print("DONE")
