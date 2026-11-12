import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 定位 "The consequence" 段：从 L.append( 到 parsimony.")
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
    if "parsimony." in lines[i]:
        e0 = i + 1
        break
assert e0 is not None
print("  The consequence 段：%d..%d（%d 行）" % (s0 + 1, e0, e0 - s0))
block = lines[s0:e0]
del lines[s0:e0]

# 定位 "The three panels" 段之后（parsimony 之外，找它的 L.append("") 之后）
ins = None
for i, ln in enumerate(lines):
    if "The three panels are the reason" in ln:
        j = i
        while j < len(lines) and not lines[j].strip().endswith('")'):
            j += 1
        ins = j + 1
        break
assert ins is not None, "no panels end"
while ins < len(lines) and lines[ins].strip().startswith("L.append(\"\")"):
    ins += 1
print("  插入位置：%d" % (ins + 1))
lines[ins:ins] = block

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  顺序已恢复")