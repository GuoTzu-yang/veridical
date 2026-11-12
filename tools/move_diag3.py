import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 残差节：从 "# 残差诊断" 到 "# ── 前沿是怎么算出来的" 之前
s0 = None
for i, ln in enumerate(lines):
    if "残差诊断：题目的" in ln:
        s0 = i
        break
assert s0 is not None
e0 = None
for i in range(s0 + 1, len(lines)):
    if "前沿是怎么算出来的" in lines[i]:
        e0 = i
        break
assert e0 is not None
# 去掉尾部的空行
while e0 > s0 and not lines[e0 - 1].strip():
    e0 -= 1
print("  残差节：%d..%d（%d 行）" % (s0 + 1, e0, e0 - s0))
block = lines[s0:e0]
del lines[s0:e0]

# 现在 "前沿" 那行上移了 len(block) 行，重新定位
ins = None
for i, ln in enumerate(lines):
    if "前沿是怎么算出来的" in ln:
        ins = i
        break
assert ins is not None
# 插在 "前沿" 注释块之前（它前面可能还有空行）
while ins > 0 and not lines[ins - 1].strip():
    ins -= 1
print("  插入位置：%d" % (ins + 1))

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
print("  完成")