# -*- coding: utf-8 -*-
"""Read-only self-check of the deliverable before handing it in.

Reproduces the gate's rules locally: 4 probes, verdict in {pass,finding},
every pass has tried >= 30 chars, every finding has where+evidence (>=3 chars)
and that evidence literally exists in the where file, resolved present when any
finding exists. Prints only. Writes nothing.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONP = os.path.join(ROOT, "out", "红队七板", "self_correction-confession-auditor.json")
MDP = os.path.join(ROOT, "out", "红队七板", "self_correction-confession-auditor.md")

with open(JSONP, "r", encoding="utf-8") as f:
    d = json.load(f)

print("JSON parses OK")
print("section:", d.get("section"), " role:", d.get("role"))
probes = d.get("probes") or []
print("probes:", len(probes))

bad = 0
nfind = 0
for i, p in enumerate(probes, 1):
    v = p.get("verdict")
    tried = p.get("tried") or ""
    ok = True
    if v not in ("pass", "finding"):
        print("  [%d] BAD verdict %r" % (i, v)); ok = False
    if v == "pass" and len(tried) < 30:
        print("  [%d] BAD pass without tried>=30 (len=%d)" % (i, len(tried))); ok = False
    if v == "finding":
        nfind += 1
        w = p.get("where") or ""
        e = p.get("evidence") or ""
        if not w or not e or len(e) < 3:
            print("  [%d] BAD finding missing where/evidence" % i); ok = False
        else:
            fp = os.path.join(ROOT, w.replace("/", os.sep))
            if not os.path.exists(fp):
                print("  [%d] BAD where file missing: %s" % (i, w)); ok = False
            else:
                txt = open(fp, "r", encoding="utf-8").read()
                n = txt.count(e)
                if n == 0:
                    print("  [%d] BAD evidence not found in %s: %r" % (i, w, e)); ok = False
                else:
                    print("  [%d] finding evidence OK: %r in %s (x%d)" % (i, e, w, n))
    print("  [%d] %-16s len(tried)=%d  %s" % (i, v, len(tried), "ok" if ok else "FAIL"))
    bad += 0 if ok else 1

resolved = d.get("resolved") or ""
print("findings:", nfind, " resolved present:", bool(resolved),
      " contains 未处理:", "未处理" in resolved)
print("board verdict:", d.get("verdict"))

print("MD exists:", os.path.exists(MDP), " bytes:", os.path.getsize(MDP) if os.path.exists(MDP) else 0)
if os.path.exists(MDP):
    md = open(MDP, "r", encoding="utf-8").read()
    for need in ("例 A", "例 B", "错在哪", "怎么发现", "改了什么", "为什么这个改法是对的",
                 "log contains 29", "30 rounds of a 129"):
        print("   md contains %-22r %s" % (need, need in md))

print()
print("SELF-CHECK:", "PASS" if bad == 0 and nfind >= 1 else "REVIEW")
