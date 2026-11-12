import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
t = open(os.path.join(HERE, "out", "runs", "age_struct", "paper.tex"),
         encoding="utf-8").read()
r = aitaste.analyze(t)
for c in (r.get("checks") or []):
    if c.get("name") == "句式重复":
        print("  score=%s total=%s" % (c.get("score"), c.get("total")))
        for f in (c.get("found") or [])[:12]:
            print("    %-46s x%d" % (str(f.get("phrase"))[:46], f.get("count")))