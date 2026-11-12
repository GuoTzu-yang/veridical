import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(HERE, "domain.py"), encoding="utf-8").read().splitlines()
print("  === domain.py 310-345 ===")
for i in range(305, min(350, len(d))):
    print("%4d %s" % (i + 1, d[i][:92]))