"""rtB / results board: the author's own existing review for section == results.

Read-only. Prints only.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT = os.path.join(ROOT, "out", "final", "redteam.json")
d = json.load(open(RT, encoding="utf-8"))

print("top-level keys:", list(d.keys()) if isinstance(d, dict) else type(d))
revs = d.get("reviews", d) if isinstance(d, dict) else d
print("n reviews:", len(revs))
print("\n=== which sections have a review? ===")
for r in revs:
    print("  section=%-28r role=%r probes=%s" %
          (r.get("section"), r.get("role"), len(r.get("probes", []))))

hits = [r for r in revs if str(r.get("section")) == "results"]
print("\n=== results section review present? ===", bool(hits))
for r in hits:
    print("\nrole:", r.get("role"))
    print("verdict:", r.get("verdict"))
    print("resolved:", r.get("resolved"))
    for i, p in enumerate(r.get("probes", []), 1):
        print("\n  probe #%d" % i)
        for k in ("probe", "verdict", "note", "tried", "where", "evidence"):
            v = p.get(k)
            if v is not None:
                print("    %-8s %s" % (k, str(v)[:400]))
