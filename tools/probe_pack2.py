import os
p = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools", "pack.py")
lines = open(p, encoding="utf-8").read().splitlines()
for i, ln in enumerate(lines, 1):
    if i < 40 or ("out" in ln and ("fig" in ln or "data" in ln)):
        print("  %4d  %s" % (i, ln[:92]))