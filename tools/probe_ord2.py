import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
for i, ln in enumerate(lines, 1):
    for k in ("The consequence for the rest", "The three panels are the reason",
              "残差诊断：题目的", "前沿是怎么算出来的"):
        if k in ln:
            print("  %5d [%2d] %s" % (i, len(ln) - len(ln.lstrip()),
                                      ln.strip()[:64]))