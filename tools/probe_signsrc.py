import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("cards.py", "paper.py", "mmkit.py", "falsify.py"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    lines = open(p, encoding="utf-8").read().splitlines()
    for i, ln in enumerate(lines, 1):
        if "Not supported" in ln or "The sign of" in ln or "does not fix it" in ln:
            print("  %-12s:%-5d %s" % (f, i, ln.strip()[:86]))