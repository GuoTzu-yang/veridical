# -*- coding: utf-8 -*-
"""rtB_notation_scan.py -- read-only scanner for the 'notation' board.

Emits, for every symbol declared in the Notation table (paper.tex L255-L278):
  * total math-mode occurrence count
  * ordered list of (line, context) first occurrences
  * the section each occurrence falls in
  * candidate unit/dimension tokens adjacent to the symbol

Reads only. Prints only. Writes nothing.
"""
import io
import os
import re
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

with io.open(PAPER, encoding="utf-8") as fh:
    RAW = fh.read()
LINES = RAW.split("\n")


def lineno(idx_char):
    return RAW.count("\n", 0, idx_char) + 1


# ---- section map ------------------------------------------------------------
SEC_RE = re.compile(r"^\\(section|subsection)\{([^}]*)\}")
sections = []  # (start_line, kind, title)
for i, ln in enumerate(LINES, 1):
    m = SEC_RE.match(ln.strip())
    if m:
        sections.append((i, m.group(1), m.group(2)))


def section_of(line):
    cur = ("<preamble>", "<preamble>")
    for start, kind, title in sections:
        if start <= line:
            cur = (kind, title)
    return "%s:%s" % cur


# ---- math spans -------------------------------------------------------------
# Collect display + inline math spans so we can tell math-mode from prose.
MATH_RE = re.compile(
    r"\\begin\{equation\*?\}.*?\\end\{equation\*?\}"
    r"|\\begin\{align\*?\}.*?\\end\{align\*?\}"
    r"|\$\$.*?\$\$"
    r"|(?<!\\)\$[^$]{1,400}?(?<!\\)\$",
    re.S,
)
math_spans = [(m.start(), m.end()) for m in MATH_RE.finditer(RAW)]


def in_math(idx):
    for a, b in math_spans:
        if a <= idx < b:
            return True
    return False


# ---- declared symbols (transcribed from the Notation table) -----------------
SYMBOLS = [
    ("N", r"N", "numeric tokens in a report"),
    ("T", r"T", "token classes"),
    ("\\tau", r"\\tau", "tracing rate"),
    ("c", r"c", "a claim under test"),
    ("W", r"W", "window length"),
    ("\\alpha", r"\\alpha", "significance level"),
    ("\\mathcal{C}", r"\\mathcal\{C\}", "channel set"),
    ("D", r"D", "report digest"),
]

# a symbol occurrence in math mode: not preceded by a letter/backslash
def find_occ(pat):
    out = []
    rx = re.compile(r"(?<![A-Za-z\\])" + pat + r"(?![A-Za-z])")
    for m in rx.finditer(RAW):
        if in_math(m.start()):
            out.append(m.start())
    return out


print("=" * 78)
print("PAPER:", PAPER)
print("LINES:", len(LINES), " CHARS:", len(RAW))
print("MATH SPANS:", len(math_spans))
print("SECTIONS:")
for start, kind, title in sections:
    print("   L%-5d %-10s %s" % (start, kind, title))
print("=" * 78)


# ---- 1. Notation table rows -------------------------------------------------
tbl_start = tbl_end = None
for i, ln in enumerate(LINES, 1):
    if "\\label{tab:notation}" in ln:
        tbl_end = i
for i in range(tbl_end or 1, 0, -1):
    if "\\begin{table}" in LINES[i - 1]:
        tbl_start = i
        break
print("NOTATION TABLE: L%s - L%s" % (tbl_start, tbl_end))

print("\n--- declared rows ---")
for name, pat, meaning in SYMBOLS:
    print("  %-16s %s" % (name, meaning))

# ---- 2. per-symbol occurrence census ---------------------------------------
print("\n" + "=" * 78)
print("OCCURRENCE CENSUS (math mode only)")
print("=" * 78)
census = {}
for name, pat, meaning in SYMBOLS:
    occ = find_occ(pat)
    census[name] = occ
    print("\n### %s   (declared: %s)   n=%d" % (name, meaning, len(occ)))
    for idx in occ:
        ln = lineno(idx)
        lo = max(0, idx - 60)
        hi = min(len(RAW), idx + 60)
        ctx = RAW[lo:hi].replace("\n", " ")
        print("    L%-5d [%s] ...%s..." % (ln, section_of(ln), ctx))
    if not occ:
        print("    (no math-mode occurrence found)")

# ---- 3. undefined-looking symbols used before the table ---------------------
print("\n" + "=" * 78)
print("SYMBOLS APPEARING BEFORE THE NOTATION SECTION (L<%d)" % 255)
print("=" * 78)
for name, pat, meaning in SYMBOLS:
    occ = [i for i in census[name] if lineno(i) < 255]
    if occ:
        print("  %-16s first L%-5d (%d occurrences before L255)"
              % (name, lineno(occ[0]), len(occ)))
    else:
        print("  %-16s none before L255" % name)

# ---- 4. unit / dimension adjacency -----------------------------------------
print("\n" + "=" * 78)
print("UNIT / DIMENSION ADJACENCY (declared-row text only)")
print("=" * 78)
UNIT_WORDS = [
    "unit", "units", "s", "sec", "second", "seconds", "ms", "%", "percent",
    "ratio", "fraction", "proportion", "count", "integer", "rows", "tokens",
    "level", "probability", "p-value", "dimensionless", "bytes",
]
for name, pat, meaning in SYMBOLS:
    row = None
    for i in range((tbl_start or 1), (tbl_end or 1) + 1):
        ln = LINES[i - 1]
        if re.search(r"(?<![A-Za-z\\])" + pat + r"(?![A-Za-z])", ln) and "$" in ln:
            row = ln
            break
    low = (row or "").lower()
    hits = [w for w in UNIT_WORDS if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)]
    print("  %-16s units_in_row=%-28s | row: %s"
          % (name, ",".join(hits) if hits else "-NONE-", (row or "").strip()[:110]))

# ---- 5. bare-text (non-math) uses of the same letters ----------------------
print("\n" + "=" * 78)
print("NON-MATH BARE USES OF SINGLE LETTERS IN PROSE (sample, first 6 each)")
print("=" * 78)
PROSE_NOTE = {
    "N": r"\bN\b", "T": r"\bT\b", "c": r"\bc\b", "W": r"\bW\b",
    "D": r"\bD\b",
}
for name, pat in PROSE_NOTE.items():
    hits = []
    rx = re.compile(pat)
    for m in rx.finditer(RAW):
        if not in_math(m.start()):
            hits.append(m.start())
    print("\n  %s : %d prose hits" % (name, len(hits)))
    for idx in hits[:6]:
        ln = lineno(idx)
        lo = max(0, idx - 55)
        hi = min(len(RAW), idx + 55)
        print("     L%-5d ...%s..." % (ln, RAW[lo:hi].replace("\n", " ")))

print("\n" + "=" * 78)
print("DONE")
