import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
# 从 2006 往前找缩进 < 8 的控制流行
print("  2006 行之前，缩进 < 8 的控制流：")
for i in range(2005, 1900, -1):
    ln = lines[i]
    if not ln.strip():
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind < 8 and ln.strip().startswith(("if ", "for ", "else:", "elif ", "try:", "with ")):
        print("    %5d [%d] %s" % (i + 1, ind, ln.strip()[:80]))
        if ind <= 4:
            break
print()
print("  _mm3 现在在哪：")
for i, ln in enumerate(lines, 1):
    if "_mm3" in ln and len(ln) - len(ln.lstrip()) <= 4:
        print("    %5d [%d] %s" % (i, len(ln) - len(ln.lstrip()), ln.strip()[:80]))