import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 剪出残差节：# 残差诊断 ... 到 "The consequence for the rest" 之前
s0 = None
for i, ln in enumerate(lines):
    if "残差诊断：题目的" in ln:
        s0 = i
        break
assert s0 is not None
anc = None
for i, ln in enumerate(lines):
    if "The consequence for the rest of the report" in ln:
        anc = i
        break
assert anc is not None and anc > s0
# 往前回退到该段 L.append( 的开头
e0 = anc
while e0 > s0 and lines[e0 - 1].strip() == "":
    e0 -= 1
while e0 > s0 and (not lines[e0 - 1].strip().startswith("L.append(")):
    e0 -= 1
e0 -= 1
print("  残差节：%d..%d（%d 行）" % (s0 + 1, e0, e0 - s0))
block = lines[s0:e0]
del lines[s0:e0]

# 插到 if _fd.get("front"): 之前
ins = None
for i, ln in enumerate(lines):
    if ln.strip().startswith('if _fd.get("front"):'):
        ins = i
        break
assert ins is not None, "no _fd anchor"
# 往前退到该段注释头
while ins > 0 and (lines[ins - 1].strip().startswith("#")
                   or not lines[ins - 1].strip()):
    ins -= 1
print("  插入位置：%d" % (ins + 1))

# 缩进统一到 4
out = []
for x in block:
    if not x.strip():
        out.append(x)
        continue
    ind = len(x) - len(x.lstrip())
    assert ind >= 8, "缩进不足: %r" % x[:24]
    out.append("    " + x[8:])
lines[ins:ins] = out + [""]

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  已插到 _mm3 块之后")