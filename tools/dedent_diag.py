import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 起点：残差诊断注释行（缩进 12，在 if _sp: 里）
start = None
for i, ln in enumerate(lines):
    if "残差诊断：题目的" in ln and len(ln) - len(ln.lstrip()) == 12:
        start = i
        break
assert start is not None, "no residual comment at indent 12"

# 终点：从这里往后第一个「非空且缩进 <= 12」的行（即离开 if _sp: 块）
end = None
for i in range(start + 1, len(lines)):
    ln = lines[i]
    if not ln.strip():
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= 12:
        end = i
        break
assert end is not None, "no block end"
print("  去缩进范围：%d..%d（%d 行）" % (start + 1, end, end - start))
for i in range(start, end):
    ln = lines[i]
    if not ln.strip():
        continue
    assert ln.startswith("    "), "行 %d 缩进不足" % (i + 1)
    lines[i] = ln[4:]

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  已整段减 4 格")