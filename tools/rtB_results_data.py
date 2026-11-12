"""rtB / results board: dump data.json (the taxonomy + coverage artifact) read-only."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")

d = json.load(open(os.path.join(FINAL, "data.json"), encoding="utf-8"))

print("=== data.json top-level keys ===")
for k, v in d.items():
    t = type(v).__name__
    if isinstance(v, list):
        print("  %-24s list[%d]" % (k, len(v)))
    elif isinstance(v, dict):
        print("  %-24s dict%s" % (k, list(v.keys())[:10]))
    else:
        print("  %-24s %r" % (k, v))

print("\n=== defect_taxonomy ===")
dt = d.get("defect_taxonomy", {})
for cls, rec in dt.items():
    rounds = rec.get("rounds", [])
    print("  %-22s n_rounds=%-3s rounds=%s" % (cls, rec.get("n_rounds"), rounds))
    print("     other keys:", {k: v for k, v in rec.items() if k != "rounds"})

print("\n=== scalar coverage fields ===")
for k in sorted(d):
    v = d[k]
    if not isinstance(v, (list, dict)):
        print("  %-28s %r" % (k, v))

print("\n=== per-problem objective / label fields (first 3 rows, all keys) ===")
probs = d.get("problems", [])
print("n problems:", len(probs))
if probs:
    print("keys:", list(probs[0].keys()))
    for p in probs[:3]:
        print("  ", p)
