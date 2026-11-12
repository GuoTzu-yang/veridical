import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  移动后的结构（找残差节）：")
for i, ln in enumerate(lines, 1):
    if "残差诊断：题目的" in ln or "What the residuals say" in ln or 'label{tab:diag}' in ln:
        ind = len(ln) - len(ln.lstrip())
        print("    %5d [%2d] %s" % (i, ind, ln.strip()[:70]))
print()
print("  外层骨架（缩进 <= 4 的 if，1950-2100）：")
for i in range(1949, min(2100, len(lines))):
    ln = lines[i]
    if ln.strip().startswith(("if ", "for ")) and len(ln) - len(ln.lstrip()) <= 4:
        print("    %5d [%d] %s" % (i + 1, len(ln) - len(ln.lstrip()), ln.strip()[:70]))