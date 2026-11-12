import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
lines = open(P, encoding="utf-8").read().splitlines()

# 定位：_sp 计算行 → if _sp: → L += [figure...] → ... → L.append("")
i = None
for k, ln in enumerate(lines):
    if '_sp = (ctx.get("figures") or {}).get("surfaces")' in ln:
        i = k
        break
assert i is not None, "no _sp"

# 外层 if _sp: 改成 if _sp or _dg_ok:
j = i + 1
assert lines[j].strip() == "if _sp:", "unexpected: %r" % lines[j]
lines[j] = lines[j].replace("if _sp:", "if _sp or _dg_ok:")

# 在 _sp 行之前插 _dg_ok
lines.insert(i, " " * (len(lines[i]) - len(lines[i].lstrip()))
             + "_dg_ok = bool((ctx.get(\"diag\") or {}).get(\"rows\"))")

# 图那一段：从 L += [r"\begin{figure} 到 L.append("")
start = None
for k in range(i, min(i + 12, len(lines))):
    if r'L += [r"\begin{figure}[H]"' in lines[k]:
        start = k
        break
assert start is not None, "no figure start"
end = None
for k in range(start, min(start + 14, len(lines))):
    if 'r"\\label{fig:surfaces}", r"\\end{figure}"]' in lines[k]:
        end = k
        break
assert end is not None, "no figure end"
# 给 start..end 前加 if _sp: 并整体缩进 4
indent = " " * (len(lines[start]) - len(lines[start].lstrip()))
lines.insert(start, indent + "if _sp:")
for k in range(start + 1, end + 2):
    lines[k] = "    " + lines[k]

s = "\n".join(lines) + "\n"
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  split done: _dg_ok=%s, figure lines %d..%d" % (True, start, end))