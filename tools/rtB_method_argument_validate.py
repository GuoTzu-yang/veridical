# -*- coding: utf-8 -*-
"""Self-validation of the deliverable pair. READ-ONLY on paper.tex and sources."""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = os.path.join(ROOT, "out", "红队七板", "method_argument-alternative-auditor.json")
M = os.path.join(ROOT, "out", "红队七板", "method_argument-alternative-auditor.md")

d = json.loads(io.open(J, encoding="utf-8").read())
print("section=%s role=%s verdict=%s" % (d["section"], d["role"], d["verdict"]))
print("probes=%d" % len(d["probes"]))
ok = True
for i, p in enumerate(d["probes"], 1):
    v = p["verdict"]
    tried = p.get("tried", "")
    where = p.get("where", "")
    ev = p.get("evidence", "")
    line = ""
    if where:
        pth = os.path.join(ROOT, where.replace("/", os.sep))
        exists = os.path.isfile(pth)
        if exists:
            hit = [n for n, l in enumerate(io.open(pth, encoding="utf-8").read().split("\n"), 1)
                   if ev and ev in l]
            line = "file=%s mark_lines=%s" % (exists, hit or "MISSING")
            if not hit:
                ok = False
        else:
            line = "file=MISSING"
            ok = False
    print("  P%d %-8s tried_len=%-4d %s len=%d %s"
          % (i, v, len(tried), "where=" + (where or "-"), len(ev), line))
    if v == "pass" and len(tried) < 30:
        ok = False
        print("      PASS WITHOUT tried>=30 -> invalid")
    if v == "finding" and (not where or len(ev) < 3):
        ok = False
        print("      FINDING WITHOUT where/evidence>=3 -> invalid")

resolved = d.get("resolved", "")
print("resolved_len=%d starts_with_unhandled=%s" % (len(resolved), resolved.startswith("未处理")))
any_finding = any(p["verdict"] == "finding" for p in d["probes"])
if any_finding and not resolved:
    ok = False
    print("  HAS FINDING BUT EMPTY resolved -> invalid")

md = io.open(M, encoding="utf-8").read()
need = ["方法", "替代", "理由", "探针 1", "探针 2", "探针 3", "探针 4", "未处理", "复现"]
missing = [n for n in need if n not in md]
print("md_len=%d missing_tokens=%s md_pipes=%d" % (len(md), missing or "none", md.count("| ")))
if missing:
    ok = False

print("\nDELIVERABLE SELF-CHECK: %s" % ok)
sys.exit(0 if ok else 1)
