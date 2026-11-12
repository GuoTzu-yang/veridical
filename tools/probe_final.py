import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  1990-2010:")
for i in range(1989, 2010):
    print("%5d [%2d] %s" % (i + 1, len(lines[i]) - len(lines[i].lstrip()),
                             lines[i].strip()[:74]))
print()
print("  2065-2100:")
for i in range(2064, min(2100, len(lines))):
    print("%5d [%2d] %s" % (i + 1, len(lines[i]) - len(lines[i].lstrip()),
                             lines[i].strip()[:74]))