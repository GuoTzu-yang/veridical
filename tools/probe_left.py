import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
lines = s.splitlines()
for i, ln in enumerate(lines, 1):
    if "print(json.dumps" in ln:
        print("  %5d %s" % (i, ln.strip()[:96]))