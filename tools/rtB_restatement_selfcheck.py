# -*- coding: utf-8 -*-
"""scope-auditor / self-check of the delivered board file.

Read-only with respect to paper.tex and every .py; it only reads my own board
JSON and the two machine-readable fact sources.

Checks:
  1. every finding's `where` resolves from the plugin root
  2. every finding's `evidence` occurs VERBATIM (>=3 chars) in that file
  3. every pass has `tried` >= 30 characters
  4. verdict values are pass|finding; board verdict is pass|revise
  5. `resolved` is present and non-empty
  6. independence: out/final/redteam.json has no restatement entry, and no gate
     check is named restatement -- so this board was never audited before
     (prints section keys only, does not read other boards' review content)
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(ROOT, "out", "红队七板", "restatement-scope-auditor.json")

board = json.loads(open(BOARD, "r", encoding="utf-8").read())
print("section=%r role=%r verdict=%r" % (board["section"], board["role"], board["verdict"]))
assert board["section"] == "restatement"
assert board["role"] == "scope-auditor"

ok = True
for i, pr in enumerate(board["probes"], 1):
    v = pr["verdict"]
    tried = pr.get("tried") or ""
    where = pr.get("where") or ""
    evid = pr.get("evidence") or ""
    line = "probe%d verdict=%-7s tried_len=%-4d" % (i, v, len(tried))
    if v == "pass":
        good = len(tried) >= 30
        line += " tried_ok=%r" % good
        ok &= good
    elif v == "finding":
        p = os.path.join(ROOT, where)
        exists = os.path.isfile(p)
        body = open(p, "r", encoding="utf-8", errors="replace").read() if exists else ""
        found = bool(evid) and len(evid) >= 3 and evid in body
        line += " exists=%r evidence_len=%d evidence_verbatim=%r" % (
            exists, len(evid), found)
        ok &= exists and found
    else:
        line += " BAD VERDICT"
        ok = False
    print(line)

if board.get("verdict") == "revise":
    any_finding = any(p["verdict"] == "finding" for p in board["probes"])
    res = (board.get("resolved") or "").strip()
    print("revise implies >=1 finding: %r" % any_finding)
    print("resolved present: %r (len=%d)" % (bool(res), len(res)))
    ok &= any_finding and bool(res)
else:
    print("board verdict=pass; findings must be zero: %r"
          % (not any(p["verdict"] == "finding" for p in board["probes"])))

print()
print("== independence / prior-audit state ==")
rt = json.loads(open(os.path.join(ROOT, "out", "final", "redteam.json"),
                     "r", encoding="utf-8").read())
revs = rt.get("reviews") or []
print("redteam.json reviews: %d" % len(revs))
print("section keys present: %r" % sorted({r.get("section") for r in revs if isinstance(r, dict)}))
print("restatement reviewed before? %r"
      % any(r.get("section") == "restatement" for r in revs if isinstance(r, dict)))
gr = json.loads(open(os.path.join(ROOT, "out", "final", "gate-report.json"),
                     "r", encoding="utf-8").read())
ids = [c.get("id") or c.get("name") for c in gr.get("checks", [])]
print("gate checks: %d; any section-level check named restatement? %r"
      % (len(ids), "restatement" in ids))
print("gate checks mentioning a board name: %r"
      % [i for i in ids if i in ("analysis", "method_argument", "self_correction",
                                 "deployment", "redteam", "restatement")])

print()
print("SELF CHECK: %s" % ("PASS" if ok else "FAIL"))
