import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 从 _dg = ctx.get("diag") 那行（缩进 12）往后，到第一个缩进 <= 8 的非空行
start = None
for i, ln in enumerate(lines):
    if ln.strip() == '_dg = ctx.get("diag") or {}':
        ind = len(ln) - len(ln.lstrip())
        if ind == 12:
            start = i
            break
assert start is not None, "no _dg at indent 12"

end = None
for i in range(start, len(lines)):
    ln = lines[i]
    if not ln.strip():
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= 8:
        end = i
        break
assert end is not None, "no block end"
print("  去缩进范围：%d..%d（%d 行）" % (start + 1, end, end - start))
# 起点那行 12 -> 8，其余同段整体减 4
n = 0
for i in range(start, end):
    ln = lines[i]
    if not ln.strip():
        continue
    assert ln.startswith("    "), "行 %d 缩进不足: %r" % (i + 1, ln[:20])
    lines[i] = ln[4:]
    n += 1

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  已处理 %d 行" % n)