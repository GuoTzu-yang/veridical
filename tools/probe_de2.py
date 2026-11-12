import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "domain_extra.py"), encoding="utf-8").read().splitlines()
for i, ln in enumerate(lines, 1):
    if i <= 60:
        print("%4d %s" % (i, ln[:94]))