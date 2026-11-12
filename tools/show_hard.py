import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = [
    ("gate.py", 749),
    ("mmkit.py", 4788),
    ("abstract.py", 238),
    ("innovation.py", 188),
]
for f, no in TARGETS:
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8").read().splitlines()
    lo = max(0, no - 8)
    hi = min(len(lines), no + 3)
    print("=" * 70)
    print("%s:%d" % (f, no))
    print("=" * 70)
    for i in range(lo, hi):
        mark = ">>" if i + 1 == no else "  "
        print("%s %4d  %s" % (mark, i + 1, lines[i][:96]))
    print()