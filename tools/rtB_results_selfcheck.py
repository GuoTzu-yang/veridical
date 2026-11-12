"""rtB / results board: self-check the delivered JSON (shape + evidence greppable).

Read-only over the report and the evidence files. Prints only.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rep = os.path.join(ROOT, "out", "红队七板", "results-reproducibility-auditor.json")

d = json.load(open(rep, encoding="utf-8"))
print("JSON parses OK")
print("section:", d["section"], "| role:", d["role"], "| verdict:", d["verdict"])
print("n probes:", len(d["probes"]))

ok = True
for i, p in enumerate(d["probes"], 1):
    v = p["verdict"]
    tried = p.get("tried", "")
    print("\nprobe #%d  verdict=%s  tried_len=%d" % (i, v, len(tried)))
    if v == "pass" and len(tried) < 30:
        print("   FAIL: pass without tried >= 30 chars")
        ok = False
    if v == "finding":
        where = p.get("where", "")
        ev = p.get("evidence", "")
        full = os.path.join(ROOT, where.replace("/", os.sep))
        exists = os.path.exists(full)
        grep = False
        if exists and len(ev) >= 3:
            txt = open(full, encoding="utf-8", errors="replace").read()
            grep = ev in txt
        print("   where=%s exists=%s evidence=%r greppable=%s" %
              (where, exists, ev, grep))
        if not (exists and grep):
            ok = False
print("\nresolved present:", bool(d.get("resolved")))
print("\nSELF-CHECK:", "PASS" if ok else "FAIL")
