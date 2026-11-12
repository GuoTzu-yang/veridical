import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
for i in range(900, 985):
    print("%5d %s" % (i + 1, lines[i][:94]))