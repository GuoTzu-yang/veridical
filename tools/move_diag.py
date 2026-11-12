import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 残差节：1995（1-based）..2074
s0 = None
for i, ln in enumerate(lines):
    if "残差诊断：题目的" in ln and len(ln) - len(ln.lstrip()) == 8:
        s0 = i
        break
assert s0 is not None, "no residual start"
e0 = None
for i in range(s0, len(lines)):
    if lines[i].strip() == 'L.append("")' and i > s0:
        # 残差节以 L.append("") 结束，下一段是 _mm3 的收尾
        nxt = i + 1
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        if nxt < len(lines) and "The consequence for the rest of the report" in "\n".join(lines[nxt:nxt + 6]):
            e0 = i + 1
            break
assert e0 is not None, "no residual end"
print("  残差节：%d..%d（%d 行）" % (s0 + 1, e0, e0 - s0))

block = lines[s0:e0]
del lines[s0:e0]

# 插到 _mm3 块结束后（找 "The consequence for the rest" 那段之后的第一个空行）
anchor = None
for i, ln in enumerate(lines):
    if "The consequence for the rest of the report" in ln:
        anchor = i
        break
assert anchor is not None, "no anchor"
j = anchor
while j < len(lines) and (not lines[j].strip()
                          or len(lines[j]) - len(lines[j].lstrip()) > 4):
    j += 1
print("  插入位置：%d 行之后" % j)

# 缩进 8 -> 4
block = [("    " + x[4:]) if x.strip() else x for x in block]
lines[j:j] = [""] + block

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  已移到 _mm3 块之外")