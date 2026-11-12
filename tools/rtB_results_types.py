"""rtB / results board: dump type_coverage (label counts) read-only."""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
d = json.load(open(os.path.join(FINAL, "data.json"), encoding="utf-8"))

tc = d["type_coverage"]
print("n type_coverage rows:", len(tc))
print("row keys:", list(tc[0].keys()))
print()
for r in tc:
    print(" ", r)

print("\n=== derived label counts ===")
for key in tc[0].keys():
    vals = [r[key] for r in tc if isinstance(r[key], list)]
    if vals:
        c = Counter(v for lst in vals for v in lst)
        print(" field %-16s total assignments=%d  %s" % (key, sum(c.values()), dict(c)))

# rows where curated vs detected
if "curated" in tc[0] and "detected" in tc[0]:
    print("\n=== per-problem curated vs detected ===")
    for r in tc:
        cur, det = set(r["curated"]), set(r["detected"])
        print("  %-18s curated=%-38s detected=%-38s exact=%s" %
              (r.get("name"), sorted(cur), sorted(det), cur == det))
    print("\ncurated counts:", Counter(v for r in tc for v in r["curated"]))
    print("detected counts:", Counter(v for r in tc for v in r["detected"]))
    full = sum(1 for r in tc if set(r["curated"]) == set(r["detected"]))
    print("fully classified (curated==detected): %d of %d" % (full, len(tc)))
