import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 所有 \includegraphics{...} 的字面图名，改成用对应的 figs 变量
FIX = [
    ("cand", "_cp"),
    ("tornado", "_tpath"),
    ("surfaces", "_sp"),
]
for kind, var in FIX:
    # r"\includegraphics[...]{kind.pdf}"
    pat = re.compile(r'(\\includegraphics\[width=[^\]]*\]\{)' + kind + r'\.pdf(\})')
    m = pat.search(s)
    if not m:
        print("  [skip] %s: includegraphics not found" % kind)
        continue
    s = s[:m.start()] + m.group(1) + '" + ' + var + ' + "' + m.group(2) + s[m.end():]
    print("  patched includegraphics for %s" % kind)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)