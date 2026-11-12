import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("paper.py", "cards.py", "mmkit.py"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    lines = open(p, encoding="utf-8").read().splitlines()
    for i, ln in enumerate(lines, 1):
        if "not supported" in ln or "supported the sign" in ln:
            print("  %-10s:%d  %s" % (f, i, ln.strip()[:88]))