import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  === 1980-2078 ===")
for i in range(1979, min(2079, len(lines))):
    ln = lines[i]
    ind = len(ln) - len(ln.lstrip())
    mark = ">>" if i + 1 == 1998 else "  "
    print("%s%5d [%2d] %s" % (mark, i + 1, ind, ln.strip()[:82]))