import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("mmkit.py", "paper.py"):
    s = open(os.path.join(HERE, f), encoding="utf-8").read()
    print("  === %s ===" % f)
    for kw in ("falsify", "ctx[\"falsify\"]", "counterexamples"):
        n = s.count(kw)
        if n:
            print("    %-18s x%d" % (kw, n))