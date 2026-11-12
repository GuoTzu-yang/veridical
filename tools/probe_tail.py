import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
for i in range(2060, 2090):
    ln = lines[i]
    ind = len(ln) - len(ln.lstrip())
    print("%5d [%2d] %s" % (i + 1, ind, ln.strip()[:80]))