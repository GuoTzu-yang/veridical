import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 剪：The consequence 的 L.append(...) + L.append("")（1996..2003）
s0 = None
for i, ln in enumerate(lines):
    if "The consequence for the rest of the report" in ln:
        j = i
        while j > 0 and not lines[j].strip().startswith("L.append("):
            j -= 1
        s0 = j
        break
assert s0 is not None
e0 = None
for i in range(s0, len(lines)):
    if lines[i].strip().startswith('L.append("")'):
        e0 = i + 1
        break
assert e0 is not None
print("  剪出 %d..%d（%d 行）" % (s0 + 1, e0, e0 - s0))
block = lines[s0:e0]
del lines[s0:e0]

# 插：The three panels 那段的 L.append("") 之后（缩进 4 的顶层）
ins = None
for i, ln in enumerate(lines):
    if "The three panels are the reason" in ln:
        j = i
        while j < len(lines) and not lines[j].strip().endswith('")'):
            j += 1
        ins = j + 1
        break
assert ins is not None
while ins < len(lines) and lines[ins].strip().startswith('L.append("")'):
    ins += 1
print("  插入位置 %d" % (ins + 1))

# The consequence 提到顶层：缩进 8 -> 4，12 -> 8
out = []
for x in block:
    if not x.strip():
        out.append(x)
        continue
    ind = len(x) - len(x.lstrip())
    out.append("    " * max(1, ind // 4 - 1) + x.lstrip())
lines[ins:ins] = out

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  完成")