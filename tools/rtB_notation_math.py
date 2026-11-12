# -*- coding: utf-8 -*-
"""rtB_notation_math.py -- exhaustive inventory of every math-mode span.

Lists all 19 inline-math spans in paper.tex verbatim with line numbers, then
extracts every distinct symbol-like token appearing inside math that is NOT
one of the eight declared in the Notation table. That difference set is the
evidence base for "symbol used but never defined".

Also enumerates the same question for tab_anatomy.tex (a file the paper \\inputs)
and any other \\input-ed .tex file, because math there is part of the paper.
"""
import io
import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(FINAL, "paper.tex")
RAW = io.open(PAPER, encoding="utf-8").read()


def lineno(i, text=RAW):
    return text.count("\n", 0, i) + 1


SEC_RE = re.compile(r"^\\(section|subsection)\{([^}]*)\}")
LINES = RAW.split("\n")
sections = [(i, m.group(2)) for i, ln in enumerate(LINES, 1)
            for m in [SEC_RE.match(ln.strip())] if m]


def section_of(line):
    cur = "<preamble>"
    for start, title in sections:
        if start <= line:
            cur = title
    return cur


MATH_RE = re.compile(r"(?<!\\)\$[^$]{1,400}?(?<!\\)\$", re.S)

print("=" * 78)
print("ALL INLINE MATH SPANS IN paper.tex")
print("=" * 78)
spans = []
for m in MATH_RE.finditer(RAW):
    ln = lineno(m.start())
    spans.append((ln, m.group(0)))
    print("  L%-5d [%-52s] %s" % (ln, section_of(ln)[:52], m.group(0)))
print("  count =", len(spans))

# ---- declared symbols -------------------------------------------------------
DECLARED = {"N", "T", "tau", "c", "W", "alpha", "C", "D"}
DECLARED_RAW = {"N", "T", r"\tau", "c", "W", r"\alpha", r"\mathcal{C}", "D"}

# ---- symbol-like tokens inside math ---------------------------------------
print("\n" + "=" * 78)
print("SYMBOL-LIKE TOKENS INSIDE MATH THAT ARE NOT DECLARED")
print("=" * 78)
KEYWORDS = {
    "alpha", "beta", "gamma", "delta", "tau", "sigma", "mu", "lambda", "rho",
    "theta", "phi", "psi", "omega", "epsilon", "eta", "kappa", "nu", "xi",
    "pi", "chi", "zeta", "begin", "end", "frac", "mathcal", "mathrm",
    "text", "right", "left", "quad", "qquad", "sqrt", "cdot", "times",
    "sum", "int", "partial", "infty", "le", "ge", "ne", "approx", "sim",
    "pm", "mp", "to", "mid", "vert", "hat", "bar", "tilde", "mathbf",
}
undeclared = {}
for ln, s in spans:
    inner = s[1:-1]
    # single latin letters
    for t in re.findall(r"(?<![\\A-Za-z])([A-Za-z])(?![A-Za-z])", inner):
        if t not in DECLARED:
            undeclared.setdefault(t, []).append(ln)
    # greek / commands
    for t in re.findall(r"\\([A-Za-z]+)", inner):
        if t in KEYWORDS and t not in {"begin", "end", "frac", "mathcal",
                                       "mathrm", "text", "right", "left",
                                       "quad", "qquad", "sqrt", "cdot",
                                       "times", "sum", "int", "partial",
                                       "infty", "le", "ge", "ne", "approx",
                                       "sim", "pm", "mp", "to", "mid",
                                       "vert", "hat", "bar", "tilde",
                                       "mathbf"}:
            if t not in {"tau", "alpha"}:
                undeclared.setdefault("\\" + t, []).append(ln)

for t in sorted(undeclared):
    ls = sorted(set(undeclared[t]))
    print("  UNdeclared %-10s lines=%s" % (t, ls))

# ---- \\input-ed tex files --------------------------------------------------
print("\n" + "=" * 78)
print("\\input-ED .tex FILES (part of the paper, separate math scope)")
print("=" * 78)
inputs = re.findall(r"\\input\{([^}]*)\}", RAW)
print("  \\input targets:", inputs)
for tgt in inputs:
    p = os.path.join(FINAL, tgt)
    if not os.path.exists(p):
        print("  MISSING:", tgt)
        continue
    txt = io.open(p, encoding="utf-8").read()
    ms = MATH_RE.findall(txt)
    print("  %-24s math spans=%d" % (tgt, len(ms)))
    for s in ms:
        print("      %s" % s)
    for t in re.findall(r"(?<![\\A-Za-z])([A-Za-z])(?![A-Za-z])", " ".join(ms)):
        if t not in DECLARED:
            print("      UNdeclared single letter: %s" % t)

# ---- caption claim check ---------------------------------------------------
print("\n" + "=" * 78)
print("CAPTION CLAIM vs REALITY")
print("=" * 78)
cap = None
for i, ln in enumerate(LINES, 1):
    if "\\caption{Notation." in ln:
        cap = (i, ln.strip())
print("  caption L%s: %s" % cap)
print("  declared symbols: %d" % len(DECLARED_RAW))
print("  declared-but-never-used-in-body: ",
      sorted(s for s in DECLARED_RAW))
print("  undeclared-but-used-in-math: ", sorted(undeclared))

print("\n" + "=" * 78)
print("DONE")
