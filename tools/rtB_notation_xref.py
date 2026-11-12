# -*- coding: utf-8 -*-
"""rtB_notation_xref.py -- symbol-table vs body first-occurrence cross-check.

For each declared symbol this prints:
  A. the declared row (verbatim)
  B. every math-mode occurrence of the symbol, with section + line
  C. the first body (L>278) occurrence of the *quantity* the symbol stands for,
     found by its English name, with the surrounding sentence
  D. whether a numeric value for that quantity is ever stated, and where

Reads out/final/paper.tex only. Prints only.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
RAW = io.open(PAPER, encoding="utf-8").read()
LINES = RAW.split("\n")


def lineno(i):
    return RAW.count("\n", 0, i) + 1


SEC_RE = re.compile(r"^\\(section|subsection)\{([^}]*)\}")
sections = [(i, m.group(2)) for i, ln in enumerate(LINES, 1)
            for m in [SEC_RE.match(ln.strip())] if m]


def section_of(line):
    cur = "<preamble>"
    for start, title in sections:
        if start <= line:
            cur = title
    return cur


print("=" * 78)
print("MATH DELIMITER INVENTORY")
print("=" * 78)
for name, pat in [
    ("dollar-inline $...$", r"(?<!\\)\$[^$]{1,400}?(?<!\\)\$"),
    ("dollar-display $$...$$", r"\$\$"),
    ("paren \\( \\)", r"\\\("),
    ("bracket \\[ \\]", r"\\\["),
    ("equation env", r"\\begin\{equation"),
    ("align env", r"\\begin\{align"),
    ("mathmode \\ensuremath", r"\\ensuremath"),
]:
    print("  %-24s %d" % (name, len(re.findall(pat, RAW))))

# ---- symbol -> quantity-name map -------------------------------------------
SPECS = [
    # (symbol, latex-pattern, quantity regex, value-regex)
    ("N", r"N", r"numeric tokens?|number of numeric tokens?|tokens in a report",
     r"\b\d[\d,]*\b(?=\s*(?:numeric )?tokens)"),
    ("T", r"T", r"token class(?:es)?|four classes|structural, configuration",
     r"\b4\b(?=\s*classes)|four classes"),
    ("tau", r"\\tau", r"tracing rate|traced tokens?|traced fraction|rate of trad",
     r"0\.\d+"),
    ("c", r"c", r"a claim under test|claim under test|conditioning set",
     r""),
    ("W", r"W", r"window length|windowed|window size|\bwindow\b",
     r"\b(?:W|window)\s*=?\s*\d+|\b\d+\s*rows?\b"),
    ("alpha", r"\\alpha", r"significance level|alpha\s*=|0\.05",
     r"0\.05"),
    ("C", r"\\mathcal\{C\}", r"channel set|eight channels|channels",
     r"\b(?:eight|8)\b(?=\s*channels)"),
    ("D", r"D", r"report digest|digest|sha256|SHA-256",
     r"sha256|SHA-256"),
]

for sym, spat, qpat, vpat in SPECS:
    print("\n" + "=" * 78)
    print("SYMBOL %s" % sym)
    print("=" * 78)
    # A. declared row
    for i in range(257, 277):
        ln = LINES[i - 1]
        if re.search(r"(?<![A-Za-z\\])" + spat + r"(?![A-Za-z])", ln) and "$" in ln:
            print("  DECLARED L%-4d %s" % (i, ln.strip()))
            break
    # B. math occurrences anywhere
    occ = [m.start() for m in
           re.finditer(r"(?<![A-Za-z\\])" + spat + r"(?![A-Za-z])", RAW)]
    body_occ = [i for i in occ if lineno(i) > 278]
    print("  MATH OCCURRENCES total=%d  body(L>278)=%d" % (len(occ), len(body_occ)))
    for i in body_occ[:10]:
        ln = lineno(i)
        print("     L%-5d [%s]" % (ln, section_of(ln)))
    # C. body first occurrence of the quantity by name
    m = re.search(qpat, RAW)
    if m:
        ln = lineno(m.start())
        lo = max(0, m.start() - 130)
        hi = min(len(RAW), m.start() + 170)
        print("  QUANTITY FIRST IN BODY  L%-5d [%s]" % (ln, section_of(ln)))
        print("     ...%s..." % RAW[lo:hi].replace("\n", " "))
    else:
        print("  QUANTITY FIRST IN BODY  -none-")
    # D. numeric value stated?
    vals = []
    if vpat:
        for vm in re.finditer(vpat, RAW):
            vals.append((lineno(vm.start()), RAW[max(0, vm.start() - 50):vm.start() + 50].replace("\n", " ")))
    print("  VALUE MENTIONS n=%d" % len(vals))
    for ln, ctx in vals[:5]:
        print("     L%-5d ...%s..." % (ln, ctx))

# ---- consistency spot-check: numbers attached to each symbol ---------------
print("\n" + "=" * 78)
print("CONSISTENCY SPOT-CHECK: every 0.05 mention")
print("=" * 78)
for m in re.finditer(r"0\.05", RAW):
    ln = lineno(m.start())
    print("  L%-5d [%s] ...%s..."
          % (ln, section_of(ln), RAW[max(0, m.start() - 90):m.start() + 70].replace("\n", " ")))

print("\n" + "=" * 78)
print("CONSISTENCY SPOT-CHECK: 'window' mentions with numbers")
print("=" * 78)
for m in re.finditer(r"window[^.]{0,90}", RAW):
    ln = lineno(m.start())
    txt = m.group(0)
    if re.search(r"\d", txt):
        print("  L%-5d [%s] %s" % (ln, section_of(ln), txt.replace("\n", " ")))

print("\n" + "=" * 78)
print("CONSISTENCY SPOT-CHECK: 'digest' / sha256 mentions")
print("=" * 78)
for m in re.finditer(r"(?:digest|sha256|SHA-256)[^.]{0,80}", RAW):
    ln = lineno(m.start())
    print("  L%-5d [%s] %s" % (ln, section_of(ln), m.group(0).replace("\n", " ")))

print("\n" + "=" * 78)
print("DONE")
