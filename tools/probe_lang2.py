import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("mmkit.py", "paper.py", "aitaste.py"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if "lang" in ln and ("out" in ln or "tex" in ln or "join" in ln):
            print("  %-12s:%-5d%s" % (f, no, ln.strip()[:88]))