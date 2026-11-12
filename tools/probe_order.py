import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  关键标记位置：")
for i, ln in enumerate(lines, 1):
    for k in ("_mm3 = ctx.get", "残差诊断：题目的", "The consequence for the rest",
              'if _fd.get("front")', "What the residuals say"):
        if k in ln:
            print("    %5d [%2d] %-30s | %s"
                  % (i, len(ln) - len(ln.lstrip()), k, ln.strip()[:44]))
print()
print("  2000-2095 骨架：")
for i in range(1999, min(2096, len(lines))):
    ln = lines[i]
    if not ln.strip():
        continue
    ind = len(ln) - len(ln.lstrip())
    st = ln.strip()
    if ind <= 8 and (st.startswith(("if ", "for ", "L.append(r\"\\subsection", "#"))
                     or "What the residuals" in st):
        print("    %5d [%2d] %s" % (i + 1, ind, st[:76]))