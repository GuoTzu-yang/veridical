import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
# 从 1995 往前，找缩进 <= 4 的 if/for/def
print("  1995 行之前的外层骨架（缩进 <= 4）：")
for i in range(1994, 1600, -1):
    ln = lines[i]
    if not ln.strip():
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= 4 and (ln.strip().startswith(("if ", "for ", "def ", "else:", "elif "))):
        print("    %5d [%d] %s" % (i + 1, ind, ln.strip()[:84]))
        if ind == 0:
            break