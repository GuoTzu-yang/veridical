import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  === 找 det 的定义 ===")
for i, ln in enumerate(lines, 1):
    if "det =" in ln or "det=" in ln:
        print("  %4d %s" % (i, ln.strip()[:88]))
print()
print("  === 1655-1685 ===")
for i in range(1654, 1686):
    print("  %4d %s" % (i + 1, lines[i][:92]))