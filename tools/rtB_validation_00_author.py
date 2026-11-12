# -*- coding: utf-8 -*-
"""探针0（只读）：读 out/final/redteam.json 里 section=="validation" 的既有记录。
只打印，不写任何文件。"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "out", "final", "redteam.json")
print("file:", p, "exists:", os.path.exists(p))
if not os.path.exists(p):
    sys.exit(0)

with open(p, encoding="utf-8") as f:
    d = json.load(f)

print("top-level keys:", list(d.keys()) if isinstance(d, dict) else type(d))
reviews = d.get("reviews", d) if isinstance(d, dict) else d
print("n_reviews:", len(reviews))

sections = []
for r in reviews:
    sections.append(r.get("section"))
print("sections present:", sections)

hits = [r for r in reviews if r.get("section") == "validation"]
print("validation records:", len(hits))
for h in hits:
    print("-" * 70)
    print("role:", h.get("role"))
    print("verdict:", h.get("verdict"))
    print("resolved:", h.get("resolved"))
    for pr in h.get("probes", []):
        print("  probe:", pr.get("probe"))
        print("    verdict:", pr.get("verdict"))
        print("    note:", pr.get("note"))
        print("    tried:", (pr.get("tried") or "")[:120], "| len =", len(pr.get("tried") or ""))
        print("    where:", pr.get("where"), "| evidence:", pr.get("evidence"))
