import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
t = open(os.path.join(HERE, "out", "runs", "age_struct", "paper.tex"),
         encoding="utf-8").read()
r = aitaste.analyze(t)
print("  keys:", list(r.keys())[:8])
print("  score:", r.get("score"))
for k in ("items", "issues", "detail", "rules"):
    v = r.get(k)
    if isinstance(v, list) and v:
        print("  %s (%d):" % (k, len(v)))
        for it in v[:8]:
            if isinstance(it, dict):
                print("    %s" % str(it)[:120])