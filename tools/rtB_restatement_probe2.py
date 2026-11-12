# -*- coding: utf-8 -*-
"""scope-auditor / probe 2: does the restatement quietly loosen or tighten constraints?

Read-only. Confronts three constraint sentences from L75-L170 against machine-readable
fact sources inside the same repo:

  (1) L100-L102  "a claim may stand only if it can be traced ... and has survived an
      attempt to break it"        <- universal bar
      vs  out/final/paper.tex L1174 "Not supported:" column of the claims table
  (2) L90-L92    "every number must be traceable" is not actionable  <- narrowed bar
      vs  the four-class decomposition, which only appears in section 2
  (3) L110       "It is not a report generator"                     <- capability bound
      vs  schema.json desc of the run / skeleton commands, and gate's pdf hard check

No file is modified.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
SCHEMA = os.path.join(ROOT, "schema.json")
GATE = os.path.join(ROOT, "out", "final", "gate-report.json")

lines = open(PAPER, "r", encoding="utf-8", errors="replace").read().splitlines()


def show(a, b, label):
    print("-- %s --" % label)
    for i in range(a - 1, min(b, len(lines))):
        print("  L%-5d| %s" % (i + 1, lines[i]))
    print()


show(89, 112, "the three constraint sentences in the restatement")

print("== (1) the paper's own claims table, 'Not supported:' column ==")
print("   header row verbatim present? %r" % ("Not supported:" in "\n".join(lines),))
show(1174, 1194, "claims table rows")

print("== (2) where does the four-class decomposition actually live? ==")
for i, ln in enumerate(lines, 1):
    if "four kinds" in ln or "four classes" in ln or "fourth class" in ln:
        print("  L%-5d| %s" % (i, ln.strip()))
print("   (all of the above are outside L75-L170: %r)"
      % all(i < 75 or i > 170 for i, ln in enumerate(lines, 1)
            if "four kinds" in ln or "four classes" in ln or "fourth class" in ln))
print()

print("== (3) schema.json capability descriptions ==")
sch = json.loads(open(SCHEMA, "r", encoding="utf-8").read())
cmds = sch.get("commands")
print("schema keys: %s" % list(sch.keys())[:12])
print("n_commands=%r" % sch.get("n_commands"))
if isinstance(cmds, dict):
    items = sorted(cmds.items())
else:
    items = [(c.get("name"), c) for c in cmds]
for name, spec in items:
    if name in ("run", "skeleton", "gate", "plot", "video", "clean", "merge",
                "contract", "experiment", "hints", "selftest"):
        d = (spec or {}).get("desc", "")
        print("  %-10s %s" % (name, d[:200]))

print()
print("== (3b) gate-report.json: is a PDF a hard gate? what does 'numbers' report? ==")
gr = json.loads(open(GATE, "r", encoding="utf-8").read())
print("gate-report keys: %s" % list(gr.keys()))
checks = gr.get("checks") or []
print("checks: %d  hard_fail=%r  stamped_at=%r"
      % (len(checks), gr.get("hard_fail"), gr.get("stamped_at")))
for c in checks:
    cid = c.get("id") or c.get("name")
    if cid in ("numbers", "redteam", "pdf", "figs", "citations"):
        print("  %-12s status=%r hard=%r msg=%r"
              % (cid, c.get("status"), c.get("hard"), str(c.get("msg") or c.get("detail"))[:160]))

print()
print("== (3c) does anything in gate.py / verify.py talk about compiling? ==")
for fn in ("gate.py", "verify.py", "paper.py"):
    src = open(os.path.join(ROOT, fn), "r", encoding="utf-8", errors="replace").read()
    n = src.lower().count("compile")
    print("  %-10s occurrences of 'compile': %d" % (fn, n))
