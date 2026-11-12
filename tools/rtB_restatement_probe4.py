# -*- coding: utf-8 -*-
"""scope-auditor / probe 4 + structure census.

Probe 4: has the restatement already stated its own answers?
  Scan L75-L170 sentence by sentence for past tense / perfect aspect /
  "we found" / present-tense capability statements, and locate the section
  that would have to be read to support each one.

Census: counts inside the block (lines, paragraphs, items, refs, cites,
numbers) so the "how much of this board is restatement" claim is measurable.
Also searches out/final/*.json for any file that names the task/brief.
Read-only.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(FINAL, "paper.tex")
lines = open(PAPER, "r", encoding="utf-8", errors="replace").read().splitlines()
block = lines[74:170]
text = "\n".join(block)

print("== census of L75-L170 ==")
print("lines: %d" % len(block))
print("paragraphs: %d  (%s)" % (
    text.count("\\paragraph{"), re.findall(r"\\paragraph\{([^}]*)\}", text)))
print("items: %d" % text.count("\\item"))
print("subsections: %d" % text.count("\\subsection{"))
print("refs: %d  %r" % (len(re.findall(r"\\ref\{([^}]*)\}", text)),
                        re.findall(r"\\ref\{([^}]*)\}", text)))
print("cites: %d  %r" % (len(re.findall(r"\\cite\{([^}]*)\}", text)),
                         re.findall(r"\\cite\{([^}]*)\}", text)))
print("lines that belong to Relation-to-prior-work (L114-L169): %d"
      % len([ln for ln in lines[113:169] if ln.strip()]))
print("restatement-proper lines (L75-L113): %d"
      % len([ln for ln in lines[74:113] if ln.strip()]))

print()
print("== probe 4: sentences that read as conclusions ==")
PATTERNS = [
    (r"we found", "past tense: a finding reported as background"),
    (r"fails closed", "present-tense guarantee of the mechanism"),
    (r"does not compile", "a behaviour claim about the tool"),
    (r"we introduce", "a design decision stated before any evidence"),
    (r"we assume", "a premise stated as settled"),
    (r"kept returning to", "past tense: the rule already adopted"),
    (r"we make the spread", "past tense: what the paper did"),
    (r"is reported as not applicable", "a post-fix behaviour stated as property"),
]
flat = " ".join(block)
for pat, why in PATTERNS:
    for m in re.finditer(pat, flat):
        s = max(0, m.start() - 60)
        e = min(len(flat), m.end() + 60)
        print("  [%s]  ...%s..." % (why, flat[s:e].replace("\n", " ")))

print()
print("== probe 4b: does the block contain any future/open question? ==")
open_q = re.findall(r"([^.]*\?)", flat)
for q in open_q[:8]:
    print("  ? %r" % q.strip()[-110:])

print()
print("== probe 4c: 'fails closed' vs the paper's own Case 3 ==")
for i, ln in enumerate(lines, 1):
    if "not applicable" in ln and ("counted" in ln or "success" in ln or "stays" in ln):
        print("  L%-5d| %s" % (i, ln.strip()))

print()
print("== out/final/*.json: any file that names the task or brief? ==")
for fn in sorted(os.listdir(FINAL)):
    if not fn.endswith(".json"):
        continue
    p = os.path.join(FINAL, fn)
    try:
        raw = open(p, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    marks = [k for k in ("题面", "problem statement", "brief", "task", "题目") if k in raw]
    if marks:
        print("  %-24s marks=%s" % (fn, marks))
        for k in marks:
            idx = raw.find(k)
            print("      ...%s..." % raw[max(0, idx - 70):idx + 90].replace("\n", " "))
