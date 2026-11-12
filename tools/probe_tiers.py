import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
for name in ("heat_sink", "population", "evaluation", "birth_rate", "age_struct"):
    p = os.path.join(HERE, "out", "runs", name, "paper.tex")
    if not os.path.exists(p):
        continue
    r = aitaste.analyze(open(p, encoding="utf-8").read())
    print("  === %-12s %3d 分 (%s) ===" % (name, r["score"], r["grade"]))
    for c in (r.get("checks") or []):
        if c.get("score"):
            print("    %-24s %3d" % (c["name"], c["score"]))
            for f in (c.get("found") or [])[:3]:
                print("        %-38s x%d" % (str(f.get("phrase"))[:38],
                                            f.get("count")))