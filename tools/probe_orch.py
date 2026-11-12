import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "orchestrate.py")
t = open(p, encoding="utf-8").read()
print("  orchestrate.py：%d 行" % len(t.splitlines()))
print("  === 前 50 行 ===")
for i, ln in enumerate(t.splitlines()[:50], 1):
    print("  %3d %s" % (i, ln[:92]))