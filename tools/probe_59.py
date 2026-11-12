import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
for name in ("fertility", "mcm2020c", "pop_panel"):
    p = os.path.join(HERE, "out", "runs", name, "paper.tex")
    r = aitaste.analyze(open(p, encoding="utf-8").read())
    print("  === %-12s %3d 分 ===" % (name, r["score"]))
    for c in (r.get("checks") or []):
        if c.get("score"):
            print("    %-22s %3d" % (c["name"], c["score"]))
            for f in (c.get("found") or [])[:3]:
                print("        %-40s x%d" % (str(f.get("phrase"))[:40],
                                            f.get("count")))