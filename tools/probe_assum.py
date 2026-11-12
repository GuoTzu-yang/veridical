import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("cards.py", "domain.py", "paper.py"):
    p = os.path.join(HERE, f)
    t = open(p, encoding="utf-8").read()
    for i, ln in enumerate(t.splitlines(), 1):
        if "assumption_lines" in ln or ("assumptions" in ln and "=" in ln
                                        and "def " not in ln):
            print("  %-10s:%-4d %s" % (f, i, ln.strip()[:86]))